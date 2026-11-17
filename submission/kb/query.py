"""Question -> intent and slots."""

import re
from dataclasses import dataclass

from kb.normalize import term_months

MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
DATE_PHRASE = re.compile(
    rf"\b{MONTH}\.?\s+(?:\d{{1,2}}(?:st|nd|rd|th)?,?\s+)?(?:19|20)\d\d\b", re.I
)
AUTO = re.compile(r"\b(auto|car|cars|vehicle|truck|suv|van|motorcycle)\b", re.I)
NOT_AUTO = re.compile(r"\b(atv|snowmobile|jet ski|boat|rv|camper)\b", re.I)
RATE_WORDS = re.compile(r"\b(apr|rates?|interest|loans?)\b", re.I)
YEAR = re.compile(r"\b(19[5-9]\d|20\d\d)\b")


@dataclass(frozen=True)
class Query:
    intent: str  # "auto_rate" or "other"
    term: int | None = None
    year: int | None = None
    newest: bool = False  # "new car": the newest model-year tier


def parse(question: str) -> Query:
    q = DATE_PHRASE.sub(" ", question)  # "as of May 2026" is not a model year
    if AUTO.search(q) and RATE_WORDS.search(q) and not NOT_AUTO.search(q):
        year = YEAR.search(q)
        return Query(
            "auto_rate",
            term=term_months(q),
            year=int(year[1]) if year else None,
            newest=bool(re.search(r"\bnew (car|vehicle|truck|auto)", q, re.I)),
        )
    return Query("other")
