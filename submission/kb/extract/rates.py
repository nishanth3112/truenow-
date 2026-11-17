"""Rate-table extractors: table + page -> facts."""

import re

from kb.facts import Fact, Page
from kb.normalize import percent, term_months, year_range
from kb.pages import tier
from kb.tables import Table

AUTO_OWNER = ("auto",)


def auto_facts(table: Table, page: Page, snapshot_id: str) -> list[Fact]:
    """Auto & motorcycle loan APR by model-year range and term. Releases never supply rates
    (rule 4); ATV/snowmobile tables share the model-year layout but not the 'Auto' heading."""
    if page.kind == "release" or not re.search(r"\bauto\b", table.context, re.I):
        return []
    out = []
    for row, quote in zip(table.rows, table.raw_rows, strict=True):
        label = next((c for c in row if "model year" in c.lower()), None)
        rng = year_range(label) if label else None
        term = next((t for c in row if (t := term_months(c))), None)
        value = next((v for c in row if (v := percent(c)) is not None), None)
        if rng and term and value is not None:
            out.append(
                Fact(
                    family="auto",
                    metric="APR",
                    term=term,
                    lo=rng[0],
                    hi=rng[1],
                    value=value,
                    label=label,
                    url=page.url,
                    kind=page.kind,
                    tier=tier(page.kind, page.path, AUTO_OWNER),
                    effective=table.effective,
                    fetched_at=page.fetched_at,
                    snapshot_id=snapshot_id,
                    quote=quote,
                )
            )
    return out


EXTRACTORS = [auto_facts]
