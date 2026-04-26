import json
import os
from datetime import datetime

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "qa_system")


# ─── Connection ───────────────────────────────────────────────────────────────
def get_db():
    client = MongoClient(MONGO_URL)
    return client[MONGO_DB]


def init_db():
    db = get_db()

    db.chunks.create_index([("chunk_id", ASCENDING)], unique=True)
    db.chunks.create_index([("page_num", ASCENDING)])
    db.minhash_signatures.create_index([("chunk_id", ASCENDING)], unique=True)
    db.lsh_buckets.create_index([("bucket_key", ASCENDING)], unique=True)
    db.simhash_fingerprints.create_index([("chunk_id", ASCENDING)], unique=True)
    db.query_log.create_index([("created_at", ASCENDING)])

    print(f"[database] MongoDB initialized — db: {MONGO_DB}")


def save_chunks(chunks: list[dict]):
    db = get_db()
    db.chunks.delete_many({})
    db.minhash_signatures.delete_many({})
    db.lsh_buckets.delete_many({})
    db.simhash_fingerprints.delete_many({})

    if chunks:
        db.chunks.insert_many(chunks)

    print(f"[database] Saved {len(chunks)} chunks to MongoDB")


def get_all_chunks() -> list[dict]:
    db = get_db()
    return list(db.chunks.find({}, {"_id": 0}).sort("chunk_id", ASCENDING))


def get_chunks_by_ids(chunk_ids: list[int]) -> list[dict]:
    if not chunk_ids:
        return []
    db = get_db()
    return list(
        db.chunks.find({"chunk_id": {"$in": chunk_ids}}, {"_id": 0}).sort(
            "chunk_id", ASCENDING
        )
    )


def get_chunk_count() -> int:
    db = get_db()
    return db.chunks.count_documents({})


# ─── MinHash signatures ───────────────────────────────────────────────────────
def save_minhash_signatures(signatures: dict[int, list[int]]):

    db = get_db()
    db.minhash_signatures.delete_many({})

    if signatures:
        docs = [
            {"chunk_id": chunk_id, "signature": sig}
            for chunk_id, sig in signatures.items()
        ]
        db.minhash_signatures.insert_many(docs)

    print(f"[database] Saved {len(signatures)} MinHash signatures")


def get_all_minhash_signatures() -> dict[int, list[int]]:

    db = get_db()
    docs = db.minhash_signatures.find({}, {"_id": 0})
    return {doc["chunk_id"]: doc["signature"] for doc in docs}


# ─── LSH buckets ─────────────────────────────────────────────────────────────
def save_lsh_buckets(buckets: dict[str, list[int]]):

    db = get_db()
    db.lsh_buckets.delete_many({})

    if buckets:
        docs = [{"bucket_key": key, "chunk_ids": ids} for key, ids in buckets.items()]
        db.lsh_buckets.insert_many(docs)

    print(f"[database] Saved {len(buckets)} LSH buckets")


def get_candidate_chunk_ids(bucket_keys: list[str]) -> list[int]:

    if not bucket_keys:
        return []
    db = get_db()
    docs = db.lsh_buckets.find(
        {"bucket_key": {"$in": bucket_keys}}, {"_id": 0, "chunk_ids": 1}
    )
    candidate_ids = set()
    for doc in docs:
        candidate_ids.update(doc["chunk_ids"])
    return list(candidate_ids)


# ─── SimHash fingerprints ─────────────────────────────────────────────────────
def save_simhash_fingerprints(fingerprints: dict[int, int]):

    db = get_db()
    db.simhash_fingerprints.delete_many({})

    if fingerprints:
        docs = [
            # Store as hex string — SimHash is an unsigned 64-bit int which
            # exceeds MongoDB's signed 64-bit BSON int limit (2^63-1).
            {"chunk_id": chunk_id, "fingerprint": format(fp, "016x")}
            for chunk_id, fp in fingerprints.items()
        ]
        db.simhash_fingerprints.insert_many(docs)

    print(f"[database] Saved {len(fingerprints)} SimHash fingerprints")


def get_all_simhash_fingerprints() -> dict[int, int]:

    db = get_db()
    docs = db.simhash_fingerprints.find({}, {"_id": 0})
    # Parse hex string back to int (handles unsigned 64-bit fingerprints).
    return {doc["chunk_id"]: int(doc["fingerprint"], 16) for doc in docs}


# ─── Query log ────────────────────────────────────────────────────────────────
def log_query(
    question: str,
    answer: str,
    lsh_chunks: list[int],
    simhash_chunks: list[int],
    tfidf_chunks: list[int],
    lsh_time_ms: float,
    simhash_time_ms: float,
    tfidf_time_ms: float,
):

    db = get_db()
    db.query_log.insert_one(
        {
            "question": question,
            "answer": answer,
            "lsh_chunks": lsh_chunks,
            "simhash_chunks": simhash_chunks,
            "tfidf_chunks": tfidf_chunks,
            "lsh_time_ms": lsh_time_ms,
            "simhash_time_ms": simhash_time_ms,
            "tfidf_time_ms": tfidf_time_ms,
            "created_at": datetime.utcnow(),
        }
    )


def get_query_logs() -> list[dict]:
    db = get_db()
    logs = list(db.query_log.find({}, {"_id": 0}).sort("created_at", -1))
    return logs


def save_hash_functions(hash_funcs: list[tuple[int, int]]):
    """Saves the (a,b) hash function pairs used to build the index."""
    db = get_db()
    db.hash_functions.delete_many({})
    db.hash_functions.insert_one({"functions": [[a, b] for a, b in hash_funcs]})
    print(f"[database] Saved {len(hash_funcs)} hash functions")


def get_hash_functions() -> list[tuple[int, int]]:
    """Loads the exact same hash functions used during index build."""
    db = get_db()
    doc = db.hash_functions.find_one({}, {"_id": 0})
    if not doc:
        return []
    return [(row[0], row[1]) for row in doc["functions"]]
