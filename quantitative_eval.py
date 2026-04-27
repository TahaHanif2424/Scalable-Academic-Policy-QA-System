import argparse
import csv
import json
import mimetypes
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request

DEFAULT_SERVER_URL = "http://localhost:8000/process"
DEFAULT_TOP_K = 5
DEFAULT_TIMEOUT = 120
DEFAULT_OUTPUT_DIR = Path("reports")


@dataclass
class QueryItem:
    question: str
    relevant_chunk_ids: list[int]


def _encode_multipart(
    fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]
) -> tuple[bytes, str]:
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    parts: list[bytes] = []

    for name, value in fields.items():
        parts.append(f"--{boundary}".encode("utf-8"))
        parts.append(f'Content-Disposition: form-data; name="{name}"'.encode("utf-8"))
        parts.append(b"")
        parts.append(str(value).encode("utf-8"))

    for name, (filename, content, content_type) in files.items():
        parts.append(f"--{boundary}".encode("utf-8"))
        parts.append(
            (
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'
            ).encode("utf-8")
        )
        parts.append(f"Content-Type: {content_type}".encode("utf-8"))
        parts.append(b"")
        parts.append(content)

    parts.append(f"--{boundary}--".encode("utf-8"))
    body = b"\r\n".join(parts) + b"\r\n"
    return body, f"multipart/form-data; boundary={boundary}"


def _post_process(
    server_url: str,
    question: str,
    top_k: int,
    timeout: int,
    pdf_path: Path | None = None,
) -> tuple[dict[str, Any], float]:
    fields = {"question": question, "top_k": str(top_k)}
    files: dict[str, tuple[str, bytes, str]] = {}

    if pdf_path is not None:
        content_type = mimetypes.guess_type(str(pdf_path))[0] or "application/pdf"
        files["file"] = (pdf_path.name, pdf_path.read_bytes(), content_type)

    body, content_type_header = _encode_multipart(fields, files)

    req = request.Request(url=server_url, data=body, method="POST")
    req.add_header("Content-Type", content_type_header)

    started = time.perf_counter()
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            latency_ms = (time.perf_counter() - started) * 1000.0
            return json.loads(raw), latency_ms
    except error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {payload}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}") from exc


def _load_queries(path: Path) -> list[QueryItem]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("queries file must be a JSON list")

    queries: list[QueryItem] = []
    for i, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"entry {i} must be an object")

        question = str(item.get("question", "")).strip()
        if not question:
            raise ValueError(f"entry {i} is missing question")

        rel_ids_raw = item.get("relevant_chunk_ids", [])
        if rel_ids_raw is None:
            rel_ids_raw = []
        if not isinstance(rel_ids_raw, list):
            raise ValueError(f"entry {i} has invalid relevant_chunk_ids")

        rel_ids: list[int] = []
        for rid in rel_ids_raw:
            try:
                rel_ids.append(int(rid))
            except (TypeError, ValueError):
                raise ValueError(f"entry {i} contains non-integer chunk id: {rid}")

        queries.append(QueryItem(question=question, relevant_chunk_ids=rel_ids))

    return queries


def _extract_chunk_ids(chunks: list[dict], top_k: int) -> list[int]:
    ids: list[int] = []
    for c in chunks[:top_k]:
        cid = c.get("chunk_id")
        if isinstance(cid, int):
            ids.append(cid)
    return ids


def _precision_at_k(
    retrieved_ids: list[int], relevant_set: set[int], k: int
) -> float | None:
    if not relevant_set:
        return None
    if k <= 0:
        return None
    hits = len(set(retrieved_ids[:k]) & relevant_set)
    return hits / float(k)


def _recall_at_k(
    retrieved_ids: list[int], relevant_set: set[int], k: int
) -> float | None:
    if not relevant_set:
        return None
    hits = len(set(retrieved_ids[:k]) & relevant_set)
    return hits / float(len(relevant_set)) if relevant_set else None


def _avg(values: list[float | None]) -> float | None:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return sum(valid) / float(len(valid))


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def run(args: argparse.Namespace) -> int:
    queries_path = Path(args.queries_file).resolve()
    if not queries_path.exists():
        print(f"Queries file not found: {queries_path}")
        return 1

    queries = _load_queries(queries_path)
    if not queries:
        print("No queries found.")
        return 1

    if not (10 <= len(queries) <= 15):
        print(
            f"Warning: found {len(queries)} queries. Expected 10-15 for your report requirement."
        )

    pdf_path = Path(args.pdf).resolve() if args.pdf else None
    if pdf_path is not None and not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Server: {args.server_url}")
    print(f"Queries: {len(queries)}")
    print(f"Top-k: {args.top_k}")

    rows: list[dict[str, Any]] = []

    for i, q in enumerate(queries, start=1):
        print("-" * 100)
        print(f"Running query {i}/{len(queries)}")
        print(q.question)

        query_pdf = pdf_path if (i == 1 and pdf_path is not None) else None

        try:
            response, end_to_end_latency = _post_process(
                server_url=args.server_url,
                question=q.question,
                top_k=args.top_k,
                timeout=args.timeout,
                pdf_path=query_pdf,
            )
        except Exception as exc:
            print(f"Failed: {exc}")
            rows.append(
                {
                    "query_index": i,
                    "question": q.question,
                    "error": str(exc),
                }
            )
            continue

        retrieval = response.get("retrieval", {})

        tfidf = response.get("tfidf", retrieval.get("exact", {}))
        simhash = response.get(
            "simhash",
            retrieval.get("approximate", {}).get("components", {}).get("simhash", {}),
        )
        lsh_minhash = response.get(
            "lsh_minhash",
            retrieval.get("approximate", {}).get("components", {}).get("lsh", {}),
        )

        tfidf_chunks = tfidf.get("chunks", []) if isinstance(tfidf, dict) else []
        simhash_chunks = simhash.get("chunks", []) if isinstance(simhash, dict) else []
        lsh_chunks = (
            lsh_minhash.get("chunks", []) if isinstance(lsh_minhash, dict) else []
        )

        relevant_set = set(q.relevant_chunk_ids)

        tfidf_ids = _extract_chunk_ids(tfidf_chunks, args.top_k)
        simhash_ids = _extract_chunk_ids(simhash_chunks, args.top_k)
        lsh_ids = _extract_chunk_ids(lsh_chunks, args.top_k)

        p_tfidf = _precision_at_k(tfidf_ids, relevant_set, args.top_k)
        r_tfidf = _recall_at_k(tfidf_ids, relevant_set, args.top_k)
        p_simhash = _precision_at_k(simhash_ids, relevant_set, args.top_k)
        r_simhash = _recall_at_k(simhash_ids, relevant_set, args.top_k)
        p_lsh = _precision_at_k(lsh_ids, relevant_set, args.top_k)
        r_lsh = _recall_at_k(lsh_ids, relevant_set, args.top_k)

        tfidf_latency = tfidf.get("time_ms") if isinstance(tfidf, dict) else None
        simhash_latency = simhash.get("time_ms") if isinstance(simhash, dict) else None
        lsh_latency = (
            lsh_minhash.get("time_ms") if isinstance(lsh_minhash, dict) else None
        )

        print(
            "Precision@k / Recall@k | "
            f"TF-IDF: {_fmt(p_tfidf)} / {_fmt(r_tfidf)} | "
            f"SimHash: {_fmt(p_simhash)} / {_fmt(r_simhash)} | "
            f"LSH+MinHash: {_fmt(p_lsh)} / {_fmt(r_lsh)}"
        )
        print(
            "Latency (ms) | "
            f"end_to_end={end_to_end_latency:.2f}, "
            f"tfidf={tfidf_latency}, simhash={simhash_latency}, lsh_minhash={lsh_latency}"
        )

        rows.append(
            {
                "query_index": i,
                "question": q.question,
                "relevant_chunk_ids": q.relevant_chunk_ids,
                "precision_at_k_tfidf": p_tfidf,
                "recall_at_k_tfidf": r_tfidf,
                "precision_at_k_simhash": p_simhash,
                "recall_at_k_simhash": r_simhash,
                "precision_at_k_lsh_minhash": p_lsh,
                "recall_at_k_lsh_minhash": r_lsh,
                "latency_ms_end_to_end": end_to_end_latency,
                "latency_ms_tfidf": tfidf_latency,
                "latency_ms_simhash": simhash_latency,
                "latency_ms_lsh_minhash": lsh_latency,
                "selected_method": retrieval.get("selected_method", ""),
            }
        )

    metric_rows = [r for r in rows if "error" not in r]

    summary = {
        "query_count": len(queries),
        "successful_queries": len(metric_rows),
        "k": args.top_k,
        "avg_precision_at_k_tfidf": _avg(
            [r.get("precision_at_k_tfidf") for r in metric_rows]
        ),
        "avg_recall_at_k_tfidf": _avg(
            [r.get("recall_at_k_tfidf") for r in metric_rows]
        ),
        "avg_precision_at_k_simhash": _avg(
            [r.get("precision_at_k_simhash") for r in metric_rows]
        ),
        "avg_recall_at_k_simhash": _avg(
            [r.get("recall_at_k_simhash") for r in metric_rows]
        ),
        "avg_precision_at_k_lsh_minhash": _avg(
            [r.get("precision_at_k_lsh_minhash") for r in metric_rows]
        ),
        "avg_recall_at_k_lsh_minhash": _avg(
            [r.get("recall_at_k_lsh_minhash") for r in metric_rows]
        ),
        "avg_latency_ms_end_to_end": _avg(
            [r.get("latency_ms_end_to_end") for r in metric_rows]
        ),
        "avg_latency_ms_tfidf": _avg([r.get("latency_ms_tfidf") for r in metric_rows]),
        "avg_latency_ms_simhash": _avg(
            [r.get("latency_ms_simhash") for r in metric_rows]
        ),
        "avg_latency_ms_lsh_minhash": _avg(
            [r.get("latency_ms_lsh_minhash") for r in metric_rows]
        ),
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"quantitative_eval_{timestamp}.json"
    csv_path = output_dir / f"quantitative_eval_{timestamp}.csv"

    json_path.write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "query_index",
            "question",
            "precision_at_k_tfidf",
            "recall_at_k_tfidf",
            "precision_at_k_simhash",
            "recall_at_k_simhash",
            "precision_at_k_lsh_minhash",
            "recall_at_k_lsh_minhash",
            "latency_ms_end_to_end",
            "latency_ms_tfidf",
            "latency_ms_simhash",
            "latency_ms_lsh_minhash",
            "selected_method",
            "error",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    print("=" * 100)
    print("Summary")
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"- {k}: {v:.4f}")
        else:
            print(f"- {k}: {v}")
    print(f"Saved JSON: {json_path}")
    print(f"Saved CSV:  {csv_path}")

    if summary["avg_precision_at_k_tfidf"] is None:
        print(
            "Note: Precision@k and Recall@k are n/a because relevant_chunk_ids were not provided."
        )

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Quantitative evaluation: Precision@k / Recall@k and query latency"
    )
    parser.add_argument("--queries-file", required=True, help="Path to JSON query file")
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL)
    parser.add_argument("--pdf", default="", help="PDF path for the first query")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
