import os
import pickle
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from src.database import get_all_chunks, get_chunks_by_ids
except ModuleNotFoundError:
    # Fall back to a flat import when running outside the src package context
    from database import get_all_chunks, get_chunks_by_ids

# ─── Configuration ────────────────────────────────────────────────────────────
INDEX_PATH = "index/tfidf_index.pkl"  # where we save the fitted vectorizer
TOP_K_DEFAULT = 5
MIN_SCORE = 0.05  # discard chunks with cosine similarity below this
TFIDF_CANDIDATE_K = 20  # over-fetch before reranking to give the graph enough candidates
GRAPH_ALPHA = 0.7  # interpolation weight: higher = trust seed scores more than graph
GRAPH_SIM_THRESHOLD = 0.1  # zero out weak inter-chunk edges to keep the graph sparse
GRAPH_MAX_ITERS = 30  # cap iterations to bound runtime if convergence is slow
GRAPH_TOL = 1e-6  # L1 norm change below which we consider the scores converged


def _graph_rerank(seed_scores: list[float], candidate_matrix) -> list[float]:
    """
    Build a chunk similarity graph over TF-IDF candidates and propagate relevance.
    This smooths local score noise and promotes chunks central to related evidence.
    """
    # Run lightweight graph propagation over candidate similarities.
    n = len(seed_scores)

    # A single candidate has no neighbors to propagate through — return as-is
    if n <= 1:
        return seed_scores

    # Normalize seed scores to [0, 1] so alpha blending is scale-invariant
    seed = np.asarray(seed_scores, dtype=np.float64)
    seed_max = seed.max()
    if seed_max > 0:
        seed = seed / seed_max

    # Build a full pairwise cosine similarity matrix between candidate chunk vectors
    sim = cosine_similarity(candidate_matrix, candidate_matrix)

    # Self-similarity is always 1 but meaningless for propagation — zero it out
    np.fill_diagonal(sim, 0.0)

    # Prune weak edges to prevent noise from diffusing across unrelated chunks
    sim[sim < GRAPH_SIM_THRESHOLD] = 0.0

    # Row-normalize to form a proper stochastic transition matrix;
    # rows that sum to zero (isolated nodes) stay zero via the `where` guard
    row_sums = sim.sum(axis=1, keepdims=True)
    transition = np.divide(sim, row_sums, out=np.zeros_like(sim), where=row_sums != 0)

    # Iterative propagation: blend the original seed signal with neighbor-smoothed scores
    rank = seed.copy()
    for _ in range(GRAPH_MAX_ITERS):
        updated = GRAPH_ALPHA * seed + (1.0 - GRAPH_ALPHA) * (transition @ rank)

        # Early exit when the scores have stabilized within tolerance
        if np.linalg.norm(updated - rank, ord=1) < GRAPH_TOL:
            rank = updated
            break
        rank = updated

    return rank.tolist()


# ─── Step 1: Build TF-IDF index ───────────────────────────────────────────────
def build_tfidf_index():
    # Fit and persist TF-IDF vectorizer/matrix for all chunks.
    print("[tfidf] Starting TF-IDF index build...")

    chunks = get_all_chunks()
    if not chunks:
        print("[tfidf] No chunks found. Run ingestion first.")
        return

    print(f"[tfidf] Processing {len(chunks)} chunks...")

    texts = [chunk["text"] for chunk in chunks]
    chunk_ids = [chunk["chunk_id"] for chunk in chunks]

    vectorizer = TfidfVectorizer(
        sublinear_tf=True,    # apply log(1+tf) to compress high-frequency term dominance
        max_df=0.85,          # ignore terms appearing in >85% of chunks (too common)
        min_df=2,             # ignore terms appearing in fewer than 2 chunks (too rare)
        ngram_range=(1, 2),   # include both unigrams and bigrams for phrase sensitivity
        stop_words="english",
    )

    start = time.time()
    matrix = vectorizer.fit_transform(texts)
    elapsed = (time.time() - start) * 1000

    print(f"[tfidf] Vectorized {len(texts)} chunks in {elapsed:.1f}ms")
    print(f"[tfidf] Vocabulary size: {len(vectorizer.vocabulary_)}")
    print(f"[tfidf] Matrix shape: {matrix.shape}")

    # save index to disk
    os.makedirs("index", exist_ok=True)
    index = {"vectorizer": vectorizer, "matrix": matrix, "chunk_ids": chunk_ids}
    with open(INDEX_PATH, "wb") as f:
        pickle.dump(index, f)

    print(f"[tfidf] Index saved to {INDEX_PATH}")


# ─── Step 2: Load TF-IDF index from disk ─────────────────────────────────────
def load_tfidf_index() -> dict:
    # Load the saved TF-IDF index bundle from disk.

    if not os.path.exists(INDEX_PATH):
        print(
            f"[tfidf] Index not found at {INDEX_PATH}. Run build_tfidf_index() first."
        )
        return None

    with open(INDEX_PATH, "rb") as f:
        index = pickle.load(f)

    return index


# ─── Step 3: Query ───────────────────────────────────────────────────────────
def query_tfidf(query_text: str, top_k: int = TOP_K_DEFAULT) -> list[dict]:
    # Score chunks by TF-IDF cosine and rerank with graph smoothing.

    index = load_tfidf_index()
    if index is None:
        return []

    vectorizer = index["vectorizer"]
    matrix = index["matrix"]
    chunk_ids = index["chunk_ids"]

    # Project the query into the same TF-IDF space as the indexed chunks
    query_vector = vectorizer.transform([query_text])

    # Compute cosine similarity between the query vector and every chunk vector
    scores = cosine_similarity(query_vector, matrix).flatten()

    # Filter out low-scoring chunks and attach their matrix row index for later slicing
    scored = [
        {"index": i, "chunk_id": chunk_ids[i], "tfidf_score": float(scores[i])}
        for i in range(len(chunk_ids))
        if scores[i] >= MIN_SCORE
    ]
    scored.sort(key=lambda x: x["tfidf_score"], reverse=True)

    # Over-fetch so the graph reranker has a richer neighborhood to work with
    candidate_k = max(top_k, TFIDF_CANDIDATE_K)
    candidates = scored[:candidate_k]
    if not candidates:
        return []

    # Extract the sparse matrix rows for just the candidates to keep reranking fast
    candidate_indices = [item["index"] for item in candidates]
    candidate_matrix = matrix[candidate_indices]
    seed_scores = [item["tfidf_score"] for item in candidates]

    # Propagate relevance through the inter-chunk similarity graph
    graph_scores = _graph_rerank(seed_scores, candidate_matrix)

    # Normalize both score arrays independently before blending so neither dominates
    seed_arr = np.asarray(seed_scores, dtype=np.float64)
    graph_arr = np.asarray(graph_scores, dtype=np.float64)

    if seed_arr.max() > 0:
        seed_arr = seed_arr / seed_arr.max()
    if graph_arr.max() > 0:
        graph_arr = graph_arr / graph_arr.max()

    # Weighted combination: graph score gets slightly more weight (0.55) than raw TF-IDF
    combined = 0.45 * seed_arr + 0.55 * graph_arr

    reranked = []
    for i, item in enumerate(candidates):
        reranked.append(
            {
                "chunk_id": item["chunk_id"],
                "score": float(combined[i]),
                "tfidf_score": float(item["tfidf_score"]),
                "graph_score": float(graph_scores[i]),
            }
        )

    reranked.sort(key=lambda x: x["score"], reverse=True)

    return reranked[:top_k]


# ─── Step 4: Get top-k chunks with full text ─────────────────────────────────
def query_tfidf_with_text(query_text: str, top_k: int = TOP_K_DEFAULT) -> list[dict]:
    # Fetch full chunk payloads for top TF-IDF results.

    results = query_tfidf(query_text, top_k)
    chunk_ids = [r["chunk_id"] for r in results]
    chunks = get_chunks_by_ids(chunk_ids)

    # merge score into chunk dict
    score_map = {r["chunk_id"]: r["score"] for r in results}
    for chunk in chunks:
        chunk["score"] = score_map.get(chunk["chunk_id"], 0.0)

    # sort by score again (MongoDB does not preserve order)
    chunks.sort(key=lambda x: x["score"], reverse=True)
    return chunks


# ─── Step 5: Get top keywords from TF-IDF for a chunk ────────────────────────
def get_top_keywords(chunk_text: str, top_n: int = 10) -> list[tuple[str, float]]:
    # Extract highest-weight TF-IDF terms for one chunk.

    index = load_tfidf_index()
    if index is None:
        return []

    vectorizer = index["vectorizer"]
    vector = vectorizer.transform([chunk_text])
    feature_names = vectorizer.get_feature_names_out()

    # get non-zero scores
    scores = vector.toarray().flatten()
    pairs = [(feature_names[i], scores[i]) for i in range(len(scores)) if scores[i] > 0]
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs[:top_n]
