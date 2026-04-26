import os
import sys
import time

# ── allow both `python -m src.query_processor` (root) and
#    `python query_processor.py` (from inside src/)  ──────────────────────────
if __name__ == "__main__" and __package__ is None:
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
    if not results:
        return []

    chunk_ids = [r["chunk_id"] for r in results]
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
                "score": r.get("score") or r.get("similarity") or 0.0,
            }
        )
    return enriched


def _timed(fn, *args, **kwargs):
    """Run fn(*args, **kwargs), return (result, elapsed_ms)."""
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, (time.perf_counter() - t0) * 1000


# ─── public API ──────────────────────────────────────────────────────────────


def retrieve_lsh(query: str, top_k: int = 5) -> tuple[list[dict], float]:
    """
    LSH/MinHash retrieval.
    Returns (enriched_chunks, elapsed_ms).
    """
    raw, ms = _timed(query_minhash, query, top_k)
    return _enrich(raw, "lsh"), ms


def retrieve_simhash(query: str, top_k: int = 5) -> tuple[list[dict], float]:
    """
    SimHash retrieval.
    Returns (enriched_chunks, elapsed_ms).
    """
    raw, ms = _timed(query_simhash, query, top_k)
    return _enrich(raw, "simhash"), ms


def retrieve_tfidf(query: str, top_k: int = 5) -> tuple[list[dict], float]:
    """
    TF-IDF (baseline) retrieval.
    Returns (enriched_chunks, elapsed_ms).
    """
    raw, ms = _timed(query_tfidf, query, top_k)
    return _enrich(raw, "tfidf"), ms


def retrieve_all(query: str, top_k: int = 5) -> dict:

    lsh_chunks, lsh_ms = retrieve_lsh(query, top_k)
    sim_chunks, sim_ms = retrieve_simhash(query, top_k)
    tfidf_chunks, tfidf_ms = retrieve_tfidf(query, top_k)

    # ── deduplicate across methods: keep highest score per chunk_id ───────────
    seen: dict[int, dict] = {}
    for chunk in lsh_chunks + sim_chunks + tfidf_chunks:
        cid = chunk["chunk_id"]
        if cid not in seen or chunk["score"] > seen[cid]["score"]:
            seen[cid] = chunk

    evidence = sorted(seen.values(), key=lambda x: x["score"], reverse=True)

    return {
        "question": query,
        "lsh": {"chunks": lsh_chunks, "time_ms": round(lsh_ms, 2)},
        "simhash": {"chunks": sim_chunks, "time_ms": round(sim_ms, 2)},
        "tfidf": {"chunks": tfidf_chunks, "time_ms": round(tfidf_ms, 2)},
        "evidence": evidence,
    }
