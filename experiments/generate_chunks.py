"""Generate a chunks JSON file from a PDF using the project's ingestion logic.

Usage:
  python experiments/generate_chunks.py --pdf data/UG.pdf --out data/chunks.json

This writes a JSON list of objects with keys `id` and `text` suitable for
`experiments/compare_retrieval.py`.
"""

import argparse
import json
from pathlib import Path

from src.data_ingestion import ingest_pdf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, help="Path to PDF")
    parser.add_argument("--out", required=True, help="Output JSON chunks file")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    out_path = Path(args.out)

    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    chunks = ingest_pdf(pdf_path)

    out_chunks = []
    for c in chunks:
        out_chunks.append({"id": str(c.get("chunk_id")), "text": c.get("text")})

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_chunks, ensure_ascii=False), encoding="utf8")
    print(f"Wrote {len(out_chunks)} chunks to {out_path}")


if __name__ == "__main__":
    main()
