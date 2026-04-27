import hashlib
import re
from collections import Counter

from nltk.corpus import stopwords

from src.database import (
    get_all_chunks,
    get_all_simhash_fingerprints,
    save_simhash_fingerprints,
)

# Number of bits in each SimHash fingerprint — 64 bits balances precision and storage
FINGERPRINT_BITS = 64
# Maximum Hamming distance to consider two chunks "similar" — tunable sensitivity knob
HAMMING_THRESHOLD = 5
STOP_WORDS = set(stopwords.words("english"))


def tokenize(text: str) -> dict[str, int]:
    # Normalize text and build weighted term frequencies.

    # Strip punctuation and lowercase to reduce surface variation
    text = re.sub(r"[^\w\s]", "", text.lower())
    words = text.split()

    # Remove stop words — high-frequency function words dilute topical signal
    words = [w for w in words if w not in STOP_WORDS]

    # Drop very short tokens (1-2 chars) that are unlikely to carry meaning
    words = [w for w in words if len(w) > 2]
    return dict(Counter(words))


def hash_word(word: str, bits: int = FINGERPRINT_BITS) -> int:
    # Hash a token into a fixed-width bit representation.

    # SHA-256 produces 32 bytes; we take only the first `bits/8` bytes so the
    # result fits exactly in a `bits`-wide integer used for fingerprint projection
    digest = hashlib.sha256(word.encode("utf-8")).digest()
    return int.from_bytes(digest[: bits // 8], "big")


def compute_simhash(text: str, bits: int = FINGERPRINT_BITS) -> int:
    # Project weighted token hashes into a single SimHash fingerprint.
    word_weights = tokenize(text)

    # Empty documents get a zero fingerprint — they will appear maximally distant
    if not word_weights:
        return 0

    # Accumulator vector: one float per bit position
    vector = [0.0] * bits

    for word, weight in word_weights.items():
        word_hash = hash_word(word, bits)

        # For each bit position, add the token's weight if the bit is 1,
        # subtract it if the bit is 0 — this is the core SimHash projection step
        for i in range(bits):
            bit = (word_hash >> (bits - 1 - i)) & 1
            if bit == 1:
                vector[i] += weight
            else:
                vector[i] -= weight

    # Collapse the float vector to a single integer: bit=1 where vector[i] > 0
    fingerprint = 0
    for i in range(bits):
        if vector[i] > 0:
            fingerprint |= 1 << (bits - 1 - i)

    return fingerprint


def hamming_distance(fp_a: int, fp_b: int) -> int:
    # Count differing bits between two fingerprints.

    # XOR isolates the positions where the two fingerprints disagree;
    # counting 1-bits in the result gives the Hamming distance
    xor = fp_a ^ fp_b
    return bin(xor).count("1")


def hamming_similarity(fp_a: int, fp_b: int, bits: int = FINGERPRINT_BITS) -> float:
    # Convert Hamming distance into a normalized similarity score.

    # Dividing by total bits maps distance into [0, 1] and inverting gives
    # similarity: 1.0 = identical fingerprints, 0.0 = all bits differ
    distance = hamming_distance(fp_a, fp_b)
    return 1.0 - (distance / bits)


def build_simhash_index():
    # Compute and persist one SimHash fingerprint per chunk.

    print("[simhash] Starting SimHash index build...")

    chunks = get_all_chunks()
    if not chunks:
        print("[simhash] No chunks found. Run ingestion first.")
        return

    print(f"[simhash] Processing {len(chunks)} chunks...")

    fingerprints = {}

    for i, chunk in enumerate(chunks):
        fp = compute_simhash(chunk["text"])
        fingerprints[chunk["chunk_id"]] = fp

        # Periodic progress logging for long-running index builds
        if (i + 1) % 50 == 0:
            print(f"[simhash]   {i + 1}/{len(chunks)} fingerprints computed...")

    save_simhash_fingerprints(fingerprints)
    print(f"[simhash] Done. {len(fingerprints)} fingerprints saved.")


def query_simhash(query_text: str, top_k: int = 5) -> list[dict]:
    # Retrieve top-k chunks using query fingerprint proximity.

    # step 1: fingerprint the query
    query_fp = compute_simhash(query_text)

    # step 2: load all fingerprints from MongoDB
    all_fps = get_all_simhash_fingerprints()

    if not all_fps:
        print("[simhash] No fingerprints in DB. Run build_simhash_index() first.")
        return []

    # step 3+4: compute distance and filter by threshold
    results = []
    for chunk_id, fp in all_fps.items():
        dist = hamming_distance(query_fp, fp)
        if dist <= HAMMING_THRESHOLD:
            results.append(
                {
                    "chunk_id": chunk_id,
                    "distance": dist,
                    "similarity": hamming_similarity(query_fp, fp),
                }
            )

    if not results:
        # threshold too strict — return top-k closest regardless of threshold
        print(f"[simhash] No chunks within threshold {HAMMING_THRESHOLD}.")
        print(f"[simhash] Returning top-{top_k} closest chunks instead.")
        all_results = [
            {
                "chunk_id": chunk_id,
                "distance": hamming_distance(query_fp, fp),
                "similarity": hamming_similarity(query_fp, fp),
            }
            for chunk_id, fp in all_fps.items()
        ]
        all_results.sort(key=lambda x: x["distance"])
        return all_results[:top_k]

    # step 5: sort by distance ascending (lowest distance = most similar)
    results.sort(key=lambda x: x["distance"])

    # step 6: return top-k
    return results[:top_k]
