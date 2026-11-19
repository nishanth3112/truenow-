"""Answers from non-rate claims: identifiers, links, branch addresses, hours, closures, counts and
recognitions. Returns None when the question is not one of these, so retrieval can try."""

import re
from collections import Counter
from datetime import date, datetime

from contract import Answer, Source

from kb.facts import Claim, SnapshotFacts
from kb.query import DATE_PHRASE

REFUSAL = "It isn't listed; please contact us."
STOP = set(
    "a an the of to for in on at by and or is are was were be do does did have has had i you your "
    "we our my me what which who when where how many much can could would should will dupaco "
    "dupaco's it its this that there their with from about any all".split()
)
# "the Galena branch", "the old Hy-Vee location", "the Asbury office"
BRANCH = re.compile(
    r"((?:[A-Z][\w.'’-]*\s+)*[A-Z][\w.'’-]*)\s+(?:[Bb]ranch|[Ll]ocation|[Oo]ffice)\b"
)


def refuse() -> Answer:
    return Answer(text=REFUSAL, confident=False)


def cite(claims: list[Claim], n: int = 3) -> list[Source]:
    """Product pages before landing pages and releases, one source per URL."""
    order = sorted(claims, key=lambda c: ("/newsroom/" in c.url, c.url.count("/") <= 3, c.url))
    urls = list(dict.fromkeys(c.url for c in order))[:n]
    first = {c.url: c for c in reversed(order)}
    return [
        Source(url=u, snapshot_id=first[u].snapshot_id, quote=first[u].quote[:200]) for u in urls
    ]


def when(c: Claim) -> str:
    d = c.published
    return f"{d:%B} {d.day}, {d.year}" if d else "an undated page"


def branch_words(question: str) -> list[str]:
    """'the Mullan Avenue branch' -> ['mullan', 'avenue']."""
    m = BRANCH.search(question)
    if not m:
        return []
    return [w.lower() for w in re.findall(r"[\w’'-]+", m[1]) if w.lower() not in STOP]


ABBR = {"street": "st", "avenue": "ave", "road": "rd", "drive": "dr", "boulevard": "blvd"}
ABBR |= {"lane": "ln", "court": "ct", "highway": "hwy", "north": "n", "south": "s"}


def _abbr(word: str) -> str:
    return ABBR.get(word.lower().rstrip("."), word.lower().rstrip("."))


def matches(words: list[str], text: str) -> bool:
    """All words appear in text, comparing 'Street' with 'St.' and so on."""
    have = {_abbr(w) for w in re.findall(r"[\w’'-]+", text)}
    return all(_abbr(w) in have for w in words)


def most_common(claims: list[Claim], kind: str) -> tuple[str, list[Claim]] | None:
    hits = [c for c in claims if c.kind == kind]
    if not hits:
        return None
    value = Counter(c.value for c in hits).most_common(1)[0][0]
    return value, [c for c in hits if c.value == value]


def site_fact(sf: SnapshotFacts, kind: str, template: str) -> Answer | None:
    found = most_common(sf.claims, kind)
    if not found:
        return refuse()
    value, claims = found
    return Answer(text=template.format(value), sources=cite(claims))


def closure_answer(
    sf: SnapshotFacts, question: str, words: list[str], as_of: str | None
) -> Answer | None:
    closures = [c for c in sf.claims if c.kind == "closure" and matches(words, c.subject)]
    if not closures:
        return None
    c = max(closures, key=lambda c: c.published or date.min)
    closes = datetime.strptime(
        re.sub(r"(\w{3})\w*\.?", r"\1", c.value, count=1), "%b %d, %Y"
    ).date()
    today = date.fromisoformat((as_of or sf.taken_on)[:10])
    verb = "closed on" if closes <= today else "is scheduled to close on"
    asks_open = re.search(r"still open|open today|still bank", question, re.I)
    text = (
        "No. " if asks_open and closes <= today else ""
    ) + f"The {c.subject} branch {verb} {c.value}"
    alts = [a for a in sf.claims if a.kind == "closure_alternative" and a.subject == c.subject]
    if alts:
        text += f"; members can use the full-service branches at {alts[0].value}"
    text += f" (Dupaco newsroom, {when(c)})."
    return Answer(text=text, sources=cite([c, *alts]))


def with_locator(sf: SnapshotFacts, sources: list[Source]) -> list[Source]:
    """Hours come from opening releases; the branch locator follows them as a source."""
    found = most_common(sf.claims, "locator_url")
    if found and found[0] not in {s.url for s in sources}:
        sources = [*sources, Source(url=found[0], snapshot_id=sf.snapshot_id)]
    return sources


def eligibility_answer(sf: SnapshotFacts) -> Answer:
    found = most_common(sf.claims, "eligibility")
    if not found:
        return refuse()
    value, claims = found
    criteria = [c[0].lower() + c[1:] for c in value.split("; ")]
    listed = (
        criteria[0] if len(criteria) == 1 else "; ".join(criteria[:-1]) + "; or " + criteria[-1]
    )
    text = f"You're eligible to join Dupaco if: {listed}."
    region = most_common([c for c in sf.claims if c.url == claims[0].url], "region")
    if region:
        text += f" Dupaco's locations are in {region[0]}."
    return Answer(text=text, sources=cite(claims))


def hours_answer(sf: SnapshotFacts, question: str, words: list[str]) -> Answer:
    section = "drive-up" if re.search(r"drive", question, re.I) else "lobby"
    claims = [c for c in sf.claims if c.kind == "hours" and c.key == section]
    if words:
        claims = [c for c in claims if matches(words, c.subject)]
        if not claims:
            return refuse()  # no schedule names that branch: never guess
    claims.sort(key=lambda c: c.published or date.min, reverse=True)
    by_schedule: dict[str, list[Claim]] = {}
    for c in claims:
        by_schedule.setdefault(c.value, []).append(c)
    if not by_schedule:
        return refuse()
    label = "Lobby" if section == "lobby" else "Drive-up"
    if len(by_schedule) == 1 and words:
        ((value, cs),) = by_schedule.items()
        text = (
            f"{label} hours at the {cs[0].subject}: {value} (opening announcement, {when(cs[0])})."
        )
        return Answer(text=text, sources=with_locator(sf, cite(cs)))
    parts = [f"{' and '.join(c.subject for c in cs)}: {value}" for value, cs in by_schedule.items()]
    lead = (
        "No, they differ by branch. "
        if re.search(r"\bsame\b|\bevery\b|\ball\b", question, re.I)
        else ""
    )
    text = (
        f"{lead}{label} hours vary by branch. From Dupaco's branch opening announcements: "
        f"{' | '.join(parts)}. Which branch are you asking about?"
    )
    return Answer(text=text, sources=with_locator(sf, cite(claims)))


def address_answer(sf: SnapshotFacts, words: list[str]) -> Answer:
    hits = [c for c in sf.claims if c.kind == "address" and matches(words, c.value)]
    branch = [c for c in hits if c.key == "branch"] or hits
    if not branch:
        return refuse()
    value = Counter(c.value for c in branch).most_common(1)[0][0]
    claims = [c for c in branch if c.value == value]
    name = " ".join(w.capitalize() for w in words)
    return Answer(text=f"The {name} branch is at {value}.", sources=cite(claims))


def stem(word: str) -> str:
    """'branches' -> 'branch', 'employees' -> 'employe', 'locations' -> 'location'."""
    if word.endswith("es") and len(word) > 4:
        return word[:-2]
    return word[:-1] if word.endswith("s") else word


def content_words(text: str) -> set[str]:
    return {stem(w) for w in re.findall(r"[a-z]+", text.lower()) if w not in STOP}


APPROX = re.compile(r"\b(over|nearly|about|almost|approximately|roughly|more than)\s+$", re.I)
RELATIVE = [(r"\b(last|previous|past) year\b", -1), (r"\bthis year\b", 0)]


def clause(sentence: str, limit: int = 140) -> str:
    """The sentence up to its first clause break after `limit` characters at most."""
    if len(sentence) <= limit:
        return sentence
    cut = max(sentence.rfind(", ", 0, limit), sentence.rfind(" (", 0, limit))
    return sentence[:cut] if cut > 40 else sentence[:limit].rsplit(" ", 1)[0]


def head_noun(question: str) -> str | None:
    """'how many volunteer hours ...' -> 'hour'; 'how many Dupaco employees used' -> 'employe'."""
    m = re.search(r"how many\s+((?:[\w-]+\s+){0,2}[\w-]+)", question, re.I)
    if not m:
        return None
    words = [w.lower() for w in m[1].split() if w.lower() not in ("dupaco", "dupaco's")]
    plural = next((w for w in words if w.endswith("s") and not w.endswith("ss")), None)
    return stem(plural or words[0]) if words else None


def count_answer(sf: SnapshotFacts, question: str, as_of: str | None) -> Answer | None:
    """'How many X ...': release sentences that put a number on X. A named year gets that year's
    figure only; a relative year the site does not report gets the two latest reported years;
    otherwise the newest release wins (rule 4). Ties go to the sentence sharing the most words
    with the question, then to exact figures over approximate ones ('over 7,200')."""
    q = DATE_PHRASE.sub(" ", question)
    head = head_noun(q)
    if not head:
        return None
    others = content_words(q) - {head, "many", "how"}
    number = re.compile(
        rf"(?<![\d,])(?!(?:19|20)\d\d\b)\d[\d,]*\**\s+(?:[\w-]+\s+){{0,2}}{re.escape(head)}", re.I
    )
    cands = []
    for c in sf.claims:
        m = number.search(c.value) if c.kind == "sentence" else None
        if m:
            exact = not APPROX.search(c.value[: m.start()])
            cands.append((len(others & content_words(c.value)), exact, c.published or date.min, c))
    if not cands:
        return None
    best_overlap = max(x[0] for x in cands)
    on_topic = [x for x in cands if x[0] >= max(1, best_overlap - 1)] or cands

    def answer_for(pool, one_year=False):
        # within one year every candidate is on topic: an exact figure beats "over 7,200"
        key = (lambda x: (x[1], x[0], x[2])) if one_year else (lambda x: x[:3])
        best = max(pool, key=key)[3]
        lead = f"In {best.key}: " if best.key and best.key not in best.value else ""
        return best, f"{lead}{clause(best.value)} (Dupaco newsroom, {when(best)})"

    stated = re.search(r"\b((?:19|20)\d\d)\b", q)
    ref = int((as_of or sf.taken_on)[:4])
    target = (
        stated[1]
        if stated
        else next((str(ref + d) for pat, d in RELATIVE if re.search(pat, q, re.I)), None)
    )
    if re.search(r"\b(most recent|latest)\b", q, re.I) and not stated:
        years = sorted({x[3].key for x in on_topic if x[3].key})
        target = years[-1] if years else None
    if target is None:
        best, text = answer_for(cands)
        return Answer(text=text, sources=cite([best]))
    pool = [x for x in on_topic if x[3].key == target]
    if pool:
        best, text = answer_for(pool, one_year=True)
        return Answer(text=text, sources=cite([best]))
    years = sorted({x[3].key for x in on_topic if x[3].key}, reverse=True)[:2]
    if not years:
        return refuse()
    found = [answer_for([x for x in on_topic if x[3].key == y], one_year=True) for y in years]
    listed = "; ".join(
        t if t.startswith("In ") else f"In {y}: {t}" for y, (_, t) in zip(years, found, strict=True)
    )
    text = f"The site doesn't give a {target} figure. Latest reported: {listed}"
    return Answer(text=text, sources=cite([b for b, _ in found]))


def recognition_answer(sf: SnapshotFacts, question: str) -> Answer | None:
    """The newest release sentence naming the organization with an ordinal ('fifth time')."""
    orgs = [w for w in re.findall(r"\b[A-Z][\w&]+", question) if w.lower() not in STOP]
    if not orgs:
        return None
    ordinal = re.compile(
        r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b", re.I
    )
    cands = [
        c
        for c in sf.claims
        if c.kind == "sentence" and ordinal.search(c.value) and any(o in c.value for o in orgs)
    ]
    if not cands:
        return None
    best = max(cands, key=lambda c: c.published or date.min)
    same = [c for c in sf.claims if c.kind == "sentence" and c.url == best.url]
    i = same.index(best)
    lead = same[i - 1].value + " " if i and any(o in same[i - 1].value for o in orgs) else ""
    text = f"{lead}{best.value} (Dupaco newsroom, {when(best)})"
    return Answer(text=text, sources=cite([best]))


def entity_answer(sf: SnapshotFacts, question: str, as_of: str | None) -> Answer | None:
    q = question
    words = branch_words(q)
    if words and re.search(
        r"clos|still open|open today|still bank|instead|members go|full-service|took over|replac|"
        r"alternative",
        q,
        re.I,
    ):
        found = closure_answer(sf, q, words, as_of)
        if found:
            return found
    if re.search(r"\bhow many\b", q, re.I):  # "how many volunteer hours" is a count, not hours
        return count_answer(sf, q, as_of)
    if re.search(
        r"\bhours?\b|\blobb(y|ies)\b.*\bopen\b|\bdrive.?(up|thru|through)\b.*\b(open|close)",
        q,
        re.I,
    ):
        return hours_answer(sf, q, words)
    if re.search(r"routing|\baba\b", q, re.I):
        return site_fact(sf, "routing", "Dupaco's routing number is {}.")
    if re.search(
        r"(update|change).{0,40}(contact|phone|address|email)|phone number|call you", q, re.I
    ):
        return site_fact(
            sf, "phone", "Call Dupaco at {} to update or confirm your contact details."
        )
    if words and re.search(r"address|located|where is", q, re.I):
        return address_answer(sf, words)
    if re.search(r"locator|finder|find (a|an|the) (branch|atm)|branch(es)? (and|&) atm", q, re.I):
        return site_fact(sf, "locator_url", "Find Dupaco branches and ATMs at {}")
    if re.search(r"eligib|who can join|qualif|requirements? to (join|become)|can i join", q, re.I):
        return eligibility_answer(sf)
    if re.search(r"\bjoin\b|membership|become a member", q, re.I) and not re.search(
        r"eligib|who can|qualif", q, re.I
    ):
        return site_fact(sf, "join_url", "You can join Dupaco online at {}")
    if re.search(r"recogni|award|rank|honor|forbes", q, re.I):
        found = recognition_answer(sf, q)
        if found:
            return found
    return None
