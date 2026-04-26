import os
import textwrap

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DEFAULT_LLM_MODEL = "llama-3.3-70b-versatile"
LLM_MODEL = os.getenv("LLM_MODEL", os.getenv("GROQ_MODEL", DEFAULT_LLM_MODEL))
MAX_CONTEXT_CHARS = 6000  # trim context fed to LLM to stay within token budget


# ─── prompt builder ───────────────────────────────────────────────────────────


def _build_prompt(question: str, chunks: list[dict]) -> str:
    """
    Build a grounded prompt from evidence chunks.
    Each chunk is numbered so the LLM can cite it easily.
    """
    if not chunks:
        context_block = "[No relevant policy sections were retrieved.]"
    else:
        sections = []
        running = 0
        for idx, chunk in enumerate(chunks, start=1):
            text = chunk.get("text", "").strip().replace("\n", " ")
            label = (
                f"[Source {idx} | chunk_id={chunk['chunk_id']} "
                f"| page {chunk.get('page_num', '?')}]"
            )
            entry = f"{label}\n{text}"
            if running + len(entry) > MAX_CONTEXT_CHARS:
                break
            sections.append(entry)
            running += len(entry)
        context_block = "\n\n".join(sections)

    prompt = textwrap.dedent(f"""
        You are an academic policy assistant for NUST
        (National University of Sciences and Technology).
        Answer the student's question using ONLY the policy sections provided below.
        If the answer is not found in the provided sections, say:
        "I could not find information about this in the provided policy documents.
        However, based on my general knowledge, and mention that this answer is
        not grounded in the provided sections."

        When you answer:
        - Be concise and direct.
        - Quote relevant rules or numbers exactly as they appear.
        - Cite the source number (e.g. [Source 1]) after any claim you make.

        ── Policy Sections ──────────────────────────────────────────────────────
        {context_block}
        ─────────────────────────────────────────────────────────────────────────

        Student question: {question}

        Answer:
    """).strip()

    return prompt


# ─── LLM call ────────────────────────────────────────────────────────────────


def _call_groq(prompt: str) -> tuple[str, str]:
    try:
        from groq import Groq  # lazy import

        model_name = (LLM_MODEL or "").strip() or DEFAULT_LLM_MODEL
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful academic policy assistant. "
                        "Answer only based on the provided context."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=600,
        )

        text = completion.choices[0].message.content or ""
        return text.strip(), model_name
    except Exception as exc:
        return f"[LLM error: {exc}]", "error"


def _fallback_answer(question: str, chunks: list[dict]) -> str:
    """Return a no-LLM answer using the top chunk's text directly."""
    if not chunks:
        return "No relevant policy sections were found for your question."
    top = chunks[0]
    snippet = top.get("text", "")[:800].strip()
    return (
        f"[No LLM key configured — showing top retrieved excerpt]\n\n"
        f"From page {top.get('page_num', '?')} (chunk {top['chunk_id']}):\n"
        f"{snippet}"
    )


# ─── public API ──────────────────────────────────────────────────────────────


def build_evidence(chunks: list[dict]) -> list[dict]:
    """
    Convert raw chunk dicts into clean evidence records for the API response.
    Keeps only what the consumer needs — avoids dumping 10 KB of text per chunk.
    """
    evidence = []
    for idx, c in enumerate(chunks, start=1):
        evidence.append(
            {
                "source_num": idx,
                "chunk_id": c.get("chunk_id"),
                "page_num": c.get("page_num"),
                "source": c.get("source", "unknown"),
                "score": round(c.get("score", 0.0), 4),
                # First 300 chars as a readable snippet.
                "snippet": c.get("text", "")[:300].strip(),
            }
        )
    return evidence


def generate_answer(question: str, chunks: list[dict]) -> dict:

    evidence = build_evidence(chunks)

    if not GROQ_API_KEY:
        answer = _fallback_answer(question, chunks)
        model = "none (no GROQ_API_KEY)"
    else:
        prompt = _build_prompt(question, chunks)
        answer, used_model = _call_groq(prompt)
        model = used_model

    return {
        "answer": answer,
        "evidence": evidence,
        "model": model,
    }
