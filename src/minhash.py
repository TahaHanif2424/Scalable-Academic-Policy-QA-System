import re
import random
import hashlib
import numpy as np
from src.database import (
    get_all_chunks,
    save_minhash_signatures,
    save_lsh_buckets,
    get_candidate_chunk_ids,
    get_all_minhash_signatures
)

# ─── Configuration ────────────────────────────────────────────────────────────
NUM_HASH_FUNCTIONS = 128    # N — more = more accurate, slower to compute
NUM_BANDS          = 32     # b — more bands = higher recall, more false positives
ROWS_PER_BAND      = NUM_HASH_FUNCTIONS // NUM_BANDS   # r = 128/32 = 4
SHINGLE_SIZE       = 3      # k — number of words per shingle
LARGE_PRIME        = 4294967311   # large prime for hash function mod

assert NUM_BANDS * ROWS_PER_BAND == NUM_HASH_FUNCTIONS, \
    "NUM_BANDS * ROWS_PER_BAND must equal NUM_HASH_FUNCTIONS"

def build_shingles(text: str, k: int = SHINGLE_SIZE) -> set[str]:
    text   = re.sub(r'[^\w\s]', '', text.lower())
    words  = text.split()

    if len(words) < k:
        return set(words)

    shingles = set()
    for i in range(len(words) - k + 1):
        shingle = ' '.join(words[i:i + k])
        shingles.add(shingle)

    return shingles


def shingle_to_int(shingle: str) -> int:
    return int(hashlib.sha256(shingle.encode('utf-8')).hexdigest(), 16)


def generate_hash_functions(n: int, prime: int = LARGE_PRIME) -> list[tuple[int, int]]:
    random.seed(42)  
    hash_funcs = []
    for _ in range(n):
        a = random.randint(1, prime - 1)
        b = random.randint(0, prime - 1)
        hash_funcs.append((a, b))
    return hash_funcs



def compute_minhash_signature(
    shingles:    set[str],
    hash_funcs:  list[tuple[int, int]],
    prime:       int = LARGE_PRIME
) -> list[int]:
    shingle_ints = [shingle_to_int(s) for s in shingles]

    if not shingle_ints:
        return [0] * len(hash_funcs)

    signature = []
    for (a, b) in hash_funcs:
        min_hash = min((a * x + b) % prime for x in shingle_ints)
        signature.append(min_hash)

    return signature


def build_lsh_buckets(
    signatures:     dict[int, list[int]],
    num_bands:      int = NUM_BANDS,
    rows_per_band:  int = ROWS_PER_BAND
) -> dict[str, list[int]]:
    buckets = {}

    for chunk_id, signature in signatures.items():
        for band_idx in range(num_bands):
            start = band_idx * rows_per_band
            end   = start + rows_per_band

            band_rows = tuple(signature[start:end])

            band_hash    = hashlib.md5(str(band_rows).encode()).hexdigest()[:16]
            bucket_key   = f"band_{band_idx}_{band_hash}"

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

    signatures = {}

    for i, chunk in enumerate(chunks):
        # build shingles
        shingles  = build_shingles(chunk["text"])

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
    hash_funcs      = generate_hash_functions(NUM_HASH_FUNCTIONS)
    shingles        = build_shingles(query_text)
    query_signature = compute_minhash_signature(shingles, hash_funcs)

    bucket_keys = []
    for band_idx in range(NUM_BANDS):
        start      = band_idx * ROWS_PER_BAND
        end        = start + ROWS_PER_BAND
        band_rows  = tuple(query_signature[start:end])
        band_hash  = hashlib.md5(str(band_rows).encode()).hexdigest()[:16]
        bucket_keys.append(f"band_{band_idx}_{band_hash}")

    candidate_ids = get_candidate_chunk_ids(bucket_keys)

    if not candidate_ids:
        print("[minhash] No candidates found in LSH buckets.")
        return []

    all_signatures = get_all_minhash_signatures()

    scored = []
    for chunk_id in candidate_ids:
        if chunk_id not in all_signatures:
            continue
        sim = jaccard_from_signatures(query_signature, all_signatures[chunk_id])
        scored.append({"chunk_id": chunk_id, "similarity": sim})

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]


if __name__ == "__main__":
    import time

    print("=" * 60)
    print("MinHash + LSH — unit tests")
    print("=" * 60)

        # test 1: shingles
    text     = "the minimum GPA requirement for graduation is 2.0"
    shingles = build_shingles(text, k=3)
    print(f"\n[test 1] Shingles from: '{text}'")
    for s in list(shingles)[:5]:
        print(f"  '{s}'")

    # test 2: hash functions
    hf = generate_hash_functions(4)
    print(f"\n[test 2] Generated 4 hash functions (a,b):")
    for a, b in hf:
        print(f"  a={a}, b={b}")

    # test 3: signature
    sig = compute_minhash_signature(shingles, hf)
    print(f"\n[test 3] Signature (4 values): {sig}")

    # test 4: Jaccard similarity
    text_a = "minimum GPA requirement for graduation"
    text_b = "minimum GPA requirement to pass the course"
    text_c = "the attendance policy requires 80 percent"

    hf128  = generate_hash_functions(128)
    sig_a  = compute_minhash_signature(build_shingles(text_a), hf128)
    sig_b  = compute_minhash_signature(build_shingles(text_b), hf128)
    sig_c  = compute_minhash_signature(build_shingles(text_c), hf128)

    sim_ab = jaccard_from_signatures(sig_a, sig_b)
    sim_ac = jaccard_from_signatures(sig_a, sig_c)

    print(f"\n[test 4] Jaccard similarity:")
    print(f"  A vs B (similar topic) : {sim_ab:.3f}  ← should be higher")
    print(f"  A vs C (different topic): {sim_ac:.3f}  ← should be lower")

    # test 5: full index build + query (requires MongoDB with chunks)
    print(f"\n[test 5] Building full MinHash index from MongoDB...")
    start = time.time()
    build_minhash_index()
    elapsed = (time.time() - start) * 1000
    print(f"  Index built in {elapsed:.1f}ms")

    print(f"\n[test 6] Querying: 'What is the minimum GPA requirement?'")
    start   = time.time()
    results = query_minhash("What is the minimum GPA requirement?", top_k=3)
    elapsed = (time.time() - start) * 1000
    print(f"  Query completed in {elapsed:.1f}ms")
    print(f"  Top results:")
    for r in results:
        print(f"    chunk_id={r['chunk_id']}  similarity={r['similarity']:.3f}")