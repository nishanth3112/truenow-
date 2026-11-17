"""Currency rules 2-3 (authority, then effective date, then fetched_at) and slot grouping."""

from dataclasses import dataclass, field
from datetime import date, datetime

from kb.facts import Change, Fact, Ledger


def overlap(a: Fact, b: Fact) -> float:
    return min(a.hi, b.hi) - max(a.lo, b.lo)


def slot(f: Fact) -> tuple:
    return (f.family, f.variant, f.metric, f.term)


def same_slot(a: Fact, b: Fact) -> bool:
    return slot(a) == slot(b) and overlap(a, b) >= 0


def rank(f: Fact) -> tuple:
    """Sort key: the first fact wins."""
    fetched = datetime.fromisoformat(f.fetched_at.replace("Z", "+00:00")).timestamp()
    return (f.tier, -(f.effective or date.min).toordinal(), -fetched, f.kind != "product", f.url)


@dataclass
class Group:
    winner: Fact
    support: list[Fact] = field(default_factory=list)  # other pages with the winning value
    losers: list[Fact] = field(default_factory=list)  # other pages with a different value


def resolve(cands: list[Fact]) -> Group | None:
    if not cands:
        return None
    ordered = sorted(cands, key=rank)
    g = Group(ordered[0])
    for f in ordered[1:]:
        (g.support if f.value == g.winner.value else g.losers).append(f)
    return g


def lookup(facts: list[Fact], key: tuple, point: float) -> Group | None:
    """Resolve the value at one point (a model year, a balance) of one slot (see slot())."""
    return resolve([f for f in facts if slot(f) == key and f.lo <= point <= f.hi])


def groups(facts: list[Fact]) -> list[Group]:
    """Walk facts in rank order; a fact that overlaps no earlier winner in its slot becomes a
    winner, otherwise it joins the winner it overlaps most. Labels drift between pages
    ('2023-26' vs '2024-27'), so slots are matched by range overlap, never by label."""
    out: list[Group] = []
    for f in sorted(facts, key=rank):
        hits = [g for g in out if same_slot(g.winner, f)]
        if not hits:
            out.append(Group(f))
            continue
        g = max(hits, key=lambda g: overlap(g.winner, f))
        (g.support if f.value == g.winner.value else g.losers).append(f)
    return out


def cite(g: Group) -> list[Fact]:
    """Rule 7: the highest-tier pages holding the winning value, owner pages first, one per URL."""
    best = [f for f in [g.winner, *g.support] if f.tier == g.winner.tier]
    seen, out = set(), []
    for f in sorted(best, key=lambda f: (f.kind != "product", f.url)):
        if f.url not in seen:
            seen.add(f.url)
            out.append(f)
    return out


def _best(f: Fact, others: list[Fact]) -> Fact | None:
    hits = [o for o in others if same_slot(f, o)]
    return max(hits, key=lambda o: overlap(f, o)) if hits else None


def changes(ledger: Ledger) -> list[Change]:
    """Winning values that changed between consecutive snapshots. Old and new winners are paired
    only when each is the other's best overlap, so one old row never explains two new ones."""
    out = []
    for prev, cur in zip(ledger.snapshots, ledger.snapshots[1:], strict=False):
        old = [g.winner for g in groups(prev.facts)]
        new = [g.winner for g in groups(cur.facts)]
        for w in new:
            match = _best(w, old)
            if match and _best(match, new) is w and match.value != w.value:
                out.append(Change(w.family, w.metric, w.term, w.label, match, w))
    return out
