"""Long tail: an extractive answer from the best retrieved sentences, or an honest refusal."""

import re

from contract import Answer, Source

from kb import llm
from kb.extract.rates import CATALOG
from kb.facts import SnapshotFacts
from kb.resolve import groups
from kb.retrieval import Index, tokens

REFUSAL = "It isn't listed; please contact us."
# Calibrated on the dev refusal probe (SWIFT code: unseen word, coverage 0.36) and the dev
# long-tail items (lowest coverage 0.40, wordy, no unseen word; lowest top score 7.1).
MIN_SCORE = 3.0  # below this the best chunk shares almost nothing with the question
MIN_COVER = 0.5  # with a word the site never uses, the evidence must cover this share of the rest
TOP_K = 5
NOT_NAMES = {"dupaco", "dupaco's", "dupaco’s", "i", "i'm", "i’m", "i'd", "i’ve", "i've"}
MAX_CHARS = 450


def refuse() -> Answer:
    return Answer(text=REFUSAL, confident=False)


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z“\"])|\s+-\s+(?=[A-Z])", text)
    return [p.strip(" -") for p in parts if len(p.strip()) > 15]


def evidence(index: Index, question: str):
    """(score, (page rank, position), chunk, sentence index, sentences, covered terms, own terms,
    retrieval rank) for the top chunks. A sentence is scored with its chunk heading (ties go to
    the sentence that holds more of the question itself); quoted remarks rank below prose."""
    q = set(tokens(question))
    out, page_rank = [], {}
    for raw, (_, chunk, _) in enumerate(index.search(question, TOP_K)):
        rank = page_rank.setdefault(chunk.url, raw)  # chunks of one page compete by position
        sents = sentences(chunk.text)
        head = set(tokens(chunk.heading))
        for i, s in enumerate(sents):
            own = q & set(tokens(s))
            covered = own | (q & head)
            score = sum(index.idf.get(t, 0.0) for t in covered)
            if s.startswith(("“", '"')):
                score *= 0.9
            out.append((score, (rank, chunk.pos), chunk, i, sents, covered, len(own), raw))
    return out


_losers: dict[str, list] = {}


def superseded(sf: SnapshotFacts, text: str) -> set[float]:
    """Values the resolver ruled stale for any product the text names (minus current values)."""
    if sf.snapshot_id not in _losers:
        _losers[sf.snapshot_id] = groups(sf.facts)
    named = {p.family for p in CATALOG if re.search(p.pattern.pattern.replace("^", ""), text, re.I)}
    gs = [g for g in _losers[sf.snapshot_id] if g.winner.family in named]
    current = {g.winner.num for g in gs}
    return {f.num for g in gs for f in g.losers} - current


def coverage(index: Index, question: str, score: float) -> float:
    """Share of the question's idf mass that the chosen evidence covers. Words the site never
    uses count at the highest idf: asking about them is asking about something not listed."""
    top = max(index.idf.values(), default=1.0)
    mass = sum(index.idf.get(t, top) for t in dict.fromkeys(tokens(question))) or 1.0
    return score / mass


def names(question: str) -> list[str]:
    """Capitalised names inside a question ('Zelle', 'Apple Pay'), not its first word."""
    words = re.findall(r"[A-Za-z][\w$'’&-]*", question)[1:]
    return [w for w in words if w[0].isupper() and not w.isupper() and w.lower() not in NOT_NAMES]


def long_tail_answer(sf: SnapshotFacts, question: str) -> Answer:
    index, snapshot_id = sf.index, sf.snapshot_id
    if index.unseen_product(question):
        return refuse()
    hits = index.search(question, TOP_K)
    if not hits or hits[0][0] < MIN_SCORE:
        return refuse()
    cands = evidence(index, question)
    score, _, chunk, i, sents, covered, *_ = min(cands, key=lambda c: (-c[0], -c[6], c[1], c[3]))
    if index.unseen(question) and coverage(index, question, score) < MIN_COVER:
        return refuse()  # the best sentence misses most of what was asked (e.g. a SWIFT code)
    text = " ".join(sents[i : i + 2])
    if (
        chunk.heading
        and not chunk.heading.startswith("http")
        and chunk.heading.lower() not in text.lower()
    ):
        text = f"{chunk.heading.strip('*')}: {text}"
    sources = [Source(url=chunk.url, snapshot_id=snapshot_id, quote=sents[i][:200])]
    # a second chunk's sentence joins only if it adds a fifth of the question's weight
    mass = sum(index.idf.get(t, 0.0) for t in set(tokens(question))) or 1.0
    gain = lambda c: sum(index.idf.get(t, 0.0) for t in c[5] - covered)  # noqa: E731
    others = [c for c in cands if c[2] is not chunk and gain(c) >= 0.2 * mass]
    if others:
        extra = min(others, key=lambda c: (-gain(c), c[7], c[3]))
        text += " " + extra[4][extra[3]]
        sources.append(
            Source(url=extra[2].url, snapshot_id=snapshot_id, quote=extra[4][extra[3]][:200])
        )
    missing = [n for n in names(question) if n.lower() not in f"{chunk.heading} {text}".lower()]
    if missing:
        return refuse()  # the question names something (a brand, a service) the evidence never does
    excerpts = [f"{c.heading}: {c.text}" for _, c, _ in hits[:3]]
    composed = llm.compose(question, excerpts, snapshot_id, lambda t: superseded(sf, t))
    if composed == llm.NOT_FOUND:
        return refuse()
    if composed:
        top = [c for _, c, _ in hits[:3]]
        return Answer(
            text=composed, sources=[Source(url=c.url, snapshot_id=snapshot_id) for c in top]
        )
    if len(text) > MAX_CHARS:
        text = text[: text.rfind(" ", 0, MAX_CHARS)] + " …"
    return Answer(text=text, sources=sources)
