"""Page kind, authority tier and publish date."""

import re
from datetime import date, datetime

RATE_SHEETS = {"/rates", "/business-rates"}
PUBLISHED = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2}), (20\d\d)\b"
)

# Lower is more authoritative (currency rule 2).
OWNER, OTHER_PRODUCT, PDF, LANDING, RELEASE = 1, 2, 3, 4, 5


def page_kind(path: str) -> str:
    if path in RATE_SHEETS:
        return "rate_sheet"
    if path.endswith(".pdf") or path.startswith("/hubfs/"):
        return "pdf"
    if re.match(r"/(learn|newsroom|blog)(/|$)", path) or "/resources/" in path:
        return "release"
    if path.startswith("/calculators/") or path.count("/") <= 1:
        return "landing"  # top-level marketing pages such as /switch-and-earn
    return "product"


def tier(kind: str, path: str, owner_words: tuple[str, ...]) -> int:
    """Authority of a fact about a product whose owner pages have one of owner_words in the path."""
    if kind == "rate_sheet":
        return OWNER
    if kind == "product":
        return OWNER if any(w in path for w in owner_words) else OTHER_PRODUCT
    return {"pdf": PDF, "landing": LANDING}.get(kind, RELEASE)


def publish_date(markdown: str) -> date | None:
    """A release's date sits near the top of the page."""
    m = PUBLISHED.search(markdown[:3000])
    return datetime.strptime(f"{m[1]} {m[2]} {m[3]}", "%b %d %Y").date() if m else None
