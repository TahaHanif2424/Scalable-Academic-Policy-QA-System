import hashlib
import re
from collections import Counter

from nltk.corpus import stopwords

from src.database import (
    get_all_chunks,
    get_all_simhash_fingerprints,
    save_simhash_fingerprints,
)

FINGERPRINT_BITS = 64
HAMMING_THRESHOLD = 5
STOP_WORDS = set(stopwords.words("english"))


def tokenize(text: str) -> dict[str, int]:
    text = re.sub(r"[^\w\s]", "", text.lower())
    words = text.split()
    words = [w for w in words if w not in STOP_WORDS]

    words = [w for w in words if len(w) > 2]
    return dict(Counter(words))


def hash_word(word: str, bits: int = FINGERPRINT_BITS) -> int:
    digest = hashlib.sha256(word.encode("utf-8")).digest()
    return int.from_bytes(digest[: bits // 8], "big")


def compute_simhash(text: str, bits: int = FINGERPRINT_BITS) -> int:
    word_weights = tokenize(text)

    if not word_weights:
        return 0

    vector = [0.0] * bits

    for word, weight in word_weights.items():
        word_hash = hash_word(word, bits)

        for i in range(bits):
            bit = (word_hash >> (bits - 1 - i)) & 1
            if bit == 1:
                vector[i] += weight
            else:
                vector[i] -= weight

    fingerprint = 0
    for i in range(bits):
        if vector[i] > 0:
            fingerprint |= 1 << (bits - 1 - i)

    return fingerprint


def hamming_distance(fp_a: int, fp_b: int) -> int:

    xor = fp_a ^ fp_b
    return bin(xor).count("1")


def hamming_similarity(fp_a: int, fp_b: int, bits: int = FINGERPRINT_BITS) -> float:

    distance = hamming_distance(fp_a, fp_b)
    return 1.0 - (distance / bits)


def build_simhash_index():

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

        if (i + 1) % 50 == 0:
            print(f"[simhash]   {i + 1}/{len(chunks)} fingerprints computed...")

    save_simhash_fingerprints(fingerprints)
    print(f"[simhash] Done. {len(fingerprints)} fingerprints saved.")


def query_simhash(query_text: str, top_k: int = 5) -> list[dict]:

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
