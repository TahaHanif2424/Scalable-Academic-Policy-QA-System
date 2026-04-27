"""Compare TF-IDF (exact) vs MinHash+LSH (approximate) retrieval.

Usage examples:
  python experiments/compare_retrieval.py --chunks-file data/chunks.json --queries-file quant_queries.sample.json --top-k 5 --output results.csv

Dependencies:
  pip install scikit-learn datasketch psutil

This script expects `--chunks-file` to be a JSON list of objects with keys `id` and `text`.
`--queries-file` should be a JSON list of objects with keys `id` and `query`.

If no ground-truth relevance is available, the script treats TF-IDF top-k as the reference
and reports how well LSH recovers that set (recall@k).
"""

import argparse
import csv
import json
import os
import statistics
import time

try:
    import psutil

    _HAS_PSUTIL = True
except Exception:
    import tracemalloc

    _HAS_PSUTIL = False

from datasketch import MinHash, MinHashLSH
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel


def read_json_list(path):
    with open(path, "r", encoding="utf8") as f:
        data = json.load(f)
    return data


def tokenize_shingles(text, k=3):
    toks = text.split()
    if len(toks) < k:
        return set(toks)
    shingles = set()
    for i in range(len(toks) - k + 1):
        shingles.add(" ".join(toks[i : i + k]))
    return shingles


def build_tfidf(chunks, max_features=None):
    texts = [c["text"] for c in chunks]
    vectorizer = TfidfVectorizer(max_features=max_features)
    X = vectorizer.fit_transform(texts)
    return vectorizer, X


def build_lsh(chunks, num_perm=128, lsh_threshold=0.5):
    lsh = MinHashLSH(threshold=lsh_threshold, num_perm=num_perm)
    minhashes = {}
    for c in chunks:
        sh = tokenize_shingles(c["text"])
        m = MinHash(num_perm=num_perm)
        for s in sh:
            m.update(s.encode("utf8"))
        minhashes[c["id"]] = m
        lsh.insert(c["id"], m)
    return lsh, minhashes


def query_tfidf(vectorizer, X, query, top_k=5):
    qv = vectorizer.transform([query])
    sims = linear_kernel(qv, X).flatten()
    top_idx = sims.argsort()[::-1][:top_k]
    return top_idx, sims[top_idx]


def query_lsh_then_rank(
    lsh, minhashes, vectorizer, X, id_to_idx, chunks, query, top_k=5, num_perm=128
):
    sh = tokenize_shingles(query)
    mq = MinHash(num_perm=num_perm)
    for s in sh:
        mq.update(s.encode("utf8"))
    try:
        candidates = lsh.query(mq)
    except Exception:
        candidates = []
    # If no candidates returned, fallback to full TF-IDF (degraded behavior)
    if not candidates:
        idxs, scores = query_tfidf(vectorizer, X, query, top_k=top_k)
        ids = [chunks[i]["id"] for i in idxs]
        return ids

    cand_idxs = [id_to_idx[cid] for cid in candidates if cid in id_to_idx]
    if not cand_idxs:
        idxs, scores = query_tfidf(vectorizer, X, query, top_k=top_k)
        ids = [chunks[i]["id"] for i in idxs]
        return ids

    qv = vectorizer.transform([query])
    subX = X[cand_idxs]
    sims = linear_kernel(qv, subX).flatten()
    top_local = sims.argsort()[::-1][:top_k]
    top_ids = [candidates[i] for i in top_local if i < len(candidates)]
    return top_ids


def mem_rss():
    if _HAS_PSUTIL:
        p = psutil.Process()
        return p.memory_info().rss
    else:
        # tracemalloc provides snapshot of Python allocations
        current, peak = tracemalloc.get_traced_memory()
        return current


def human_bytes(n):
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(n) < 1024.0:
            return f"{n:3.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}TB"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks-file", required=True)
    parser.add_argument("--queries-file", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--num-perm", type=int, default=128)
    parser.add_argument("--lsh-threshold", type=float, default=0.5)
    parser.add_argument("--max-features", type=int, default=None)
    parser.add_argument("--output", default="compare_results.csv")
    args = parser.parse_args()

    if not _HAS_PSUTIL:
        tracemalloc.start()

    chunks = read_json_list(args.chunks_file)
    queries = read_json_list(args.queries_file)

    id_to_idx = {c["id"]: i for i, c in enumerate(chunks)}

    # Build TF-IDF
    t0 = time.time()
    vectorizer, X = build_tfidf(chunks, max_features=args.max_features)
    tfidf_build_time = time.time() - t0
    tfidf_mem = mem_rss()

    # Build LSH
    t0 = time.time()
    lsh, minhashes = build_lsh(
        chunks, num_perm=args.num_perm, lsh_threshold=args.lsh_threshold
    )
    lsh_build_time = time.time() - t0
    lsh_mem = mem_rss()

    # Per-query benchmarks
    tfidf_times = []
    lsh_times = []
    recalls = []
    overlaps = []

    for q in queries:
        qtext = q.get("query") or q.get("text") or q.get("q")
        if not qtext:
            continue

        # TF-IDF exact
        t0 = time.time()
        top_idx, _ = query_tfidf(vectorizer, X, qtext, top_k=args.top_k)
        tf_time = time.time() - t0
        tf_ids = [chunks[i]["id"] for i in top_idx]

        # LSH approximate
        t0 = time.time()
        lsh_ids = query_lsh_then_rank(
            lsh,
            minhashes,
            vectorizer,
            X,
            id_to_idx,
            chunks,
            qtext,
            top_k=args.top_k,
            num_perm=args.num_perm,
        )
        lsh_time = time.time() - t0

        tfidf_times.append(tf_time)
        lsh_times.append(lsh_time)

        # If no ground truth provided, treat TF-IDF top-k as reference
        gt = set(tf_ids)
        found = set(lsh_ids)
        recall = len(gt & found) / float(args.top_k)
        overlap = (
            len(gt & found) / float(len(gt.union(found))) if gt.union(found) else 0.0
        )
        recalls.append(recall)
        overlaps.append(overlap)

    results = {
        "tfidf_build_time_s": tfidf_build_time,
        "lsh_build_time_s": lsh_build_time,
        "tfidf_index_rss": tfidf_mem,
        "lsh_index_rss": lsh_mem,
        "queries": len(queries),
        "tfidf_avg_query_s": statistics.mean(tfidf_times) if tfidf_times else 0.0,
        "lsh_avg_query_s": statistics.mean(lsh_times) if lsh_times else 0.0,
        "recall_at_k_mean": statistics.mean(recalls) if recalls else 0.0,
        "overlap_mean": statistics.mean(overlaps) if overlaps else 0.0,
    }

    # Print summary
    print("\n=== Retrieval Comparison Summary ===")
    print(f"TF-IDF build time: {results['tfidf_build_time_s']:.3f}s")
    print(f"LSH build time: {results['lsh_build_time_s']:.3f}s")
    print(f"TF-IDF index RSS: {human_bytes(results['tfidf_index_rss'])}")
    print(f"LSH index RSS: {human_bytes(results['lsh_index_rss'])}")
    print(f"Queries evaluated: {results['queries']}")
    print(f"TF-IDF avg query time: {results['tfidf_avg_query_s'] * 1000:.2f} ms")
    print(f"LSH avg query time: {results['lsh_avg_query_s'] * 1000:.2f} ms")
    print(f"Mean recall@{args.top_k}: {results['recall_at_k_mean']:.3f}")
    print(f"Mean overlap: {results['overlap_mean']:.3f}")

    # Save CSV summary
    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    with open(args.output, "w", newline="", encoding="utf8") as csvf:
        writer = csv.writer(csvf)
        writer.writerow(["metric", "value"])
        for k, v in results.items():
            writer.writerow([k, v])

    print(f"\nResults written to {args.output}")


if __name__ == "__main__":
    main()
