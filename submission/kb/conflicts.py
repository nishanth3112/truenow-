"""Contradictions the site showed on some day: one conflict per fact, across every snapshot.

Rate facts: a slot whose pages disagreed within a snapshot (a stale copy beside the current
value). Older snapshots' slots attach to the current slot they overlap most, so one fact keeps one
conflict however its label drifted ('2023-26' -> '2024-27'). Dated claims: release sentences that
say the same thing about a number ('... 22 branch office locations') with different numbers.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from contract import Conflict, Source

from kb.facts import Claim, Fact, Ledger
from kb.pages import LANDING, OTHER_PRODUCT, OWNER, PDF
from kb.resolve import Group, cite, groups, overlap, same_slot

TIER_NAME = {
    OWNER: "the product page and rate sheet",
    OTHER_PRODUCT: "another product page",
    PDF: "a PDF",
    LANDING: "a landing or calculator page",
}
# A row's rate and APR (or dividend and APY) move together; one conflict per row is enough.
REPORTED_METRICS = {"APR", "APY"}
CAP = 40
ORDINALS = "first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth"


def _when(f: Fact) -> str:
    return f"effective {f.effective:%m/%d/%Y}" if f.effective else "no effective date"


def topic(w: Fact) -> str:
    parts = [f"{w.product} {w.metric}", w.label]
    if w.term and w.family != "mortgage":  # mortgage labels already name the term
        parts.append(f"{w.term} months")
    return ", ".join(p for p in parts if p)


@dataclass
class Entry:
    current: Group  # the slot as it stands in the newest snapshot that has it
    latest: bool  # the slot exists in the newest snapshot
    stale: dict[str, Fact] = field(
        default_factory=dict
    )  # competing value -> newest page showing it
    changed: dict[str, Fact] = field(default_factory=dict)  # earlier winning values


def _anchor(g: Group, current: list[Group]) -> Group | None:
    hits = [c for c in current if same_slot(g.winner, c.winner)]
    return max(hits, key=lambda c: overlap(g.winner, c.winner)) if hits else None


def rate_entries(ledger: Ledger) -> list[Entry]:
    latest = groups(ledger.snapshots[-1].facts)
    entries: dict[int, Entry] = {id(g): Entry(g, True) for g in latest}
    orphans: dict[tuple, Entry] = {}
    for snap in reversed(ledger.snapshots):  # newest first: the newest page per value is kept
        for g in latest if snap is ledger.snapshots[-1] else groups(snap.facts):
            if g.winner.metric not in REPORTED_METRICS:
                continue
            a = _anchor(g, latest)
            if a is not None:
                e = entries[id(a)]
            else:  # a slot gone from the newest snapshot (an expired offer)
                w = g.winner
                key = (w.family, w.variant, w.metric, w.term, w.lo, w.hi)
                e = orphans.setdefault(key, Entry(g, False))
            for f in g.losers:
                if f.value != e.current.winner.value:
                    e.stale.setdefault(f.value, f)
            if g.winner.value != e.current.winner.value:
                e.changed.setdefault(g.winner.value, g.winner)
    return [*entries.values(), *orphans.values()]


def rate_conflict(e: Entry, include_changes: bool) -> tuple[float, Conflict] | None:
    w = e.current.winner
    competing = dict(e.stale)
    if include_changes:
        for v, f in e.changed.items():
            competing.setdefault(v, f)
    if not competing:
        return None
    lost = "; ".join(
        dict.fromkeys(
            f"{f.value} on {f.url} ({TIER_NAME.get(f.tier, 'a release')}, {_when(f)}, "
            f"{f.snapshot_id[:2]})"
            for f in competing.values()
        )
    )
    when = "in the newest snapshot" if e.latest else f"until {w.snapshot_id}"
    conflict = Conflict(
        topic=topic(w),
        values=[w.value, *competing],
        sources=[
            Source(f.url, f.snapshot_id, f.quote) for f in [*cite(e.current), *competing.values()]
        ],
        resolution=w.value,
        reason=f"{TIER_NAME[w.tier].capitalize()} ({_when(w)}, {when}) outrank {lost}.",
    )
    # confidence: a stale copy beats a pure change; the newest snapshot beats older ones;
    # a lower-tier page losing to a product page is the clearest case
    tiers = [f.tier for f in e.stale.values()]
    score = (2.0 if e.stale else 0.5) + (1.0 if e.latest else 0.0)
    score += 0.5 if tiers and max(tiers) >= LANDING else 0.0
    return score, conflict


FOOTPRINT = {"branch", "branches", "location", "locations", "office", "offices"}


def dated_key(value: str, rest: str) -> str | None:
    """The fact a dated sentence restates: a count of branch locations, or an 'Nth time'
    recognition. Other boilerplate counts (members, employees, assets) drift with time and are
    not member-facing contradictions."""
    words = re.findall(r"[a-z]+", rest.lower())[:3]
    if len(words) < 3:
        return None
    if words[0] in FOOTPRINT and value.isdigit():
        return " ".join(words)
    if words[0] == "time" and not value.isdigit():
        return " ".join(words)
    return None


def dated_conflicts(claims: list[Claim]) -> list[tuple[float, Conflict]]:
    """Releases restating the same fact with different numbers; the newest release wins (rule 4)."""
    by_fact: dict[str, dict[str, Claim]] = {}
    for c in claims:
        if c.kind != "sentence":
            continue
        # a lookahead, so "600 employees and 22 branch office locations" yields both numbers
        pattern = rf"(?<![\d$.,])(?=(\d[\d,]*|{ORDINALS})\s+([A-Za-z][^.!?]*))"
        for m in re.finditer(pattern, c.value, re.I):
            value = m[1].lower().replace(",", "")
            key = None if re.fullmatch(r"(19|20)\d\d", value) else dated_key(value, m[2])
            if key:
                seen = by_fact.setdefault(key, {})
                old = seen.get(value)
                if old is None or (c.published or date.min) > (old.published or date.min):
                    seen[value] = c
    out = []
    for key, values in by_fact.items():
        if len(values) < 2:
            continue
        newest = max(values.items(), key=lambda kv: kv[1].published or date.min)
        ordered = [newest[0], *(v for v in values if v != newest[0])]
        reason = (
            f"The newest release ({newest[1].published}) says {newest[0]} {key}; older releases "
            f"say {', '.join(ordered[1:])}."
        )
        sources = [Source(values[v].url, values[v].snapshot_id, values[v].quote) for v in ordered]
        out.append(
            (
                2.5,
                Conflict(
                    topic=f"Dupaco {key}",
                    values=[f"{v} {key}" for v in ordered],
                    sources=sources,
                    resolution=f"{newest[0]} {key}",
                    reason=reason,
                ),
            )
        )
    return out


def conflicts(
    ledger: Ledger, include_changes: bool = False, cap: int | None = CAP
) -> list[Conflict]:
    if not ledger.snapshots:
        return []
    scored = [c for e in rate_entries(ledger) if (c := rate_conflict(e, include_changes))]
    scored += dated_conflicts(ledger.snapshots[-1].claims)
    scored.sort(key=lambda sc: (-sc[0], sc[1].topic))
    return [c for _, c in scored[:cap]]
