import hashlib
import random
import re

import numpy as np
from nltk.corpus import stopwords

from src.database import (
    get_all_chunks,
    get_all_minhash_signatures,
    get_candidate_chunk_ids,
    get_hash_functions,
    save_hash_functions,
    save_lsh_buckets,
    save_minhash_signatures,
)

# ─── Configuration ────────────────────────────────────────────────────────────
NUM_HASH_FUNCTIONS = 128  # N — more = more accurate, slower to compute
NUM_BANDS = 64  # b — more bands = higher recall (lower threshold ~0.25)
ROWS_PER_BAND = NUM_HASH_FUNCTIONS // NUM_BANDS  # r = 128/64 = 2
SHINGLE_SIZE = 2  # k — bigrams give better query↔chunk overlap than trigrams
LARGE_PRIME = 4294967311  # large prime for hash function mod
STOP_WORDS = set(stopwords.words("english"))

assert (
    NUM_BANDS * ROWS_PER_BAND == NUM_HASH_FUNCTIONS
), "NUM_BANDS * ROWS_PER_BAND must equal NUM_HASH_FUNCTIONS"


def build_shingles(text: str, k: int = SHINGLE_SIZE) -> set[str]:
    text = re.sub(r"[^\w\s]", "", text.lower())
    words = text.split()
    words = [w for w in words if w not in STOP_WORDS]
    if len(words) < k:
        return set(words)
    shingles = set()
    for i in range(len(words) - k + 1):
        shingle = " ".join(words[i : i + k])
        shingles.add(shingle)

    return shingles


def shingle_to_int(shingle: str) -> int:
    return int(hashlib.sha256(shingle.encode("utf-8")).hexdigest(), 16)


def generate_hash_functions(n: int, prime: int = LARGE_PRIME) -> list[tuple[int, int]]:
    hash_funcs = []
    for i in range(n):
        a_bytes = hashlib.sha256(f"hash_a_{i}".encode()).digest()
        b_bytes = hashlib.sha256(f"hash_b_{i}".encode()).digest()
        a = int.from_bytes(a_bytes, "big") % (prime - 1) + 1
        b = int.from_bytes(b_bytes, "big") % prime
        hash_funcs.append((a, b))
    return hash_funcs


def compute_minhash_signature(
    shingles: set[str], hash_funcs: list[tuple[int, int]], prime: int = LARGE_PRIME
) -> list[int]:
    shingle_ints = [shingle_to_int(s) for s in shingles]

    if not shingle_ints:
        return [0] * len(hash_funcs)

    signature = []
    for a, b in hash_funcs:
        min_hash = min((a * x + b) % prime for x in shingle_ints)
        signature.append(min_hash)

    return signature


def build_lsh_buckets(
    signatures: dict[int, list[int]],
    num_bands: int = NUM_BANDS,
    rows_per_band: int = ROWS_PER_BAND,
) -> dict[str, list[int]]:
    buckets = {}

    for chunk_id, signature in signatures.items():
        for band_idx in range(num_bands):
            start = band_idx * rows_per_band
            end = start + rows_per_band

            band_rows = tuple(signature[start:end])

            band_hash = hashlib.md5(str(band_rows).encode()).hexdigest()[:16]
            bucket_key = f"band_{band_idx}_{band_hash}"

            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append(chunk_id)

    return buckets


def jaccard_from_signatures(sig_a: list[int], sig_b: list[int]) -> float:
    if len(sig_a) != len(sig_b):
        return 0.0
    matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return matches / len(sig_a)


def build_minhash_index():
    print("[minhash] Starting MinHash index build...")

    chunks = get_all_chunks()
    if not chunks:
        print("[minhash] No chunks found in MongoDB. Run ingestion first.")
        return

    print(f"[minhash] Processing {len(chunks)} chunks...")

    hash_funcs = generate_hash_functions(NUM_HASH_FUNCTIONS)
    save_hash_functions(hash_funcs)  # persist so query always uses same functions

    signatures = {}

    for i, chunk in enumerate(chunks):
        # build shingles
        shingles = build_shingles(chunk["text"])

        # compute MinHash signature
        signature = compute_minhash_signature(shingles, hash_funcs)

        signatures[chunk["chunk_id"]] = signature

        if (i + 1) % 50 == 0:
            print(f"[minhash]   {i + 1}/{len(chunks)} signatures computed...")

    save_minhash_signatures(signatures)

    print("[minhash] Building LSH buckets...")
    buckets = build_lsh_buckets(signatures)
    save_lsh_buckets(buckets)

    print(f"[minhash] Done. {len(signatures)} signatures, {len(buckets)} buckets")


def query_minhash(query_text: str, top_k: int = 5) -> list[dict]:
    # Load the exact same hash functions used during index build
    hash_funcs = get_hash_functions()
    if not hash_funcs:
        # Fallback: regenerate deterministically (same result as build)
        hash_funcs = generate_hash_functions(NUM_HASH_FUNCTIONS)

    shingles = build_shingles(query_text)
    query_signature = compute_minhash_signature(shingles, hash_funcs)

    bucket_keys = []
    for band_idx in range(NUM_BANDS):
        start = band_idx * ROWS_PER_BAND
        end = start + ROWS_PER_BAND
        band_rows = tuple(query_signature[start:end])
        band_hash = hashlib.md5(str(band_rows).encode()).hexdigest()[:16]
        bucket_keys.append(f"band_{band_idx}_{band_hash}")

    candidate_ids = get_candidate_chunk_ids(bucket_keys)

    all_signatures = get_all_minhash_signatures()

    if not candidate_ids:
        # Fallback: brute-force scan all signatures (query is too short for LSH)
        print("[minhash] No LSH candidates — falling back to full signature scan.")
        candidate_ids = list(all_signatures.keys())

    scored = []
    for chunk_id in candidate_ids:
        if chunk_id not in all_signatures:
            continue
        sim = jaccard_from_signatures(query_signature, all_signatures[chunk_id])
        scored.append({"chunk_id": chunk_id, "similarity": sim})

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]
