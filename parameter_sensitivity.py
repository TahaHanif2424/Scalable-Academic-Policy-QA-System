import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from time import perf_counter

from src.database import get_chunk_count, init_db
from src.minhash import build_minhash_index
from src.query_processor import retrieve_lsh, retrieve_simhash, retrieve_tfidf
from src.simhash import build_simhash_index

DEFAULT_TOP_K = 5
DEFAULT_OUTPUT_DIR = Path("reports")


def load_queries(path: Path | None) -> list[str]:
    if path is None:
        return [
            "How many times can a course be repeated?",
            "What is the minimum CGPA required for graduation?",
            "What is the attendance requirement for appearing in final exams?",
            "What happens if a student gets an F grade in a core course?",
            "Can a student improve a grade after passing a course?",
            "What are the credit hour limits per semester?",
            "What is the policy for probation and dismissal?",
            "How is semester GPA calculated?",
            "What is the process for course withdrawal?",
            "Is there a policy for transfer of credits from another university?",
            "What is the policy on plagiarism or academic misconduct?",
            "Can a final exam be retaken if missed due to medical reasons?",
        ]

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("queries file must be a JSON list")

    queries = []
    for entry in raw:
        if isinstance(entry, str):
            q = entry.strip()
        elif isinstance(entry, dict):
            q = str(entry.get("question", "")).strip()
        else:
            q = ""
        if q:
            queries.append(q)

    if not queries:
        raise ValueError("no valid queries found")

    return queries


def jaccard_at_k(a: list[int], b: list[int]) -> float:
    sa = set(a)
    sb = set(b)
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def overlap_at_k(a: list[int], b: list[int], k: int) -> float:
    if k <= 0:
        return 0.0
    return len(set(a) & set(b)) / float(k)


def extract_ids(chunks: list[dict], top_k: int) -> list[int]:
    return [
        c.get("chunk_id") for c in chunks[:top_k] if isinstance(c.get("chunk_id"), int)
    ]


def evaluate_setting(
    queries: list[str],
    top_k: int,
    num_hash_functions: int,
    num_bands: int,
    hamming_threshold: int,
) -> dict:
    import src.minhash as minhash_module
    import src.simhash as simhash_module

    if num_hash_functions <= 0 or num_bands <= 0:
        raise ValueError("num_hash_functions and num_bands must be positive")
    if num_hash_functions % num_bands != 0:
        raise ValueError("num_hash_functions must be divisible by num_bands")

    # Apply runtime config for this experiment.
    minhash_module.NUM_HASH_FUNCTIONS = num_hash_functions
    minhash_module.NUM_BANDS = num_bands
    minhash_module.ROWS_PER_BAND = num_hash_functions // num_bands
    simhash_module.HAMMING_THRESHOLD = hamming_threshold

    idx_start = perf_counter()
    build_minhash_index()
    build_simhash_index()
    index_build_ms = (perf_counter() - idx_start) * 1000.0

    lsh_latencies = []
    sim_latencies = []
    tfidf_latencies = []

    lsh_overlap = []
    sim_overlap = []
    lsh_jaccard = []
    sim_jaccard = []

    for q in queries:
        lsh_chunks, lsh_ms = retrieve_lsh(q, top_k)
        sim_chunks, sim_ms = retrieve_simhash(q, top_k)
        tfidf_chunks, tfidf_ms = retrieve_tfidf(q, top_k)

        lsh_latencies.append(lsh_ms)
        sim_latencies.append(sim_ms)
        tfidf_latencies.append(tfidf_ms)

        lsh_ids = extract_ids(lsh_chunks, top_k)
        sim_ids = extract_ids(sim_chunks, top_k)
        tfidf_ids = extract_ids(tfidf_chunks, top_k)

        lsh_overlap.append(overlap_at_k(lsh_ids, tfidf_ids, top_k))
        sim_overlap.append(overlap_at_k(sim_ids, tfidf_ids, top_k))
        lsh_jaccard.append(jaccard_at_k(lsh_ids, tfidf_ids))
        sim_jaccard.append(jaccard_at_k(sim_ids, tfidf_ids))

    return {
        "num_hash_functions": num_hash_functions,
        "num_bands": num_bands,
        "rows_per_band": num_hash_functions // num_bands,
        "hamming_threshold": hamming_threshold,
        "query_count": len(queries),
        "top_k": top_k,
        "index_build_ms": round(index_build_ms, 2),
        "avg_lsh_latency_ms": round(mean(lsh_latencies), 2),
        "avg_simhash_latency_ms": round(mean(sim_latencies), 2),
        "avg_tfidf_latency_ms": round(mean(tfidf_latencies), 2),
        "avg_lsh_overlap_vs_tfidf_at_k": round(mean(lsh_overlap), 4),
        "avg_simhash_overlap_vs_tfidf_at_k": round(mean(sim_overlap), 4),
        "avg_lsh_jaccard_vs_tfidf_at_k": round(mean(lsh_jaccard), 4),
        "avg_simhash_jaccard_vs_tfidf_at_k": round(mean(sim_jaccard), 4),
    }


def parse_sweep(values: str, cast_type=int) -> list[int]:
    parts = [p.strip() for p in values.split(",") if p.strip()]
    if not parts:
        raise ValueError("empty sweep values")
    return [cast_type(p) for p in parts]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parameter sensitivity analysis for MinHash/LSH/SimHash"
    )
    parser.add_argument("--queries-file", default="", help="JSON file with questions")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument(
        "--num-hash-functions",
        default="64,128,256",
        help="Comma-separated sweep values for MinHash hash count",
    )
    parser.add_argument(
        "--num-bands",
        default="16,32,64",
        help="Comma-separated sweep values for LSH bands",
    )
    parser.add_argument(
        "--hamming-thresholds",
        default="3,5,8",
        help="Comma-separated sweep values for SimHash threshold",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    init_db()
    if get_chunk_count() <= 0:
        raise SystemExit(
            "No chunks found in DB. Run your ingestion first by calling /process with a PDF."
        )

    queries_file = Path(args.queries_file) if args.queries_file else None
    queries = load_queries(queries_file)

    hash_values = parse_sweep(args.num_hash_functions)
    band_values = parse_sweep(args.num_bands)
    threshold_values = parse_sweep(args.hamming_thresholds)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for n_hash in hash_values:
        for n_bands in band_values:
            if n_hash % n_bands != 0:
                print(
                    f"Skipping invalid combo n_hash={n_hash}, n_bands={n_bands} "
                    "(must divide evenly)."
                )
                continue
            for ham in threshold_values:
                print(
                    f"Running setting: hash_functions={n_hash}, "
                    f"bands={n_bands}, hamming_threshold={ham}"
                )
                result = evaluate_setting(
                    queries=queries,
                    top_k=args.top_k,
                    num_hash_functions=n_hash,
                    num_bands=n_bands,
                    hamming_threshold=ham,
                )
                results.append(result)

    if not results:
        raise SystemExit("No valid parameter combinations were evaluated.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"parameter_sensitivity_{timestamp}.json"
    csv_path = output_dir / f"parameter_sensitivity_{timestamp}.csv"

    payload = {
        "metadata": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "query_count": len(queries),
            "top_k": args.top_k,
            "hash_sweep": hash_values,
            "band_sweep": band_values,
            "hamming_threshold_sweep": threshold_values,
        },
        "results": results,
    }
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8"
    )

    fieldnames = [
        "num_hash_functions",
        "num_bands",
        "rows_per_band",
        "hamming_threshold",
        "query_count",
        "top_k",
        "index_build_ms",
        "avg_lsh_latency_ms",
        "avg_simhash_latency_ms",
        "avg_tfidf_latency_ms",
        "avg_lsh_overlap_vs_tfidf_at_k",
        "avg_simhash_overlap_vs_tfidf_at_k",
        "avg_lsh_jaccard_vs_tfidf_at_k",
        "avg_simhash_jaccard_vs_tfidf_at_k",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("\nSensitivity analysis complete")
    print(f"Saved JSON: {json_path}")
    print(f"Saved CSV:  {csv_path}")

    best_lsh = max(results, key=lambda r: r["avg_lsh_overlap_vs_tfidf_at_k"])
    best_sim = max(results, key=lambda r: r["avg_simhash_overlap_vs_tfidf_at_k"])
    fastest_lsh = min(results, key=lambda r: r["avg_lsh_latency_ms"])
    fastest_sim = min(results, key=lambda r: r["avg_simhash_latency_ms"])

    print("\nQuick takeaways")
    print(
        "- Best LSH overlap vs TF-IDF: "
        f"hash={best_lsh['num_hash_functions']}, bands={best_lsh['num_bands']}, "
        f"ham={best_lsh['hamming_threshold']}, "
        f"overlap@k={best_lsh['avg_lsh_overlap_vs_tfidf_at_k']}"
    )
    print(
        "- Best SimHash overlap vs TF-IDF: "
        f"hash={best_sim['num_hash_functions']}, bands={best_sim['num_bands']}, "
        f"ham={best_sim['hamming_threshold']}, "
        f"overlap@k={best_sim['avg_simhash_overlap_vs_tfidf_at_k']}"
    )
    print(
        "- Fastest LSH latency: "
        f"hash={fastest_lsh['num_hash_functions']}, bands={fastest_lsh['num_bands']}, "
        f"ham={fastest_lsh['hamming_threshold']}, "
        f"latency_ms={fastest_lsh['avg_lsh_latency_ms']}"
    )
    print(
        "- Fastest SimHash latency: "
        f"hash={fastest_sim['num_hash_functions']}, bands={fastest_sim['num_bands']}, "
        f"ham={fastest_sim['hamming_threshold']}, "
        f"latency_ms={fastest_sim['avg_simhash_latency_ms']}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
