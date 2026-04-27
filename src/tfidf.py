import os
import pickle
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from src.database import get_all_chunks, get_chunks_by_ids
except ModuleNotFoundError:
    from database import get_all_chunks, get_chunks_by_ids

# ─── Configuration ────────────────────────────────────────────────────────────
INDEX_PATH = "index/tfidf_index.pkl"  # where we save the fitted vectorizer
TOP_K_DEFAULT = 5
MIN_SCORE = 0.05  # discard chunks with cosine similarity below this
TFIDF_CANDIDATE_K = 20
GRAPH_ALPHA = 0.7
GRAPH_SIM_THRESHOLD = 0.1
GRAPH_MAX_ITERS = 30
GRAPH_TOL = 1e-6


def _graph_rerank(seed_scores: list[float], candidate_matrix) -> list[float]:
    """
    Build a chunk similarity graph over TF-IDF candidates and propagate relevance.
    This smooths local score noise and promotes chunks central to related evidence.
    """
    # Run lightweight graph propagation over candidate similarities.
    n = len(seed_scores)
    if n <= 1:
        return seed_scores

    seed = np.asarray(seed_scores, dtype=np.float64)
    seed_max = seed.max()
    if seed_max > 0:
        seed = seed / seed_max

    sim = cosine_similarity(candidate_matrix, candidate_matrix)
    np.fill_diagonal(sim, 0.0)
    sim[sim < GRAPH_SIM_THRESHOLD] = 0.0

    row_sums = sim.sum(axis=1, keepdims=True)
    transition = np.divide(sim, row_sums, out=np.zeros_like(sim), where=row_sums != 0)

    rank = seed.copy()
    for _ in range(GRAPH_MAX_ITERS):
        updated = GRAPH_ALPHA * seed + (1.0 - GRAPH_ALPHA) * (transition @ rank)
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
        sublinear_tf=True,
        max_df=0.85,
        min_df=2,
        ngram_range=(1, 2),
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

    query_vector = vectorizer.transform([query_text])

    scores = cosine_similarity(query_vector, matrix).flatten()

    scored = [
        {"index": i, "chunk_id": chunk_ids[i], "tfidf_score": float(scores[i])}
        for i in range(len(chunk_ids))
        if scores[i] >= MIN_SCORE
    ]
    scored.sort(key=lambda x: x["tfidf_score"], reverse=True)

    candidate_k = max(top_k, TFIDF_CANDIDATE_K)
    candidates = scored[:candidate_k]
    if not candidates:
        return []

    candidate_indices = [item["index"] for item in candidates]
    candidate_matrix = matrix[candidate_indices]
    seed_scores = [item["tfidf_score"] for item in candidates]

    graph_scores = _graph_rerank(seed_scores, candidate_matrix)

    seed_arr = np.asarray(seed_scores, dtype=np.float64)
    graph_arr = np.asarray(graph_scores, dtype=np.float64)

    if seed_arr.max() > 0:
        seed_arr = seed_arr / seed_arr.max()
    if graph_arr.max() > 0:
        graph_arr = graph_arr / graph_arr.max()

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
