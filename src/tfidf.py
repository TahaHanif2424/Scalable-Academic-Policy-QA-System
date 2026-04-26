import os
import pickle
import time

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


# ─── Step 1: Build TF-IDF index ───────────────────────────────────────────────
def build_tfidf_index():
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

    index = load_tfidf_index()
    if index is None:
        return []

    vectorizer = index["vectorizer"]
    matrix = index["matrix"]
    chunk_ids = index["chunk_ids"]

    query_vector = vectorizer.transform([query_text])

    scores = cosine_similarity(query_vector, matrix).flatten()

    scored = [
        {"chunk_id": chunk_ids[i], "score": float(scores[i])}
        for i in range(len(chunk_ids))
        if scores[i] >= MIN_SCORE
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)

    return scored[:top_k]


# ─── Step 4: Get top-k chunks with full text ─────────────────────────────────
def query_tfidf_with_text(query_text: str, top_k: int = TOP_K_DEFAULT) -> list[dict]:

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
