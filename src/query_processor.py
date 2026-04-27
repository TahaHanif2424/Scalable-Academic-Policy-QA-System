import os
import sys
import time
import tracemalloc

# ── allow both `python -m src.query_processor` (root) and
#    `python query_processor.py` (from inside src/)  ──────────────────────────
if __name__ == "__main__" and __package__ is None:
    # Running directly from inside src/ — add the directory to sys.path so
    # sibling modules can be imported without the src. prefix
    sys.path.insert(0, os.path.dirname(__file__))
    from database import get_chunks_by_ids
    from minhash import query_minhash
    from simhash import query_simhash
    from tfidf import query_tfidf
else:
    from src.database import get_chunks_by_ids
    from src.minhash import query_minhash
    from src.simhash import query_simhash
    from src.tfidf import query_tfidf


# ─── helpers ─────────────────────────────────────────────────────────────────


def _enrich(results: list[dict], source: str) -> list[dict]:
    """Fetch full chunk text and tag each result with its retrieval source."""
    # Join retrieval IDs with stored chunk metadata/text.
    if not results:
        return []

    chunk_ids = [r["chunk_id"] for r in results]
    # Fetch all chunks in one DB call and key by chunk_id for O(1) lookup below
    chunks = {c["chunk_id"]: c for c in get_chunks_by_ids(chunk_ids)}

    enriched = []
    for r in results:
        cid = r["chunk_id"]
        chunk = chunks.get(cid, {})
        enriched.append(
            {
                "chunk_id": cid,
                "page_num": chunk.get("page_num"),
                "text": chunk.get("text", ""),
                "source": source,
                # normalise score field name across methods
                # different retrievers use different key names — coalesce to "score"
                "score": r.get("score") or r.get("similarity") or 0.0,
            }
        )
    return enriched


def _timed(fn, *args, **kwargs):
    """Run fn(*args, **kwargs), return (result, elapsed_ms)."""
    # Measure wall-clock runtime of a retrieval call.
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, (time.perf_counter() - t0) * 1000


def _timed_with_memory(fn, *args, **kwargs):
    """Run fn(*args, **kwargs), return (result, elapsed_ms, peak_memory_kb)."""
    # Capture both runtime and peak traced memory for comparisons.
    tracemalloc.start()
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    # get_traced_memory returns (current, peak); we only care about peak
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, elapsed_ms, peak / 1024.0


def _hybrid_approximate(
    lsh_chunks: list[dict], sim_chunks: list[dict], top_k: int
) -> list[dict]:
    """Fuse MinHash+SimHash results into one approximate path ranking."""
    # Weighted late-fusion of LSH and SimHash candidate rankings.
    if not lsh_chunks and not sim_chunks:
        return []

    # Normalise each method's scores independently before blending so that
    # differences in raw score magnitude don't bias the fusion
    lsh_max = max((c["score"] for c in lsh_chunks), default=1.0) or 1.0
    sim_max = max((c["score"] for c in sim_chunks), default=1.0) or 1.0

    # fused accumulates weighted scores keyed by chunk_id; a chunk can appear
    # in both lists and will receive contributions from both methods
    fused: dict[int, dict] = {}

    # LSH carries more weight (0.6) as MinHash similarity is the primary signal
    for c in lsh_chunks:
        cid = c["chunk_id"]
        score = 0.6 * (c["score"] / lsh_max)
        if cid not in fused:
            fused[cid] = {**c, "source": "approx_hybrid", "score": 0.0}
        fused[cid]["score"] += score

    # SimHash contributes a smaller weight (0.4) as a complementary signal
    for c in sim_chunks:
        cid = c["chunk_id"]
        score = 0.4 * (c["score"] / sim_max)
        if cid not in fused:
            fused[cid] = {**c, "source": "approx_hybrid", "score": 0.0}
        fused[cid]["score"] += score

    ranked = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]


def _overlap_metrics(a_chunks: list[dict], b_chunks: list[dict]) -> dict:
    """Proxy relevance comparison between methods using overlap-at-k."""
    # Compute set-overlap diagnostics between two retrieval outputs.
    a_ids = [c["chunk_id"] for c in a_chunks]
    b_ids = [c["chunk_id"] for c in b_chunks]

    a_set = set(a_ids)
    b_set = set(b_ids)
    intersection = len(a_set & b_set)
    union = len(a_set | b_set)
    # k is the length of the longer list so the metric penalises size mismatches
    k = max(len(a_chunks), len(b_chunks), 1)

    return {
        "overlap_at_k": round(intersection / k, 4),
        # Jaccard is undefined when both sets are empty — guard with `if union`
        "jaccard_at_k": round(intersection / union, 4) if union else 0.0,
    }


# ─── public API ──────────────────────────────────────────────────────────────


def retrieve_lsh(query: str, top_k: int = 5) -> tuple[list[dict], float]:
    """
    LSH/MinHash retrieval.
    Returns (enriched_chunks, elapsed_ms).
    """
    # Run MinHash retrieval then attach full chunk payloads.
    raw, ms = _timed(query_minhash, query, top_k)
    return _enrich(raw, "lsh"), ms


def retrieve_simhash(query: str, top_k: int = 5) -> tuple[list[dict], float]:
    """
    SimHash retrieval.
    Returns (enriched_chunks, elapsed_ms).
    """
    # Run SimHash retrieval then attach full chunk payloads.
    raw, ms = _timed(query_simhash, query, top_k)
    return _enrich(raw, "simhash"), ms


def retrieve_tfidf(query: str, top_k: int = 5) -> tuple[list[dict], float]:
    """
    TF-IDF (baseline) retrieval.
    Returns (enriched_chunks, elapsed_ms).
    """
    # Run TF-IDF retrieval then attach full chunk payloads.
    raw, ms = _timed(query_tfidf, query, top_k)
    return _enrich(raw, "tfidf"), ms


def retrieve_all(query: str, top_k: int = 5) -> dict:
    # Execute all retrieval paths and return a unified comparison payload.

    # Path A (approximate): MinHash + SimHash hybrid
    # Each retriever is wrapped in _timed_with_memory so we get both latency
    # and peak allocation figures for the comparison payload
    (lsh_chunks, _lsh_inner_ms), lsh_ms, lsh_mem_kb = _timed_with_memory(
        retrieve_lsh, query, top_k
    )
    (sim_chunks, _sim_inner_ms), sim_ms, sim_mem_kb = _timed_with_memory(
        retrieve_simhash, query, top_k
    )
    approx_chunks = _hybrid_approximate(lsh_chunks, sim_chunks, top_k)

    # Path B (exact baseline): TF-IDF + cosine similarity
    (tfidf_chunks, _tfidf_inner_ms), tfidf_ms, tfidf_mem_kb = _timed_with_memory(
        retrieve_tfidf, query, top_k
    )

    # Final answer path (for UI): exact baseline by default
    # TF-IDF is preferred for generation because its scores are more calibrated
    selected_method = "exact_tfidf"
    selected_chunks = tfidf_chunks

    # Overlap metrics give a quick proxy for how much the two paths agree
    comparison = _overlap_metrics(approx_chunks, tfidf_chunks)

    return {
        "question": query,
        "approximate": {
            "method": "lsh_hybrid_minhash_simhash",
            "chunks": approx_chunks,
            # Sum the two approximate method times for a combined latency figure
            "time_ms": round(lsh_ms + sim_ms, 2),
            "memory_kb": round(lsh_mem_kb + sim_mem_kb, 2),
            "components": {
                "lsh": {
                    "chunks": lsh_chunks,
                    "time_ms": round(lsh_ms, 2),
                    "memory_kb": round(lsh_mem_kb, 2),
                },
                "simhash": {
                    "chunks": sim_chunks,
                    "time_ms": round(sim_ms, 2),
                    "memory_kb": round(sim_mem_kb, 2),
                },
            },
        },
        "exact": {
            "method": "tfidf_cosine",
            "chunks": tfidf_chunks,
            "time_ms": round(tfidf_ms, 2),
            "memory_kb": round(tfidf_mem_kb, 2),
        },
        "comparison": comparison,
        "selected_for_generation": {
            "method": selected_method,
            "chunks": selected_chunks,
        },
        # Backward-compatible key used by other parts of the app.
        "evidence": selected_chunks,
    }
