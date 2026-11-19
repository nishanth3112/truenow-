"""Question -> intent, product families and slots."""

import calendar
import re
from dataclasses import dataclass, field

from kb.normalize import term_months

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}  # "jan" -> 1
MONTH = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
DATE_PHRASE = re.compile(
    rf"\b{MONTH}\.?\s+(?:(\d{{1,2}})(?:st|nd|rd|th)?,?\s+)?((?:19|20)\d\d)\b", re.I
)
AMOUNT = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*(million|k\b)?", re.I)
RATE_WORDS = re.compile(r"\b(rates?|aprs?|apys?|dividends?|interest|yields?|pays?|earns?)\b", re.I)
LINK_WORDS = re.compile(r"\b(link|url|web ?page|website)\b", re.I)
YEAR = re.compile(r"\b(19[5-9]\d|20\d\d)\b")
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
NEGATED = re.compile(r"\b(?:not|non|no)[- ](jumbo|special|intro)\b", re.I)

# Question wording -> catalog families. Order matters: specific before general.
FAMILY_WORDS = [
    (r"\bira\b|\broth\b|retirement (account|certificate)", ["ira"]),
    (r"certificate|\bcds?\b|term share", ["certificate"]),
    (r"\bachieve\b", ["achieve_money_market"]),
    (r"money market|investor.?s choice", ["money_market"]),
    (r"\bhsa\b|health savings", ["hsa"]),
    (r"bright savings", ["bright_savings"]),
    (r"high.yield", ["high_yield_savings"]),
    (r"you.name.it", ["you_name_it"]),
    (r"holiday club|christmas club", ["holiday_club"]),
    (r"launchpad", ["launchpad"]),
    (r"1st rate checking|first rate checking", ["first_rate_checking"]),
    (r"free checking", ["free_checking"]),
    (r"checking", ["free_checking", "first_rate_checking"]),
    (r"savings", ["share_savings"]),
    (r"heloc|home equity line", ["heloc"]),
    (r"home equity loan", ["home_equity_loan"]),
    (r"home improvement", ["home_improvement"]),
    (
        r"mortgage|home loan|\barm\b|adjustable.rate|\b(15|20|30)[- ]year fixed|fixed.rate",
        ["mortgage"],
    ),
    (r"\batv\b|snowmobile|jet ski", ["atv"]),
    (r"\bboat\b|\brv\b|camper", ["boat_rv"]),
    (r"\b(auto|car|cars|vehicle|truck|suv|van|motorcycle)\b", ["auto"]),
    (r"personal loan", ["personal_loan"]),
    (r"platinum", ["platinum_visa"]),
    (r"rewards (visa|card|credit)", ["rewards_visa"]),
    (r"credit cards?|\bvisa\b", ["platinum_visa", "rewards_visa"]),
]
# Words that ask for a variant; a fact must carry every requested tag.
VARIANT_WORDS = [
    ("jumbo", r"\bjumbo\b"),
    ("special", r"\bspecial\b|\bpromo"),
    ("intro", r"\bintro|balance transfer"),
    ("refinance", r"refinanc"),
    ("purchase", r"\bpurchase|\bbuy"),
    ("relief", r"rate relief"),
    ("roth", r"\broth\b"),
    ("traditional", r"\btraditional\b"),
    ("variable", r"\bvariable ira"),
    ("arm", r"\barm\b|adjustable"),  # no fact carries "arm": ARM questions refuse
]


# Member wording -> the site's own words, applied before routing and before the long-tail
# unknown-word refusal check (a synonym the site never uses is not an unknown topic).
SYNONYMS = [
    (r"\bcds\b", "certificates"),
    (r"\bcd\b", "certificate"),
    (r"\bcar loans?\b", "auto loan"),
    (r"\bhome loans?\b", "mortgage"),
    (r"\b(atm|check) cards?\b", "debit card"),
]


def normalize_synonyms(question: str) -> str:
    for pat, repl in SYNONYMS:
        question = re.sub(pat, repl, question, flags=re.I)
    return question


@dataclass(frozen=True)
class Query:
    intent: str  # "rate", "rate_link" or "other"
    families: list[str] = field(default_factory=list)
    term: int | None = None
    year: int | None = None  # auto model year
    amount: float | None = None  # balance or loan amount
    tags: frozenset = frozenset()
    excluded: frozenset = frozenset()  # "not jumbo", "non-jumbo"
    business: bool | None = False  # None: both personal and business ("what cards do you offer")
    newest: bool = False  # "new car"
    superlative: str = ""  # "max" / "min"
    percent: float | None = None  # a rate named in the question


def as_of_from(question: str) -> str | None:
    """'as of May 2026' / 'in June 2026' / 'on May 15, 2026' -> ISO date; a month alone maps to its
    last day."""
    m = DATE_PHRASE.search(question)
    if not m:
        return None
    month, year = MONTHS[m[1].lower()[:3]], int(m[3])
    day = int(m[2]) if m[2] else calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse(question: str) -> Query:
    q = DATE_PHRASE.sub(" ", question)  # "as of May 2026" is neither a model year nor a balance
    families = next((fams for pat, fams in FAMILY_WORDS if re.search(pat, q, re.I)), [])
    is_rate = bool(RATE_WORDS.search(q))
    if not is_rate or (LINK_WORDS.search(q) and not families):
        return Query("other")
    year = YEAR.search(q) if families == ["auto"] else None
    amount = AMOUNT.search(q)
    pct = PERCENT.search(q)
    negated = frozenset(m.lower() for m in NEGATED.findall(q))
    return Query(
        "rate_link" if LINK_WORDS.search(q) else "rate",
        families=families,
        term=term_months(q),
        year=int(year[1]) if year else None,
        amount=float(amount[1].replace(",", ""))
        * {"million": 1e6, "k": 1e3}.get((amount[2] or "").lower(), 1)
        if amount
        else None,
        tags=frozenset(t for t, pat in VARIANT_WORDS if re.search(pat, q, re.I)) - negated,
        excluded=negated,
        business=True
        if re.search(r"\bbusiness\b", q, re.I)
        else None
        if families == ["platinum_visa", "rewards_visa"] and not re.search(r"personal", q, re.I)
        else False,
        newest=bool(re.search(r"\bnew (car|vehicle|truck|auto)", q, re.I)),
        superlative="max"
        if re.search(r"\b(highest|best|top|most)\b", q, re.I)
        else "min"
        if re.search(r"\b(lowest|cheapest)\b", q, re.I)
        else "",
        percent=float(pct[1]) if pct else None,
    )
