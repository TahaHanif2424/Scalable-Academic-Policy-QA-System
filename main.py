import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from src.answer_generator import generate_answer
from src.data_ingestion import ingest_pdf
from src.database import init_db, save_chunks
from src.minhash import build_minhash_index
from src.query_processor import retrieve_all
from src.simhash import build_simhash_index
from src.tfidf import build_tfidf_index

app = FastAPI(title="Academic Policy QA", version="1.0.0")


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

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        init_db()

        chunks = ingest_pdf(tmp_path)
        save_chunks(chunks)

        build_minhash_index()
        build_simhash_index()
        build_tfidf_index()

        retrieval = retrieve_all(question, top_k=top_k)
        generation = generate_answer(question, retrieval["evidence"])

        return {
            "status": "ok",
            "question": question,
            "chunks_saved": len(chunks),
            "answer": generation["answer"],
            "model": generation["model"],
            "evidence": generation["evidence"],
        }
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
