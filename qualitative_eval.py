import argparse
import csv
import json
import mimetypes
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

DEFAULT_QUERIES = [
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


@dataclass
class QueryItem:
    question: str
    expected: str = ""


def _encode_multipart(
    fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]
) -> tuple[bytes, str]:
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    lines: list[bytes] = []

    for name, value in fields.items():
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{name}"'.encode("utf-8"))
        lines.append(b"")
        lines.append(str(value).encode("utf-8"))

    for name, (filename, content, content_type) in files.items():
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(
            (
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'
            ).encode("utf-8")
        )
        lines.append(f"Content-Type: {content_type}".encode("utf-8"))
        lines.append(b"")
        lines.append(content)

    lines.append(f"--{boundary}--".encode("utf-8"))
    body = b"\r\n".join(lines) + b"\r\n"
    content_type_header = f"multipart/form-data; boundary={boundary}"
    return body, content_type_header


def _post_process(
    url: str,
    question: str,
    top_k: int,
    timeout: int,
    pdf_path: Path | None = None,
) -> dict[str, Any]:
    fields = {"question": question, "top_k": str(top_k)}
    files: dict[str, tuple[str, bytes, str]] = {}

    if pdf_path is not None:
        content_type = mimetypes.guess_type(str(pdf_path))[0] or "application/pdf"
        files["file"] = (pdf_path.name, pdf_path.read_bytes(), content_type)

    body, content_type_header = _encode_multipart(fields, files)

    req = request.Request(url=url, data=body, method="POST")
    req.add_header("Content-Type", content_type_header)

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {payload}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}") from exc


def _load_queries(queries_file: Path | None) -> list[QueryItem]:
    if queries_file is None:
        return [QueryItem(question=q) for q in DEFAULT_QUERIES]

    content = queries_file.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError("Queries file is empty.")

    if queries_file.suffix.lower() == ".txt":
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        return [QueryItem(question=line) for line in lines]

    data = json.loads(content)
    if not isinstance(data, list):
        raise ValueError("JSON queries file must contain a list.")

    items: list[QueryItem] = []
    for idx, item in enumerate(data, start=1):
        if isinstance(item, str):
            items.append(QueryItem(question=item))
            continue

        if isinstance(item, dict) and "question" in item:
            items.append(
                QueryItem(
                    question=str(item["question"]).strip(),
                    expected=str(item.get("expected", "")).strip(),
                )
            )
            continue

        raise ValueError(
            f"Invalid query entry at index {idx}. Use string or object with 'question'."
        )

    return [i for i in items if i.question]


def _ask_verdict() -> tuple[str, float]:
    print("Manual correctness verdict:")
    print("  2 = correct")
    print("  1 = partially correct")
    print("  0 = incorrect")

    while True:
        raw = input("Enter verdict (2/1/0): ").strip()
        if raw == "2":
            return "correct", 1.0
        if raw == "1":
            return "partially_correct", 0.5
        if raw == "0":
            return "incorrect", 0.0
        print("Invalid input. Please enter 2, 1, or 0.")


def _print_separator() -> None:
    print("\n" + "=" * 100)


def _safe_json_dump(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def run_evaluation(args: argparse.Namespace) -> int:
    queries = _load_queries(Path(args.queries_file) if args.queries_file else None)

    if not (10 <= len(queries) <= 15):
        print(
            f"Warning: you currently have {len(queries)} queries. "
            "Requirement says 10-15 queries."
        )

    pdf_path = Path(args.pdf).resolve() if args.pdf else None
    if pdf_path is not None and not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now()
    results: list[dict[str, Any]] = []

    print(f"Server URL: {args.server_url}")
    print(f"Queries loaded: {len(queries)}")
    print(f"Top-k: {args.top_k}")
    if pdf_path:
        print(f"PDF: {pdf_path}")
        print("First request uploads the PDF; later requests use question-only mode.")

    for i, item in enumerate(queries, start=1):
        _print_separator()
        print(f"Query {i}/{len(queries)}")
        print(f"Question: {item.question}")
        if item.expected:
            print(f"Expected (reference): {item.expected}")

        use_pdf = pdf_path if i == 1 and pdf_path is not None else None

        try:
            response = _post_process(
                url=args.server_url,
                question=item.question,
                top_k=args.top_k,
                timeout=args.timeout,
                pdf_path=use_pdf,
            )
        except Exception as exc:
            print(f"Request failed for query {i}: {exc}")
            results.append(
                {
                    "query_index": i,
                    "question": item.question,
                    "expected": item.expected,
                    "error": str(exc),
                    "verdict": "not_evaluated",
                    "score": 0.0,
                    "notes": "",
                }
            )
            continue

        answer = response.get("answer", "")
        model = response.get("model", "")
        selected_method = response.get("retrieval", {}).get("selected_method", "")
        evidence = response.get("evidence", [])

        print("\nModel:", model)
        print("Selected retrieval method:", selected_method)
        print("Answer:\n", answer)

        if evidence:
            print("\nEvidence snippets:")
            for ev in evidence[:3]:
                source_num = ev.get("source_num", "?")
                chunk_id = ev.get("chunk_id", "?")
                page_num = ev.get("page_num", "?")
                snippet = (ev.get("snippet") or "")[:220].replace("\n", " ")
                print(
                    f"- Source {source_num} | chunk {chunk_id} | "
                    f"page {page_num} | {snippet}"
                )

        verdict, score = _ask_verdict()
        notes = input("Notes (optional): ").strip()

        results.append(
            {
                "query_index": i,
                "question": item.question,
                "expected": item.expected,
                "verdict": verdict,
                "score": score,
                "notes": notes,
                "answer": answer,
                "model": model,
                "selected_method": selected_method,
                "chunks_saved": response.get("chunks_saved"),
                "index_rebuilt": response.get("index_rebuilt"),
                "evidence": evidence,
            }
        )

    evaluated = [r for r in results if r.get("verdict") != "not_evaluated"]
    avg_score = (
        sum(float(r.get("score", 0.0)) for r in evaluated) / len(evaluated)
        if evaluated
        else 0.0
    )
    correct_count = sum(1 for r in evaluated if r.get("verdict") == "correct")
    partial_count = sum(1 for r in evaluated if r.get("verdict") == "partially_correct")
    incorrect_count = sum(1 for r in evaluated if r.get("verdict") == "incorrect")

    ended_at = datetime.now()
    ts = started_at.strftime("%Y%m%d_%H%M%S")

    summary = {
        "started_at": started_at.isoformat(timespec="seconds"),
        "ended_at": ended_at.isoformat(timespec="seconds"),
        "server_url": args.server_url,
        "top_k": args.top_k,
        "query_count": len(queries),
        "evaluated_count": len(evaluated),
        "average_score": round(avg_score, 4),
        "correct": correct_count,
        "partially_correct": partial_count,
        "incorrect": incorrect_count,
    }

    payload = {
        "summary": summary,
        "results": results,
    }

    json_path = output_dir / f"qualitative_eval_{ts}.json"
    csv_path = output_dir / f"qualitative_eval_{ts}.csv"

    _safe_json_dump(json_path, payload)

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "query_index",
                "question",
                "expected",
                "verdict",
                "score",
                "notes",
                "model",
                "selected_method",
                "chunks_saved",
                "index_rebuilt",
            ],
        )
        writer.writeheader()
        for row in results:
            writer.writerow({k: row.get(k, "") for k in writer.fieldnames})

    _print_separator()
    print("Evaluation complete")
    print("Summary:")
    for k, v in summary.items():
        print(f"- {k}: {v}")
    print(f"\nSaved JSON: {json_path}")
    print(f"Saved CSV:  {csv_path}")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run qualitative QA evaluation (10-15 queries) and manually score answers."
        )
    )
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL)
    parser.add_argument("--pdf", default="", help="PDF path for first request")
    parser.add_argument("--queries-file", default="", help=".txt or .json with queries")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


if __name__ == "__main__":
    try:
        raise SystemExit(run_evaluation(parse_args()))
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        raise SystemExit(130)
