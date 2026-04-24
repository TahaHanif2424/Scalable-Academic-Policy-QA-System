import re
from pathlib import Path

import nltk
import pdfplumber

nltk.download("punkt", quite=True)
nltk.download("stopwords", quite=True)

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
MIN_CHUNK_SIZE = 100


def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    """Extracts all raw text from a PDF file."""
    raw_pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                raw_pages.append({"page_num": page_num, "raw_text": text})
    return raw_pages


def clean_text(text: str) -> str:

    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    lines = text.split("\n")
    lines = [l for l in lines if len(l.strip()) > 4]
    text = " ".join(lines)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s\.\,\;\:\!\?\-\(\)\'\"]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def split_into_chunks(
    text: str, page_num: int, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[dict]:

    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]

        if len(chunk_words) >= MIN_CHUNK_SIZE:
            chunks.append(
                {
                    "text": " ".join(chunk_words),
                    "word_count": len(chunk_words),
                    "page_num": page_num,
                    "start_word": start,
                    "end_word": end,
                }
            )

        start += chunk_size - overlap

    return chunks


def ingest_pdf(pdf_path: Path) -> list[dict]:
    pages = extract_text_from_pdf(pdf_path)

    all_chunks = []
    chunk_id = 0

    for page in pages:
        cleaned = clean_text(page["raw_text"])

        if len(cleaned.split()) < MIN_CHUNK_SIZE:
            continue

        chunks = split_into_chunks(cleaned, page["page_num"])

        for chunk in chunks:
            chunk["chunk_id"] = chunk_id
            all_chunks.append(chunk)
            chunk_id += 1

    print(f"[ingestion] Created {len(all_chunks)} chunks from {len(pages)} pages")
    return all_chunks
