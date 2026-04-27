import hashlib
import json
import pickle
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from src.answer_generator import generate_answer
from src.data_ingestion import INGESTION_VERSION, ingest_pdf
from src.database import get_db, init_db, log_query, save_chunks
from src.minhash import build_minhash_index
from src.query_patterns import mine_frequent_query_itemsets
from src.query_processor import retrieve_all
from src.simhash import build_simhash_index
from src.tfidf import build_tfidf_index

app = FastAPI(title="Academic Policy QA", version="1.0.0")

# Allow all origins so the frontend can call this API regardless of where it's hosted
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths are centralised here so every function references the same locations
CACHE_META_PATH = Path("index/active_document.json")
TFIDF_INDEX_PATH = Path("index/tfidf_index.pkl")


def _sha256_bytes(data: bytes) -> str:
    # Generate a stable file fingerprint for cache reuse checks.
    return hashlib.sha256(data).hexdigest()


def _cache_matches(file_hash: str) -> bool:
    # Validate cache metadata against current upload and ingestion version.

    # No metadata file means nothing has been cached yet
    if not CACHE_META_PATH.exists():
        return False

    try:
        payload = json.loads(CACHE_META_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Corrupted or unreadable metadata — treat as a cache miss
        return False

    # Both the file content and the ingestion pipeline version must match;
    # a pipeline upgrade should force a full re-ingest even for the same PDF
    return (
        payload.get("file_hash") == file_hash
        and payload.get("ingestion_version") == INGESTION_VERSION
    )


def _tfidf_index_is_consistent(db) -> bool:
    # Ensure on-disk TF-IDF index points to the same chunk IDs stored in MongoDB.

    # No index file on disk means it hasn't been built yet
    if not TFIDF_INDEX_PATH.exists():
        return False

    try:
        with open(TFIDF_INDEX_PATH, "rb") as f:
            index = pickle.load(f)
    except (OSError, pickle.PickleError, EOFError):
        # Corrupted pickle — consider the index stale
        return False

    chunk_ids = index.get("chunk_ids") if isinstance(index, dict) else None
    if not isinstance(chunk_ids, list) or not chunk_ids:
        return False

    # Duplicates in chunk_ids would indicate a corrupted index build
    unique_ids = sorted(set(chunk_ids))
    if len(unique_ids) != len(chunk_ids):
        return False

    # The number of chunks in the index must exactly match what's in MongoDB
    db_count = db.chunks.count_documents({})
    if db_count != len(unique_ids):
        return False

    # Every chunk ID in the index must resolve to an actual MongoDB document
    matched = db.chunks.count_documents({"chunk_id": {"$in": unique_ids}})
    return matched == len(unique_ids)


def _indexes_ready() -> bool:
    # Confirm all retrieval indexes are present and internally consistent.
    db = get_db()
    return (
        db.chunks.count_documents({}) > 0
        and db.minhash_signatures.count_documents({}) > 0
        and db.simhash_fingerprints.count_documents({}) > 0
        and _tfidf_index_is_consistent(db)
    )


def _write_cache_metadata(file_hash: str, filename: str, chunks_saved: int) -> None:
    # Persist cache metadata so repeated runs can skip expensive rebuilds.

    # Create the index directory if it doesn't exist yet
    CACHE_META_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_META_PATH.write_text(
        json.dumps(
            {
                "file_hash": file_hash,
                "filename": filename,
                "chunks_saved": chunks_saved,
                "ingestion_version": INGESTION_VERSION,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


@app.get("/health")
def health() -> dict:
    # Lightweight heartbeat endpoint.
    return {"status": "ok"}


@app.get("/insights/query-patterns")
def query_patterns(
    min_support: float = Query(0.2, ge=0.01, le=1.0),
    max_itemset_size: int = Query(3, ge=1, le=5),
    top_n: int = Query(20, ge=1, le=100),
) -> dict:
    # Return mined frequent term sets from historical user queries.
    return {
        "status": "ok",
        "insight": "frequent_query_itemsets",
        "data": mine_frequent_query_itemsets(
            min_support=min_support,
            max_itemset_size=max_itemset_size,
            top_n=top_n,
        ),
    }


@app.post("/process")
async def process_pdf_and_answer(
    file: UploadFile | None = File(None),
    question: str = Form(...),
    top_k: int = Form(5),
) -> dict:
    # Orchestrate ingestion/indexing, retrieval, generation, and response assembly.

    # Validate inputs before doing any expensive work
    if not question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    if top_k < 1:
        raise HTTPException(status_code=400, detail="top_k must be >= 1")

    tmp_path: Path | None = None

    try:
        init_db()

        # Follow-up mode: allow question-only requests after one document is indexed.
        if file is None:
            if not _indexes_ready():
                raise HTTPException(
                    status_code=400,
                    detail="No indexed document found. Upload a PDF first.",
                )
            # Reuse existing indexes — no ingestion or rebuild needed
            chunks_saved = get_db().chunks.count_documents({})
            index_rebuilt = False
        else:
            if not file.filename or not file.filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail="Please upload a PDF file")

            file_bytes = await file.read()
            if not file_bytes:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")

            file_hash = _sha256_bytes(file_bytes)

            if _cache_matches(file_hash) and _indexes_ready():
                # Same file and same pipeline version — skip ingestion entirely
                chunks_saved = get_db().chunks.count_documents({})
                index_rebuilt = False
            else:
                # Write to a temp file so ingest_pdf can read it from disk
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = Path(tmp.name)

                chunks = ingest_pdf(tmp_path)
                save_chunks(chunks)

                # Rebuild all three retrieval indexes after fresh ingestion
                build_minhash_index()
                build_simhash_index()
                build_tfidf_index()

                chunks_saved = len(chunks)
                index_rebuilt = True
                _write_cache_metadata(file_hash, file.filename, chunks_saved)

        # Run all retrieval methods and let the query processor select the best result
        retrieval = retrieve_all(question, top_k=top_k)
        selected = retrieval["selected_for_generation"]
        selected_chunks = selected["chunks"]
        top_chunks = selected_chunks[:top_k]
        generation = generate_answer(question, selected_chunks)

        # Unpack per-method outputs for logging and response construction
        approximate = retrieval.get("approximate", {})
        components = approximate.get("components", {})
        lsh_minhash_output = components.get("lsh", {"chunks": []})
        simhash_output = components.get("simhash", {"chunks": []})
        tfidf_output = retrieval.get("exact", {"chunks": []})

        # Persist the query and its results for later pattern mining
        log_query(
            question=question,
            answer=generation["answer"],
            lsh_chunks=[
                c.get("chunk_id") for c in lsh_minhash_output.get("chunks", [])
            ],
            simhash_chunks=[
                c.get("chunk_id") for c in simhash_output.get("chunks", [])
            ],
            tfidf_chunks=[c.get("chunk_id") for c in tfidf_output.get("chunks", [])],
            lsh_time_ms=float(lsh_minhash_output.get("time_ms", 0.0) or 0.0),
            simhash_time_ms=float(simhash_output.get("time_ms", 0.0) or 0.0),
            tfidf_time_ms=float(tfidf_output.get("time_ms", 0.0) or 0.0),
        )

        return {
            "status": "ok",
            "question": question,
            "top_k": top_k,
            "chunks_saved": chunks_saved,
            "index_rebuilt": index_rebuilt,
            "tfidf": tfidf_output,
            "simhash": simhash_output,
            "lsh_minhash": lsh_minhash_output,
            "retrieval": {
                "approximate": retrieval["approximate"],
                "exact": retrieval["exact"],
                "comparison": retrieval["comparison"],
                "selected_method": selected["method"],
            },
            "top_chunks": top_chunks,
            "answer": generation["answer"],
            "model": generation["model"],
            "evidence": generation["evidence"],
        }
    finally:
        # Always clean up the temp file even if an exception was raised above
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
