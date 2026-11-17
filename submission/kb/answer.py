"""Answer templates: structured path for known intents, naive retrieval for everything else."""

import re

from contract import Answer, Source

from kb.facts import Fact, Ledger, SnapshotFacts
from kb.query import parse
from kb.resolve import Group, cite, groups, lookup

REFUSAL = "It isn't listed; please contact us."
WORD = re.compile(r"[a-z0-9$%.]+")


def refuse() -> Answer:
    return Answer(text=REFUSAL, confident=False)


def pct(v: float) -> str:
    return f"{v:.2f}%"


def sources(g: Group) -> list[Source]:
    return [Source(url=f.url, snapshot_id=f.snapshot_id, quote=f.quote) for f in cite(g)]


def effective(f: Fact) -> str:
    return f", rates effective {f.effective:%m/%d/%Y}" if f.effective else ""


def stale_note(gs: list[Group]) -> str | None:
    """Competing values never go in the text (an answer that repeats one scores zero)."""
    by_value: dict[tuple, list[str]] = {}
    for g in gs:
        for f in g.losers:
            when = f"effective {f.effective:%m/%d/%Y}" if f.effective else "undated"
            by_value.setdefault((pct(f.value), when), []).append(f.url)
    if not by_value:
        return None
    parts = [
        f"{v} ({when}) on {', '.join(dict.fromkeys(urls))}" for (v, when), urls in by_value.items()
    ]
    w = gs[0].winner
    eff = f" (rates effective {w.effective:%m/%d/%Y})" if w.effective else ""
    return (
        f"Older tables still show {'; '.join(parts)}. "
        f"The auto loan page and rate sheet{eff} take precedence."
    )


def article(term: int) -> str:
    return "An" if str(term).startswith("8") or term in (11, 18) else "A"


def auto_answer(question: str, sf: SnapshotFacts) -> Answer:
    q = parse(question)
    facts = [f for f in sf.facts if f.family == "auto"]
    rows = [g for g in groups(facts)]
    if not rows:
        return refuse()
    year = q.year or (max(g.winner.hi for g in rows) if q.newest else None)
    if year and q.term:
        g = lookup(facts, "auto", "APR", q.term, year)
        if g:
            w = g.winner
            text = (
                f"{article(q.term)} {q.term}-month auto loan on a {year} model-year vehicle is "
                f"{pct(w.value)} APR ({w.label} tier{effective(w)})."
            )
            return Answer(text=text, sources=sources(g), conflict_note=stale_note([g]))
    if year:
        tier = sorted(
            (g for g in rows if g.winner.lo <= year <= g.winner.hi), key=lambda g: g.winner.term
        )
        if tier:
            w = tier[0].winner
            terms = ", ".join(f"{g.winner.term} months {pct(g.winner.value)} APR" for g in tier)
            text = (
                f"For a {year} model-year vehicle ({w.label} tier): {terms}{effective(w)}. "
                "Which term are you considering?"
            )
            return Answer(text=text, sources=sources(tier[0]), conflict_note=stale_note(tier))
    if q.term:
        by_age = sorted((g for g in rows if g.winner.term == q.term), key=lambda g: -g.winner.hi)
        if by_age:
            lead, last = by_age[0].winner, by_age[-1].winner
            text = (
                f"{article(q.term)} {q.term}-month auto loan is {pct(lead.value)} APR "
                f"for {lead.label} vehicles"
            )
            if last is not lead:
                text += f", up to {pct(last.value)} APR for {last.label}"
            text += f"{effective(lead)}. Which model year is the vehicle?"
            return Answer(text=text, sources=sources(by_age[0]), conflict_note=stale_note(by_age))
    lo = min(rows, key=lambda g: g.winner.value).winner
    hi = max(rows, key=lambda g: g.winner.value).winner
    text = (
        f"Auto loan rates start at {pct(lo.value)} APR ({lo.term} months, {lo.label}) and go up to "
        f"{pct(hi.value)} APR ({hi.label}){effective(lo)}. Which model year and term?"
    )
    first = min(rows, key=lambda g: g.winner.value)
    return Answer(text=text, sources=sources(first), conflict_note=stale_note([first]))


def naive_answer(question: str, sf: SnapshotFacts) -> Answer:
    """Placeholder long tail (replaced in Phase 4): the paragraph sharing the most words."""
    q = set(WORD.findall(question.lower()))
    best, best_score = None, 0
    for url, page in sf.pages.items():
        for para in page.markdown.split("\n\n"):
            s = len(q & set(WORD.findall(para.lower())))
            if s > best_score:
                best, best_score = (url, para.strip()), s
    if not best:
        return refuse()
    url, para = best
    return Answer(text=para[:600], sources=[Source(url=url, snapshot_id=sf.snapshot_id)])


def answer(ledger: Ledger, question: str, as_of: str | None = None) -> Answer:
    sf = ledger.at(as_of)
    if sf is None:  # rule 1: nothing before the first snapshot
        return refuse()
    if parse(question).intent == "auto_rate":
        return auto_answer(question, sf)
    return naive_answer(question, sf)
