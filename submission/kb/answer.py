"""Answer templates. Rate questions always get a resolved fact, a rule-6 listing that asks which
tier, or a refusal; other questions try entity claims, then long-tail retrieval."""

import re
from dataclasses import replace
from datetime import date

from contract import Answer, Source

from kb.answer_entities import entity_answer
from kb.extract.rates import YEAR_FAMILIES, named_on_product_pages
from kb.facts import Fact, Ledger, SnapshotFacts
from kb.longtail import long_tail_answer
from kb.normalize import fmt_pct
from kb.pages import LANDING
from kb.query import Query, as_of_from, normalize_synonyms, parse
from kb.resolve import Group, cite, groups, lookup, slot

REFUSAL = "It isn't listed; please contact us."
HARD_TAGS = {"jumbo", "special", "intro", "relief", "roth", "traditional", "variable", "arm"}
HIDDEN_UNLESS_ASKED = {"intro", "relief", "refinance"}
LIST_FAMILIES = {
    "certificate",
    "ira",
    "platinum_visa",
    "rewards_visa",
    "free_checking",
    "first_rate_checking",
}


def refuse() -> Answer:
    return Answer(text=REFUSAL, confident=False)


def eff_text(f: Fact) -> str:
    return f" (rates effective {f.effective:%m/%d/%Y})" if f.effective else ""


def sources(gs: list[Group]) -> list[Source]:
    out, seen = [], set()
    for g in gs:
        for f in cite(g):
            if f.url not in seen:
                seen.add(f.url)
                out.append(Source(url=f.url, snapshot_id=f.snapshot_id, quote=f.quote))
    return out[:4]


def stale_note(gs: list[Group]) -> str | None:
    """Competing values never go in the text (an answer that repeats one scores zero)."""
    by_value: dict[tuple, list[str]] = {}
    for g in gs:
        for f in g.losers:
            when = f"effective {f.effective:%m/%d/%Y}" if f.effective else "undated"
            by_value.setdefault((f.value, when), []).append(f.url)
    if not by_value:
        return None
    parts = [f"{v} ({w}) on {', '.join(dict.fromkeys(u))}" for (v, w), u in by_value.items()]
    return (
        f"Older tables still show {'; '.join(parts)}. The product page and rate sheet"
        f"{eff_text(gs[0].winner)} take precedence."
    )


_named: dict[tuple, bool] = {}


def expired(sf: SnapshotFacts, g: Group) -> bool:
    """Rule 4: an offer shown only on landing pages, PDFs or releases is expired unless a product
    page or rate sheet still names it."""
    w = g.winner
    if w.tier < LANDING:
        return False
    key = (sf.snapshot_id, w.family, w.variant, w.term)
    if key not in _named:
        _named[key] = named_on_product_pages(sf, w)
    return not _named[key]


def later_note(ledger: Ledger, sf: SnapshotFacts, g: Group, as_of: str | None) -> str | None:
    """A later crawl may show a different value effective on or before as_of: note it, never
    answer with it (decision log: as_of semantics)."""
    if not as_of:
        return None
    w, cutoff = g.winner, date.fromisoformat(as_of[:10])
    point = w.lo if w.hi == float("inf") else (w.lo + w.hi) / 2
    for s in (s for s in ledger.snapshots if s.taken_on > sf.taken_on):
        later = lookup(s.facts, slot(w), point)
        lw = later.winner if later else None
        if lw and lw.value != w.value and lw.effective and lw.effective <= cutoff:
            return (
                f"The {s.taken_on} crawl shows {lw.value} effective {lw.effective:%m/%d/%Y}, "
                f"on or before {as_of[:10]}; this answer uses the site as it stood then."
            )
    return None


def join_notes(*notes: str | None) -> str | None:
    return " ".join(n for n in notes if n) or None


def variant_ok(f: Fact, q: Query, family_tags: set[str]) -> bool:
    tags = set(f.variant.split())
    if q.business is not None and ("business" in tags) != q.business:
        return False
    if not (q.tags & HARD_TAGS) | (q.tags & family_tags) <= tags:
        return False
    if (tags & HIDDEN_UNLESS_ASKED) - q.tags or tags & q.excluded:
        return False
    return not (f.family == "mortgage" and "refinance" not in q.tags and "purchase" not in tags)


def primary_metric(facts: list[Fact]) -> str:
    metrics = {f.metric for f in facts}
    return next((m for m in ("APY", "rate", "APR") if m in metrics), "APR")


def row_key(f: Fact) -> tuple:
    return (f.family, f.variant, f.term, f.lo, f.hi)


def value_text(g: Group, companions: dict) -> str:
    w = g.winner
    other = companions.get(row_key(w), {})
    if w.metric == "APY":
        text = f"{w.value} APY" + (
            f" ({other['dividend']} dividend rate)" if "dividend" in other else ""
        )
        if "APY first 6 months" in other:
            intro = other.get("dividend first 6 months")
            text = (
                f"introductory {intro + ' dividend rate (' if intro else ''}"
                f"{other['APY first 6 months']} APY{')' if intro else ''} for the first 6 months, "
                f"then {text}"
            )
        return text
    if w.metric == "rate":
        return f"{w.value} rate" + (f" / {other['APR']} APR" if "APR" in other else "")
    return f"{w.value} {'intro ' if 'intro' in w.variant.split() else ''}APR"


def label_text(w: Fact) -> str:
    if w.family in YEAR_FAMILIES or (w.term and w.label.startswith("$")):
        return f"{w.label}, {w.term} months"
    if w.family in ("heloc", "home_equity_loan", "personal_loan") and w.term:
        return f"{w.term} months"
    if w.family in ("platinum_visa", "rewards_visa", "heloc") or w.label in ("", "-"):
        return ""
    # minimums only add information where tiers share a term (regular vs jumbo certificates)
    shown = w.minimum and w.family in ("certificate", "ira")
    return w.label + (f" ({w.minimum} minimum)" if shown else "")


RANGE_NAME = {"auto": "model year", "atv": "model year", "mortgage": "loan amount"}
RANGE_NAME |= {"boat_rv": "loan amount", "home_improvement": "loan amount"}


def missing_qualifier(rows: list[Group]) -> str:
    """Rule 6: name what the member still has to tell us."""
    missing = []
    if len({g.winner.variant for g in rows}) > 1 and rows[0].winner.family == "mortgage":
        missing.append("purchase or refinance")
    if len({(g.winner.lo, g.winner.hi) for g in rows}) > 1:
        missing.append(RANGE_NAME.get(rows[0].winner.family, "balance"))
    if len({g.winner.term for g in rows}) > 1:
        missing.append("term")
    if not missing:
        return ""
    return f" Which {' and '.join(missing)} {'apply' if len(missing) > 1 else 'applies'} to you?"


def merge_ira(rows: list[Group]) -> list[Group]:
    """Roth and Traditional IRA certificates usually share rates; show each shared rate once
    (label without the 'Roth:'/'Traditional:' prefix) and keep both when they differ."""

    def key(w: Fact, with_value: bool) -> tuple:
        tags = " ".join(t for t in w.variant.split() if t not in ("roth", "traditional"))
        return (tags, w.term, w.lo, w.hi) + ((w.value,) if with_value else ())

    values: dict[tuple, set[str]] = {}
    for g in rows:
        values.setdefault(key(g.winner, False), set()).add(g.winner.value)
    seen, out = set(), []
    for g in rows:
        w = g.winner
        if w.family != "ira":
            out.append(g)
        elif len(values[key(w, False)]) > 1:
            out.append(g)  # the two IRA types differ: keep the prefixed label
        elif key(w, True) not in seen:
            seen.add(key(w, True))
            out.append(
                Group(
                    replace(w, label=re.sub(r"^(Roth|Traditional):\s*", "", w.label)),
                    g.support,
                    g.losers,
                )
            )
    return out


def collapse_amounts(gs: list[Group], companions: dict) -> list[str]:
    """Mortgage headline: per term, the smallest loan-amount tier plus 'up to' the largest."""
    lines = []
    for term in sorted({g.winner.term or 0 for g in gs}, reverse=True):
        tier = sorted((g for g in gs if (g.winner.term or 0) == term), key=lambda g: g.winner.hi)
        first, last = tier[0], tier[-1]
        line = f"{first.winner.label}: {value_text(first, companions)}"
        if last is not first:
            line += (
                f", up to {value_text(last, companions)} for loans of "
                f"${last.winner.hi:,.0f} or less"
            )
        lines.append(line)
    return lines


def family_rows(sf: SnapshotFacts, q: Query, family: str):
    """The current rows of one family that match the question, plus companion values."""
    fam_facts = [f for f in sf.facts if f.family == family]
    family_tags = {t for f in fam_facts for t in f.variant.split()}
    facts = [f for f in fam_facts if variant_ok(f, q, family_tags)]
    metric = primary_metric(facts)
    comp: dict[tuple, dict[str, str]] = {}
    for g in groups([f for f in facts if f.metric != metric]):
        comp.setdefault(row_key(g.winner), {})[g.winner.metric] = g.winner.value
    rows = [
        g
        for g in groups([f for f in facts if f.metric == metric])
        if not expired(sf, g)
        and (q.term is None or g.winner.term == q.term)
        and (q.amount is None or g.winner.lo <= q.amount <= g.winner.hi)
    ]
    if family == "mortgage" and q.term is None and q.amount is None:
        rows = [g for g in rows if g.winner.term in (180, 360)]  # decision log: headline
    if q.superlative and rows:
        pick = max if q.superlative == "max" else min
        rows = [pick(rows, key=lambda g: g.winner.num)]
    rows.sort(key=lambda g: (g.winner.variant, -(g.winner.term or 0), -g.winner.lo))
    return merge_ira(rows), comp


def rate_answer(ledger: Ledger, sf: SnapshotFacts, q: Query, as_of: str | None) -> Answer:
    if not q.families:
        return refuse()  # a rate question about a product with no rate on the site
    if q.families == ["auto"]:
        return auto_answer(q, sf, ledger, as_of)
    texts, used, all_rows = [], [], []
    for family in q.families:
        rows, comp = family_rows(sf, q, family)
        if not rows:
            continue
        all_rows += rows
        used.append(rows[0])
        if family == "mortgage" and q.amount is None and len(rows) > 1:
            lines = collapse_amounts(rows, comp)
        else:
            one_product = len({g.winner.product for g in rows}) == 1
            lines = [
                ": ".join(
                    x
                    for x in (
                        label_text(g.winner)
                        if one_product
                        else f"{g.winner.product} {label_text(g.winner)}".strip(),
                        value_text(g, comp),
                    )
                    if x
                )
                for g in rows
            ]
        product = rows[0].winner.product
        prefix = f"{product}: " if len({g.winner.product for g in rows}) == 1 else ""
        texts.append(f"{prefix}{'; '.join(lines)}{eff_text(rows[0].winner)}.")
    if not all_rows:
        return refuse()
    if q.intent == "rate_link":
        url = cite(used[0])[0].url
        text = f"{used[0].winner.product} rates are listed at {url}"
        return Answer(text=text, sources=sources(used))
    text = " ".join(texts)
    if q.percent is not None and not any(g.winner.num == q.percent for g in all_rows):
        others = [
            f"{g.winner.product} ({g.winner.label})"
            for g in groups([f for f in sf.facts if "business" not in f.variant])
            if g.winner.num == q.percent and g.winner.metric in ("APY", "APR", "rate")
        ]
        text = f"No {used[0].winner.product} tier pays {fmt_pct(q.percent)}. {text}"
        if others:
            text += f" {fmt_pct(q.percent)} is the rate for {', '.join(dict.fromkeys(others))}."
    listed = set(q.families) & LIST_FAMILIES
    if len(all_rows) > 1 and not (q.superlative or listed or q.amount is not None or q.percent):
        text += missing_qualifier(all_rows)
    note = stale_note(all_rows)
    if len(all_rows) == 1:
        note = join_notes(note, later_note(ledger, sf, all_rows[0], as_of))
    return Answer(text=text, sources=sources(used), conflict_note=note)


def article(term: int) -> str:
    return "An" if str(term).startswith("8") or term in (11, 18) else "A"


def auto_answer(q: Query, sf: SnapshotFacts, ledger: Ledger, as_of: str | None) -> Answer:
    facts = [f for f in sf.facts if f.family == "auto" and f.variant == ""]
    rows = groups(facts)
    if not rows:
        return refuse()
    year = q.year or (max(g.winner.hi for g in rows) if q.newest else None)
    if year and q.term:
        g = lookup(facts, ("auto", "", "APR", q.term), year)
        if g:
            w = g.winner
            eff = f", rates effective {w.effective:%m/%d/%Y}" if w.effective else ""
            text = (
                f"{article(q.term)} {q.term}-month auto loan on a {year} model-year vehicle is "
                f"{w.value} APR ({w.label} tier{eff})."
            )
            note = join_notes(stale_note([g]), later_note(ledger, sf, g, as_of))
            return Answer(text=text, sources=sources([g]), conflict_note=note)
    if year:
        tier = sorted(
            (g for g in rows if g.winner.lo <= year <= g.winner.hi), key=lambda g: g.winner.term
        )
        if tier:
            w = tier[0].winner
            terms = ", ".join(f"{g.winner.term} months {g.winner.value} APR" for g in tier)
            text = (
                f"For a {year} model-year vehicle ({w.label} tier): {terms}{eff_text(w)}. "
                "Which term are you considering?"
            )
            return Answer(text=text, sources=sources(tier[:1]), conflict_note=stale_note(tier))
    if q.term:
        by_age = sorted((g for g in rows if g.winner.term == q.term), key=lambda g: -g.winner.hi)
        if by_age:
            lead, last = by_age[0].winner, by_age[-1].winner
            text = (
                f"{article(q.term)} {q.term}-month auto loan is {lead.value} APR "
                f"for {lead.label} vehicles"
            )
            if last is not lead:
                text += f", up to {last.value} APR for {last.label}"
            text += f"{eff_text(lead)}. Which model year is the vehicle?"
            return Answer(text=text, sources=sources(by_age[:1]), conflict_note=stale_note(by_age))
    lo = min(rows, key=lambda g: g.winner.num)
    hi = max(rows, key=lambda g: g.winner.num).winner
    text = (
        f"Auto loan rates start at {lo.winner.value} APR ({lo.winner.term} months, "
        f"{lo.winner.label}) and go up to {hi.value} APR ({hi.label}){eff_text(lo.winner)}. "
        "Which model year and term?"
    )
    return Answer(text=text, sources=sources([lo]), conflict_note=stale_note([lo]))


def answer(ledger: Ledger, question: str, as_of: str | None = None) -> Answer:
    as_of = as_of or as_of_from(question)  # the as_of field wins over a date in the question
    question = normalize_synonyms(question)
    sf = ledger.at(as_of)
    if sf is None:  # rule 1: nothing before the first snapshot
        return refuse()
    q = parse(question)
    if q.intent in ("rate", "rate_link"):
        if sf.index is not None and sf.index.unseen_product(question):
            return refuse()  # e.g. a reverse mortgage: the site never names that product
        return rate_answer(ledger, sf, q, as_of)
    return entity_answer(sf, question, as_of) or long_tail_answer(sf, question)
