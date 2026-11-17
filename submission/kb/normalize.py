"""Text, URL, date and range normalization shared by ingest and answering."""

import re
from datetime import date
from urllib.parse import urlsplit

SITE = "https://www.dupaco.com"
# The 2026-09-28 snapshot added /personal/loans/auto-loans/ as a copy of the auto loan page.
ALIASES = {"/personal/loans/auto-loans": "/personal/loans/auto-motorcycle-loans"}

EFFECTIVE = re.compile(r"rates (?:are )?effective (?:as of )?(\d{1,2})/(\d{1,2})/(\d{2,4})\b", re.I)
AMOUNT = r"\$\s*([\d,]+(?:\.\d+)?)"


def clean_text(s: str) -> str:
    """Tables use non-breaking spaces and mix en/em dashes with hyphens."""
    return s.replace("\xa0", " ").replace("–", "-").replace("—", "-")


NOISE = re.compile(
    r"^\s*(!\[[^\]]*\]\([^)]*\)|\[!\[.*\]\(.*\)|Twitter Widget Iframe|Third Party Plugins|"
    r"Messenger Launcher|Messenger|\[Continue\]\([^)]*\) Cancel)\s*$"
)


def strip_noise(markdown: str) -> str:
    """Drop image-only lines, chat/social widget labels and 'Continue / Cancel' modal lines."""
    return "\n".join(ln for ln in markdown.split("\n") if not NOISE.match(ln))


def canonical_url(url: str) -> str | None:
    """Drop query, fragment and trailing slash; None for modal pop-ups (not real pages)."""
    if "containerType=MODAL" in url:
        return None
    path = urlsplit(url).path.rstrip("/")
    return SITE + ALIASES.get(path, path)


def url_path(url: str) -> str:
    return urlsplit(url).path.rstrip("/") or "/"


def mdy(month: str, day: str, year: str) -> date:
    y = int(year)
    return date(y + 2000 if y < 100 else y, int(month), int(day))


def effective_dates(text: str) -> list[tuple[int, date]]:
    """(offset, date) of every 'Rates (are) effective (as of) M/D/Y' line."""
    return [(m.start(), mdy(*m.groups())) for m in EFFECTIVE.finditer(text)]


def clean_cell(cell: str) -> str:
    """Strip markdown escapes and footnote digits glued to values: '5.39% APR1' -> '5.39% APR'."""
    c = clean_text(cell).replace("\\*", "").replace("*", "").strip()
    c = re.sub(r"(%|\bAPR|\bAPY|\))\d+\b", r"\1", c)
    return re.sub(r"\s+", " ", c)


def year_range(label: str) -> tuple[int, int] | None:
    """'2024-27 Model Year' -> (2024, 2027); 'Model Year 2026-23' -> (2023, 2026);
    '2016 Model Year (and older)' -> (1900, 2016)."""
    label = clean_text(label)
    m = re.search(r"\b((?:19|20)\d\d)\s*-\s*(\d{2}|\d{4})\b", label)
    if m:
        a, b = int(m[1]), m[2]
        b = int(b) if len(b) == 4 else a // 100 * 100 + int(b)
        return min(a, b), max(a, b)
    m = re.search(r"\b((?:19|20)\d\d)\b", label)
    if not m:
        return None
    y = int(m[1])
    return (1900, y) if "older" in label.lower() else (y, y)


def money_range(label: str) -> tuple[float, float] | None:
    """'$10,000 - $24,999.99', '$10,000-24,999', '$25,000+', '$832750 or less' -> (low, high)."""
    label = clean_text(label)
    m = re.search(AMOUNT + r"\s*-\s*\$?\s*([\d,]+(?:\.\d+)?)", label)
    if m:
        return float(m[1].replace(",", "")), float(m[2].replace(",", ""))
    m = re.search(AMOUNT, label)
    if not m:
        return None
    v = float(m[1].replace(",", ""))
    if re.search(r"\+|or more", label):
        return v, float("inf")
    if re.search(r"or less|up to", label, re.I):
        return 0.0, v
    return v, v


def term_months(label: str) -> int | None:
    """'60 Months' -> 60, '10 Month Fixed' -> 10, '5 Years' -> 60."""
    m = re.search(r"\b(\d{1,3})[ -]?(months?|mos?\.?|years?|yrs?)\b", label, re.I)
    if not m:
        return None
    n = int(m[1])
    return n * 12 if m[2].lower().startswith("y") else n


def percent(cell: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", cell)
    return float(m[1]) if m else None
