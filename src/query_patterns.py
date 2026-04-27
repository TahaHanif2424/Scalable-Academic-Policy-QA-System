import re
from collections import Counter
from itertools import combinations

from src.database import get_query_logs

# Compact stopword list for query-pattern mining.
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "can",
    "could",
    "should",
    "would",
    "do",
    "does",
    "did",
    "student",
    "students",
    "policy",
    "policies",
}


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]+", text.lower())
    return [t for t in tokens if len(t) >= 3 and t not in STOPWORDS]


def _build_transactions(questions: list[str]) -> list[set[str]]:
    transactions = []
    for q in questions:
        token_set = set(_tokenize(q))
        if token_set:
            transactions.append(token_set)
    return transactions


def mine_frequent_query_itemsets(
    min_support: float = 0.2,
    max_itemset_size: int = 3,
    top_n: int = 20,
) -> dict:
    """
    Mine frequent term itemsets from logged user questions using an Apriori-style pass.
    min_support is expressed as a ratio in [0, 1].
    """
    logs = get_query_logs()
    questions = [row.get("question", "") for row in logs if row.get("question")]
    transactions = _build_transactions(questions)

    tx_count = len(transactions)
    if tx_count == 0:
        return {
            "transaction_count": 0,
            "min_support": min_support,
            "max_itemset_size": max_itemset_size,
            "patterns": [],
        }

    min_support_count = max(1, int(min_support * tx_count + 0.9999))
    itemsets: list[dict] = []

    for size in range(1, max_itemset_size + 1):
        counts: Counter[tuple[str, ...]] = Counter()

        for tx in transactions:
            if len(tx) < size:
                continue
            for combo in combinations(sorted(tx), size):
                counts[combo] += 1

        for terms, support_count in counts.items():
            if support_count < min_support_count:
                continue
            itemsets.append(
                {
                    "terms": list(terms),
                    "size": size,
                    "support_count": support_count,
                    "support_ratio": round(support_count / tx_count, 4),
                }
            )

    itemsets.sort(key=lambda x: (x["support_count"], x["size"]), reverse=True)

    return {
        "transaction_count": tx_count,
        "min_support": min_support,
        "max_itemset_size": max_itemset_size,
        "patterns": itemsets[:top_n],
    }
