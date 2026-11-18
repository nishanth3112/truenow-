"""The temporal ledger: per-snapshot pages and facts, plus a fact-level change log."""

from dataclasses import dataclass, field
from datetime import date

from kb.normalize import canonical_url, strip_noise, url_path
from kb.pages import page_kind
from kb.tables import parse_tables


@dataclass(frozen=True)
class Fact:
    family: str  # product family, e.g. "auto", "share_savings", "mortgage"
    variant: str  # space-joined sorted tags: "business", "jumbo special", "purchase", "intro"
    metric: str  # "APR", "APY", "dividend", "rate", "APY first 6 months", ...
    term: int | None  # months
    lo: float  # qualifier range: model years (auto) or dollars (balance, loan amount)
    hi: float
    value: str  # canonical percent text: "5.39%", "6.125%", "12.50%-19.50%"
    product: str  # display name, e.g. "Business Share Savings"
    label: str  # the row's qualifier as printed, e.g. "2024-27 Model Year", "$25,000+"
    minimum: str  # minimum to earn, when the table gives one
    url: str
    kind: str  # page kind
    tier: int  # currency rule 2, lower wins
    effective: date | None  # the table's (or sentence's) effective date
    fetched_at: str
    snapshot_id: str
    quote: str  # the cleaned table row or sentence

    @property
    def num(self) -> float:
        return float(self.value.split("%")[0])


@dataclass(frozen=True)
class Claim:
    """A non-rate fact: identifier, link, address, branch hours, closure, or a dated sentence."""

    kind: str  # "routing", "phone", "address", "join_url", "locator_url", "hours", "closure", ...
    subject: str  # who it is about: a branch name, "" for site-wide facts
    key: str  # e.g. "lobby" / "drive-up" for hours, the ISO date for closures
    value: str
    url: str
    published: date | None  # release publish date (rule 4: newest first)
    snapshot_id: str
    quote: str


@dataclass
class Page:
    url: str
    path: str
    kind: str
    title: str
    markdown: str
    fetched_at: str


@dataclass
class SnapshotFacts:
    snapshot_id: str
    taken_on: str
    pages: dict[str, Page] = field(default_factory=dict)
    facts: list[Fact] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    index: object = None  # kb.retrieval.Index, built at ingest


@dataclass(frozen=True)
class Change:
    family: str
    metric: str
    term: int | None
    label: str  # label in the newer snapshot
    old: Fact
    new: Fact


def build_snapshot(snapshot, extractors, page_extractors=(), post=()) -> SnapshotFacts:
    """Canonicalize pages (later fetched_at wins on a URL clash), run every table extractor on
    every table and every page extractor on every page, then each snapshot-wide post step."""
    sf = SnapshotFacts(snapshot.snapshot_id, snapshot.taken_on)
    for p in snapshot.pages:
        url = canonical_url(p.url)
        if url is None or (url in sf.pages and sf.pages[url].fetched_at >= p.fetched_at):
            continue
        path = url_path(url)
        sf.pages[url] = Page(
            url, path, page_kind(path), p.title, strip_noise(p.markdown), p.fetched_at
        )
    for page in sf.pages.values():
        for extract in page_extractors:
            sf.facts.extend(extract(page, sf.snapshot_id))
        if "|" not in page.markdown:
            continue
        for table in parse_tables(page.markdown):
            for extract in extractors:
                sf.facts.extend(extract(table, page, sf.snapshot_id))
    for step in post:
        step(sf)
    return sf


class Ledger:
    def __init__(self):
        self.snapshots: list[SnapshotFacts] = []

    def add(self, sf: SnapshotFacts) -> None:
        self.snapshots.append(sf)
        self.snapshots.sort(key=lambda s: s.taken_on)

    def at(self, as_of: str | None) -> SnapshotFacts | None:
        """Currency rule 1: the latest snapshot taken on or before as_of; None before the first."""
        if as_of is None:
            return self.snapshots[-1] if self.snapshots else None
        older = [s for s in self.snapshots if s.taken_on <= as_of[:10]]
        return older[-1] if older else None
