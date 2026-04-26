import hashlib
import json
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from src.answer_generator import generate_answer
from src.data_ingestion import ingest_pdf
from src.database import get_db, init_db, save_chunks
from src.minhash import build_minhash_index
from src.query_processor import retrieve_all
from src.simhash import build_simhash_index
from src.tfidf import build_tfidf_index

app = FastAPI(title="Academic Policy QA", version="1.0.0")

CACHE_META_PATH = Path("index/active_document.json")
TFIDF_INDEX_PATH = Path("index/tfidf_index.pkl")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cache_matches(file_hash: str) -> bool:
    if not CACHE_META_PATH.exists():
        return False

    try:
        payload = json.loads(CACHE_META_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    return payload.get("file_hash") == file_hash


def _indexes_ready() -> bool:
    db = get_db()
    return (
        db.chunks.count_documents({}) > 0
        and db.minhash_signatures.count_documents({}) > 0
        and db.simhash_fingerprints.count_documents({}) > 0
        and TFIDF_INDEX_PATH.exists()
    )


def _write_cache_metadata(file_hash: str, filename: str, chunks_saved: int) -> None:
    CACHE_META_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_META_PATH.write_text(
        json.dumps(
            {
                "file_hash": file_hash,
                "filename": filename,
                "chunks_saved": chunks_saved,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/process")
async def process_pdf_and_answer(
    file: UploadFile = File(...),
    question: str = Form(...),
    top_k: int = Form(5),
) -> dict:
    if not question.strip():
        raise HTTPException(status_code=400, detail="question is required")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    file_hash = _sha256_bytes(file_bytes)
    tmp_path: Path | None = None

    try:
        init_db()

        if _cache_matches(file_hash) and _indexes_ready():
            chunks_saved = get_db().chunks.count_documents({})
            index_rebuilt = False
        else:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = Path(tmp.name)

            chunks = ingest_pdf(tmp_path)
            save_chunks(chunks)

            build_minhash_index()
            build_simhash_index()
            build_tfidf_index()

            chunks_saved = len(chunks)
            index_rebuilt = True
            _write_cache_metadata(file_hash, file.filename, chunks_saved)

        retrieval = retrieve_all(question, top_k=top_k)
        generation = generate_answer(question, retrieval["evidence"])

        return {
            "status": "ok",
            "question": question,
            "chunks_saved": chunks_saved,
            "index_rebuilt": index_rebuilt,
            "answer": generation["answer"],
            "model": generation["model"],
            "evidence": generation["evidence"],
        }
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
