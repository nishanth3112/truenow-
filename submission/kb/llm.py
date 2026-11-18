"""Optional OpenAI composer for long-tail answers. Opt-in and unevaluated: it runs only when
KB_USE_LLM=1 and OPENAI_API_KEY is set. Every number in its answer must appear in the question or
the excerpts and must not be a value the resolver superseded; otherwise the caller keeps the
extractive answer.
"""

import os
import re
from collections.abc import Callable

TIMEOUT_S = 6.0
NOT_FOUND = "NOT_FOUND"
INSTRUCTIONS = (
    "You answer a credit union member's question using only the numbered website excerpts. "
    "Answer in one to three plain sentences. Copy every number, rate, date, phone number and URL "
    "exactly as written in the excerpts. If the excerpts do not answer the question, reply with "
    f"exactly {NOT_FOUND}."
)
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

_client = None  # tests may set this to a fake with .responses.create(...)
_cache: dict[tuple[str, str], str | None] = {}
_no_temperature = False  # set if the model rejects temperature on the first call


def enabled() -> bool:
    """Opt-in: the extractive path is the measured default (decision log, 2026-11-18)."""
    return os.environ.get("KB_USE_LLM") == "1" and bool(os.environ.get("OPENAI_API_KEY") or _client)


def numbers(text: str) -> set[float]:
    return {float(n.replace(",", "")) for n in NUMBER.findall(text or "")}


def grounded(answer: str, question: str, excerpts: list[str], superseded: set[float]) -> bool:
    """Number guard: nothing absent from the question and excerpts, nothing superseded."""
    allowed = numbers(question) | set().union(*(numbers(e) for e in excerpts))
    got = numbers(answer)
    return got <= allowed and not (got & superseded)


def _get_client():
    global _client
    if _client is None:
        import openai  # lazy: the system runs without the package being imported

        _client = openai.OpenAI(timeout=TIMEOUT_S, max_retries=0)
    return _client


def _call(question: str, excerpts: list[str]) -> str:
    global _no_temperature
    body = "\n\n".join(f"[{i + 1}] {e}" for i, e in enumerate(excerpts))
    kwargs = {
        "model": os.environ.get("KB_LLM_MODEL", "gpt-6-luna"),
        "instructions": INSTRUCTIONS,
        "input": f"Excerpts:\n{body}\n\nQuestion: {question}",
        "reasoning": {"effort": os.environ.get("KB_LLM_EFFORT", "none")},
        "max_output_tokens": 300,
        "timeout": TIMEOUT_S,
    }
    if not _no_temperature:
        kwargs["temperature"] = 0
    try:
        resp = _get_client().responses.create(**kwargs)
    except Exception as e:  # the only retry: a model that does not accept temperature
        if _no_temperature or "temperature" not in str(e).lower():
            raise
        _no_temperature = True
        kwargs.pop("temperature")
        resp = _get_client().responses.create(**kwargs)
    return (resp.output_text or "").strip()


def compose(
    question: str,
    excerpts: list[str],
    snapshot_id: str,
    superseded: Callable[[str], set[float]],
) -> str | None:
    """The model's grounded answer, NOT_FOUND, or None (disabled, failed, timed out or
    ungrounded) so the caller falls back to the extractive answer. superseded(text) gives the
    stale values of the products that text names."""
    if not enabled() or not excerpts:
        return None
    key = (" ".join(question.lower().split()), snapshot_id)
    if key not in _cache:
        try:
            text = _call(question, excerpts)
        except Exception:  # timeout, network or API error: the extractive answer stands
            text = None
        stale = superseded(f"{question} {text}") if text else set()
        if text and text != NOT_FOUND and not grounded(text, question, excerpts, stale):
            text = None
        _cache[key] = text
    return _cache[key]
