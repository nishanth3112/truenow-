"""Contradictions within the latest snapshot: same slot, different values on different pages."""

from contract import Conflict, Source

from kb.facts import Fact, Ledger
from kb.pages import LANDING, OTHER_PRODUCT, OWNER, PDF
from kb.resolve import cite, groups

TIER_NAME = {
    OWNER: "the product page and rate sheet",
    OTHER_PRODUCT: "another product page",
    PDF: "a PDF",
    LANDING: "a landing or calculator page",
}
# A row's rate and APR (or dividend and APY) move together; one conflict per row is enough.
REPORTED_METRICS = {"APR", "APY"}


def _when(f: Fact) -> str:
    return f"effective {f.effective:%m/%d/%Y}" if f.effective else "no effective date"


def topic(w: Fact) -> str:
    parts = [f"{w.product} {w.metric}", w.label]
    if w.term and w.family != "mortgage":  # mortgage labels already name the term
        parts.append(f"{w.term} months")
    return ", ".join(p for p in parts if p)


def conflicts(ledger: Ledger) -> list[Conflict]:
    if not ledger.snapshots:
        return []
    out = []
    for g in groups(ledger.snapshots[-1].facts):
        w = g.winner
        if not g.losers or w.metric not in REPORTED_METRICS:
            continue
        lost = "; ".join(
            dict.fromkeys(
                f"{f.url} ({TIER_NAME.get(f.tier, 'a release')}, {_when(f)})" for f in g.losers
            )
        )
        out.append(
            Conflict(
                topic=topic(w),
                values=list(dict.fromkeys(f.value for f in [w, *g.losers])),
                sources=[Source(f.url, f.snapshot_id, f.quote) for f in [*cite(g), *g.losers]],
                resolution=w.value,
                reason=f"{TIER_NAME[w.tier].capitalize()} ({_when(w)}) outrank {lost}.",
            )
        )
    return out
