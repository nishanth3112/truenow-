"""Rate extractors driven by a product catalog: table rows and fine-print sentences -> facts."""

import re
from dataclasses import dataclass, replace

from kb.facts import Fact, Page, SnapshotFacts
from kb.normalize import (
    canonical_url,
    clean_text,
    fmt_pct,
    mdy,
    money_range,
    rate_value,
    term_months,
    year_range,
)
from kb.pages import OTHER_PRODUCT, OWNER, tier
from kb.tables import Table


@dataclass(frozen=True)
class Product:
    family: str
    name: str  # display name
    pattern: re.Pattern
    owner: tuple[str, ...]  # words in the path of the product's owner pages
    loan: bool = False  # one APR per row, whatever the header calls the column


def _p(family, name, pattern, owner, loan=False) -> Product:
    return Product(family, name, re.compile(pattern, re.I), owner, loan)


SAVINGS = ("savings-account", "savings-accounts")
# Order matters: the first product whose pattern matches a text wins.
CATALOG = [
    _p("ira", "IRA Certificate", r"\biras?\b|^(roth|traditional):", ("retirement",)),
    _p(
        "certificate",
        "Certificate",
        r"certificate|^(special|regular)( business)?( certificates)?$",
        (*SAVINGS, "certificate"),
    ),
    _p("achieve_money_market", "Achieve Money Market", r"\bachieve\b", (*SAVINGS, "money-market")),
    _p(
        "money_market",
        "Investor's Choice Money Market",
        r"investor.?s choice|money market",
        (*SAVINGS, "money-market"),
    ),
    _p("hsa", "Health Savings Account", r"health savings", (*SAVINGS, "health-savings")),
    _p(
        "bright_savings",
        "Bright Savings",
        r"bright savings",
        (*SAVINGS, "bright-savings", "online-savings"),
    ),
    _p("high_yield_savings", "High-Yield Savings", r"high.yield", SAVINGS),
    _p("you_name_it", "You Name It Savings", r"you.name.it", SAVINGS),
    _p("holiday_club", "Holiday Club Savings", r"holiday club", (*SAVINGS, "holiday-club")),
    _p("launchpad", "Launchpad Savings", r"launchpad", SAVINGS),
    _p("share_savings", "Share Savings", r"share savings", SAVINGS),
    _p("first_rate_checking", "1st Rate Checking", r"1st rate checking", ("checking",)),
    _p("free_checking", "Free Checking", r"free checking", ("checking",)),
    _p(
        "mortgage",
        "Fixed-Rate Mortgage",
        r"^(purchase|refinance):|mortgage rate relief",
        ("home-loans",),
    ),
    _p(
        "heloc",
        "Home Equity Line of Credit (HELOC)",
        r"heloc|home equity line",
        ("home-equity",),
        True,
    ),
    _p("home_equity_loan", "Home Equity Loan", r"home equity loan", ("home-equity",), True),
    _p(
        "home_improvement",
        "Home Improvement Loan",
        r"home improvement",
        ("home-improvement", "home-loans"),
        True,
    ),
    _p("auto", "Auto & Motorcycle Loan", r"\bauto\b", ("auto",), True),
    _p(
        "atv",
        "ATV, Snowmobile & Jet Ski Loan",
        r"\batv\b|snowmobile|jet ski",
        ("recreational",),
        True,
    ),
    _p("boat_rv", "Boat & RV Loan", r"\bboat\b|\brv\b", ("recreational",), True),
    _p("personal_loan", "Personal Loan", r"personal loan", ("personal-loans",), True),
    _p("platinum_visa", "Platinum Visa", r"platinum", ("credit-cards",), True),
    _p("rewards_visa", "Rewards Visa", r"rewards (visa|credit)", ("credit-cards",), True),
]
BY_FAMILY = {p.family: p for p in CATALOG}
YEAR_FAMILIES = {"auto", "atv"}

ROLES = [
    ("ignore", r"\bmin\b|minimum|payment|points|\bmax\b"),
    ("range", r"balance|\btier\b|amount"),
    ("dividend", r"dividend"),
    ("APY", r"\bapy\b|annual percentage yield"),
    ("APR", r"\bapr\b|annual percentage rate"),
    ("rate", r"^rate\b"),
]


def role(header: str) -> str:
    return next((r for r, pat in ROLES if re.search(pat, header, re.I)), "label")


def detect(texts: list[str]) -> tuple[Product | None, str]:
    for t in texts:
        for p in CATALOG:
            if p.pattern.search(t.strip()):
                return p, t
    return None, ""


def row_product(table: Table, labels: list[str]) -> tuple[Product | None, str, int]:
    """The row's product, the text that named it and how many lines above the table it was."""
    for up, text in name_sources(table, labels):
        p, _ = detect([text])
        if p:
            return p, text, up
    return None, "", 0


def row_labels(table: Table, row: list[str]) -> list[str]:
    roles = [role(h) for h in table.header]
    cells = zip(row, roles + ["label"] * (len(row) - len(roles)), strict=False)
    return [c for c, r in cells if r == "label" and c and rate_value(c) is None]


def name_sources(table: Table, labels: list[str]) -> list[tuple[int, str]]:
    """Where a row's product name may be, nearest first, with how many lines above the table."""
    return (
        [(0, t) for t in labels + table.header] + [(table.context_up, table.context)] + table.above
    )


def variant_tags(p: Product, text: str, path: str) -> str:
    t = text.lower()
    tags = set()
    if path.startswith("/business") or "business" in t:
        tags.add("business")
    if p.family == "mortgage":
        tags |= {w for w in ("purchase", "refinance", "relief") if w in t}
    if p.family in ("certificate", "ira"):
        tags |= {w for w in ("special", "jumbo", "roth", "traditional", "variable") if w in t}
    if re.search(r"intro|balance transfer", t):
        tags.add("intro")
    return " ".join(sorted(tags))


def table_facts(table: Table, page: Page, snapshot_id: str) -> list[Fact]:
    """Releases never supply rates (rule 4)."""
    if page.kind == "release":
        return []
    roles = [role(h) for h in table.header]
    suffix = [
        " first 6 months" if re.search(r"1st 6 months", h, re.I) else "" for h in table.header
    ]
    out = []
    for row, quote in zip(table.rows, table.raw_rows, strict=True):
        cells = list(zip(row, roles + ["label"] * (len(row) - len(roles)), strict=False))
        labels = [c for c, r in cells if r == "label" and c and rate_value(c) is None]
        ranges = [c for c, r in cells if r == "range" and c]
        p, matched, _ = row_product(table, labels)
        if p is None:
            continue
        if p.loan:
            v = next((rate_value(c) for c in row if rate_value(c)), None)
            values = [("APR", v)] if v else []
        else:
            values = [
                (r + suffix[i], rate_value(c))
                for i, (c, r) in enumerate(cells)
                if r in ("dividend", "APY", "APR", "rate") and rate_value(c)
            ]
        if not values:
            continue
        if p.family in YEAR_FAMILIES:
            rng = next((y for c in labels if (y := year_range(c))), None)
            if rng is None:
                continue
        else:
            rng = next((m for c in ranges + labels if (m := money_range(c))), (0.0, float("inf")))
        text = " ".join([*labels, matched, table.context])
        variant = variant_tags(p, text, page.path)
        minimum = next(
            (c for c, h in zip(row, table.header, strict=False) if "earn" in h.lower()), ""
        )
        for metric, value in values:
            out.append(
                Fact(
                    family=p.family,
                    variant=variant,
                    metric=metric,
                    term=next((t for c in labels + ranges if (t := term_months(c))), None),
                    lo=rng[0],
                    hi=rng[1],
                    value=value,
                    product=("Business " if "business" in variant.split() else "") + p.name,
                    label=(ranges or labels or [""])[0],
                    minimum=minimum,
                    url=page.url,
                    kind=page.kind,
                    tier=tier(page.kind, page.path, p.owner),
                    effective=table.effective,
                    fetched_at=page.fetched_at,
                    snapshot_id=snapshot_id,
                    quote=quote,
                )
            )
    return _unnest(out)


def _unnest(facts: list[Fact]) -> list[Fact]:
    """'$100,000 or less', '$200,000 or less', ... are nested; make each tier start just above the
    one below it, so the tiers of one table do not overlap."""
    by_slot: dict[tuple, list[Fact]] = {}
    for f in facts:
        by_slot.setdefault((f.family, f.variant, f.metric, f.term), []).append(f)
    out = []
    for fs in by_slot.values():
        ceilings = sorted({f.hi for f in fs if f.lo == 0 and f.hi != float("inf")})
        floor = {hi: prev + 0.01 for prev, hi in zip(ceilings, ceilings[1:], strict=False)}
        out += [replace(f, lo=floor[f.hi]) if f.lo == 0 and f.hi in floor else f for f in fs]
    return out


CARD_PROSE = re.compile(
    r"(Platinum|Rewards) Visa[^:\n]{0,60}:[^\n]{0,700}?standard APR, which effective "
    r"(\d{1,2})/(\d{1,2})/(\d{2,4}) is a variable rate from (\d+(?:\.\d+)?)% APR to "
    r"(\d+(?:\.\d+)?)% APR",
    re.I,
)


def card_prose_facts(page: Page, snapshot_id: str) -> list[Fact]:
    """Card fine print states the standard APR range in a sentence with its own date."""
    if page.kind == "release":
        return []
    out = []
    for m in CARD_PROSE.finditer(clean_text(page.markdown).replace("\\*", "")):
        p = BY_FAMILY[m[1].lower() + "_visa"]
        out.append(
            Fact(
                family=p.family,
                variant="",
                metric="APR",
                term=None,
                lo=0.0,
                hi=float("inf"),
                value=f"{fmt_pct(float(m[5]))}-{fmt_pct(float(m[6]))}",
                product=p.name,
                label="standard APR (fine print)",
                minimum="",
                url=page.url,
                kind=page.kind,
                tier=tier(page.kind, page.path, p.owner),
                effective=mdy(m[2], m[3], m[4]),
                fetched_at=page.fetched_at,
                snapshot_id=snapshot_id,
                quote=m[0][m[0].rfind("standard APR") :],
            )
        )
    return out


LINK = re.compile(r"\[([^\]]{1,80})\]\((https://www\.dupaco\.com/[^)\s]*)\)")


def promote_linked_landing_pages(sf: SnapshotFacts) -> None:
    """A product shown only on a landing page is owned by that page when a product page or rate
    sheet names the product in a link to it ('[Achieve](/earn-more)' on /personal/savings-account
    in 2026-09-28). Products that have product-page facts are never promoted this way."""
    covered = {f.family for f in sf.facts if f.tier <= OTHER_PRODUCT}
    owners: dict[str, set[str]] = {}
    for page in sf.pages.values():
        if page.kind not in ("product", "rate_sheet"):
            continue
        for anchor, target in LINK.findall(page.markdown):
            p, _ = detect([re.sub(r"[*\\]", "", anchor)])
            url = canonical_url(target)
            if (
                p
                and p.family not in covered
                and url in sf.pages
                and sf.pages[url].kind == "landing"
            ):
                owners.setdefault(p.family, set()).add(url)
    sf.facts = [
        replace(f, tier=OWNER) if f.url in owners.get(f.family, ()) else f for f in sf.facts
    ]


# A promotional variant must be named as such, not just its product (rule 4).
VARIANT_NAME = {
    "relief": r"rate relief",
    "intro": r"\bintro",
    "special": r"month[^\n|]{0,40}special",
}


def named_on_product_pages(sf: SnapshotFacts, f: Fact) -> bool:
    """Does any product page or rate sheet name this product (and its promotional variant)?"""
    pats = [BY_FAMILY[f.family].pattern.pattern.replace("^", "")]
    pats += [VARIANT_NAME[t] for t in f.variant.split() if t in VARIANT_NAME]
    return any(
        all(re.search(pat, page.markdown, re.I) for pat in pats)
        for page in sf.pages.values()
        if page.kind in ("product", "rate_sheet")
    )


EXTRACTORS = [table_facts]
PAGE_EXTRACTORS = [card_prose_facts]
POST = [promote_linked_landing_pages]
