from pathlib import Path

from src.data_ingestion import ingest_pdf


def main():
    pdf_path = Path("data/UG.pdf")

    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        return

    print(f"Ingesting: {pdf_path}")

    chunks = ingest_pdf(pdf_path)

    print(f"\nSuccessfully ingested {len(chunks)} chunks.")
    if chunks:
        print("\nSample Chunk 0:")
        print(f"Page: {chunks[0]['page_num']}")
        print(f"Content: {chunks[0]['text'][:300]}...")


if __name__ == "__main__":
    main()
