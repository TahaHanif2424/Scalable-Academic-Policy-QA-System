import hashlib
import re

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

# Sanity check: LSH banding math requires bands * rows == total hash functions
assert NUM_BANDS * ROWS_PER_BAND == NUM_HASH_FUNCTIONS, (
    "NUM_BANDS * ROWS_PER_BAND must equal NUM_HASH_FUNCTIONS"
)


def build_shingles(text: str, k: int = SHINGLE_SIZE) -> set[str]:
    # Convert text into normalized k-shingles for MinHash.

    # Strip punctuation and lowercase so surface variation doesn't affect similarity
    text = re.sub(r"[^\w\s]", "", text.lower())
    words = text.split()

    # Remove stop words — they add noise without contributing to topical similarity
    words = [w for w in words if w not in STOP_WORDS]

    # If the text is shorter than one full shingle, return individual words as fallback
    if len(words) < k:
        return set(words)

    # Slide a window of size k across the word list to produce overlapping bigrams
    shingles = set()
    for i in range(len(words) - k + 1):
        shingle = " ".join(words[i : i + k])
        shingles.add(shingle)

    return shingles


def shingle_to_int(shingle: str) -> int:
    # Deterministically hash a shingle into an integer domain.

    # SHA-256 gives a uniform, collision-resistant mapping from string → large int,
    # which is then used as input x to each universal hash function h(x) = (ax+b) % p
    return int(hashlib.sha256(shingle.encode("utf-8")).hexdigest(), 16)


def generate_hash_functions(n: int, prime: int = LARGE_PRIME) -> list[tuple[int, int]]:
    # Build deterministic universal hash functions used by MinHash signatures.

    # Each hash function is of the form h(x) = (a*x + b) % prime — a classic
    # universal hash family. Parameters a and b are derived from SHA-256 so they
    # are fully deterministic across runs (no random seed needed).
    hash_funcs = []
    for i in range(n):
        # Derive unique a and b for each function using indexed seeds
        a_bytes = hashlib.sha256(f"hash_a_{i}".encode()).digest()
        b_bytes = hashlib.sha256(f"hash_b_{i}".encode()).digest()

        # a must be in [1, prime-1] to avoid the degenerate case a=0
        a = int.from_bytes(a_bytes, "big") % (prime - 1) + 1
        b = int.from_bytes(b_bytes, "big") % prime
        hash_funcs.append((a, b))
    return hash_funcs


def compute_minhash_signature(
    shingles: set[str], hash_funcs: list[tuple[int, int]], prime: int = LARGE_PRIME
) -> list[int]:
    # Compute the MinHash signature vector for one shingle set.

    # Convert each shingle string to its integer representation once up front
    # to avoid redundant hashing inside the inner loop
    shingle_ints = [shingle_to_int(s) for s in shingles]

    # Empty documents get an all-zero signature; they will appear dissimilar to everything
    if not shingle_ints:
        return [0] * len(hash_funcs)

    # For each hash function, the MinHash value is the minimum h(x) over all shingles.
    # The probability that two sets share the same minimum equals their Jaccard similarity.
    signature = []
    for a, b in hash_funcs:
        min_hash = min((a * x + b) % prime for x in shingle_ints)
        signature.append(min_hash)

    return signature


def build_lsh_buckets(
    signatures: dict[int, list[int]],
    num_bands: int | None = None,
    rows_per_band: int | None = None,
) -> dict[str, list[int]]:
    # Group signature bands into bucket keys for fast candidate lookup.

    # Fall back to module-level defaults if not explicitly provided
    if num_bands is None:
        num_bands = NUM_BANDS
    if rows_per_band is None:
        rows_per_band = ROWS_PER_BAND

    # buckets maps a band-specific hash string → list of chunk_ids that landed there
    buckets = {}

    for chunk_id, signature in signatures.items():
        for band_idx in range(num_bands):
            # Slice out this band's rows from the full signature vector
            start = band_idx * rows_per_band
            end = start + rows_per_band
            band_rows = tuple(signature[start:end])

            # Hash the band rows to a short hex string to use as a bucket key.
            # Two chunks with identical band rows will hash to the same bucket,
            # making them candidates for a full similarity check.
            band_hash = hashlib.md5(str(band_rows).encode()).hexdigest()[:16]
            bucket_key = f"band_{band_idx}_{band_hash}"

            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append(chunk_id)

    return buckets


def jaccard_from_signatures(sig_a: list[int], sig_b: list[int]) -> float:
    # Estimate Jaccard similarity via signature agreement ratio.

    # Signatures must be the same length to be comparable
    if len(sig_a) != len(sig_b):
        return 0.0

    # The fraction of positions where both signatures agree is an unbiased
    # estimator of the true Jaccard similarity between the original shingle sets
    matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return matches / len(sig_a)


def build_minhash_index():
    # Build and persist signatures plus LSH buckets for all stored chunks.
    print("[minhash] Starting MinHash index build...")

    # Validate config before doing any expensive work
    if NUM_BANDS <= 0 or NUM_HASH_FUNCTIONS <= 0:
        raise ValueError("NUM_HASH_FUNCTIONS and NUM_BANDS must be positive")
    if NUM_HASH_FUNCTIONS % NUM_BANDS != 0:
        raise ValueError("NUM_HASH_FUNCTIONS must be divisible by NUM_BANDS")

    rows_per_band = NUM_HASH_FUNCTIONS // NUM_BANDS

    chunks = get_all_chunks()
    if not chunks:
        print("[minhash] No chunks found in MongoDB. Run ingestion first.")
        return

    print(f"[minhash] Processing {len(chunks)} chunks...")

    # Generate and persist hash functions so the query path uses the exact same
    # parameters — signatures are meaningless if built with different functions
    hash_funcs = generate_hash_functions(NUM_HASH_FUNCTIONS)
    save_hash_functions(hash_funcs)  # persist so query always uses same functions

    signatures = {}

    for i, chunk in enumerate(chunks):
        # build shingles
        shingles = build_shingles(chunk["text"])

        # compute MinHash signature
        signature = compute_minhash_signature(shingles, hash_funcs)

        signatures[chunk["chunk_id"]] = signature

        # Periodic progress logging to track long-running index builds
        if (i + 1) % 50 == 0:
            print(f"[minhash]   {i + 1}/{len(chunks)} signatures computed...")

    save_minhash_signatures(signatures)

    # Band the signatures into LSH buckets for sub-linear candidate retrieval
    print("[minhash] Building LSH buckets...")
    buckets = build_lsh_buckets(
        signatures,
        num_bands=NUM_BANDS,
        rows_per_band=rows_per_band,
    )
    save_lsh_buckets(buckets)

    print(f"[minhash] Done. {len(signatures)} signatures, {len(buckets)} buckets")


def query_minhash(query_text: str, top_k: int = 5) -> list[dict]:
    # Retrieve top-k similar chunks using MinHash + LSH candidate filtering.

    # Load the exact same hash functions used during index build
    hash_funcs = get_hash_functions()
    if not hash_funcs:
        # Fallback: regenerate deterministically (same result as build)
        hash_funcs = generate_hash_functions(NUM_HASH_FUNCTIONS)

    # Compute the query's signature using the same pipeline as index time
    shingles = build_shingles(query_text)
    query_signature = compute_minhash_signature(shingles, hash_funcs)

    # Reconstruct the bucket keys the query would fall into for each band,
    # mirroring exactly the logic used in build_lsh_buckets
    bucket_keys = []
    for band_idx in range(NUM_BANDS):
        start = band_idx * ROWS_PER_BAND
        end = start + ROWS_PER_BAND
        band_rows = tuple(query_signature[start:end])
        band_hash = hashlib.md5(str(band_rows).encode()).hexdigest()[:16]
        bucket_keys.append(f"band_{band_idx}_{band_hash}")

    # Fetch only the chunk IDs that share at least one band bucket with the query
    candidate_ids = get_candidate_chunk_ids(bucket_keys)

    # Load all stored signatures so we can score candidates precisely
    all_signatures = get_all_minhash_signatures()

    if not candidate_ids:
        # Short queries may not shingle into any populated bucket, so fall back
        # to a brute-force scan over all signatures to avoid returning nothing
        print("[minhash] No LSH candidates — falling back to full signature scan.")
        candidate_ids = list(all_signatures.keys())

    # Score each candidate with an exact signature comparison and keep the best k
    scored = []
    for chunk_id in candidate_ids:
        if chunk_id not in all_signatures:
            continue
        sim = jaccard_from_signatures(query_signature, all_signatures[chunk_id])
        scored.append({"chunk_id": chunk_id, "similarity": sim})

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]
