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
FAMILY_NAME = {"auto": "Auto loan"}


def _when(f: Fact) -> str:
    return f"effective {f.effective:%m/%d/%Y}" if f.effective else "no effective date"


def conflicts(ledger: Ledger) -> list[Conflict]:
    if not ledger.snapshots:
        return []
    out = []
    for g in groups(ledger.snapshots[-1].facts):
        if not g.losers:
            continue
        w = g.winner
        values = list(dict.fromkeys(f"{f.value:.2f}%" for f in [w, *g.losers]))
        lost = "; ".join(
            dict.fromkeys(
                f"{f.url} ({TIER_NAME.get(f.tier, 'a release')}, {_when(f)})" for f in g.losers
            )
        )
        out.append(
            Conflict(
                topic=f"{FAMILY_NAME[w.family]} {w.metric}, {w.label}, {w.term} months",
                values=values,
                sources=[Source(f.url, f.snapshot_id, f.quote) for f in [*cite(g), *g.losers]],
                resolution=f"{w.value:.2f}%",
                reason=f"{TIER_NAME[w.tier].capitalize()} ({_when(w)}) outrank {lost}.",
            )
        )
    return out
