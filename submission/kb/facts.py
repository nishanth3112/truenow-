"""The temporal ledger: per-snapshot pages and facts, plus a fact-level change log."""

from dataclasses import dataclass, field
from datetime import date

from kb.normalize import canonical_url, strip_noise, url_path
from kb.pages import page_kind
from kb.tables import parse_tables


@dataclass(frozen=True)
class Fact:
    family: str  # product family, e.g. "auto"
    metric: str  # "APR", "APY", "dividend"
    term: int | None  # months
    lo: float  # qualifier range: model years for auto
    hi: float
    value: float  # percent
    label: str  # the row's qualifier as printed, e.g. "2024-27 Model Year"
    url: str
    kind: str  # page kind
    tier: int  # currency rule 2, lower wins
    effective: date | None  # the table's effective date
    fetched_at: str
    snapshot_id: str
    quote: str  # the cleaned table row


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


@dataclass(frozen=True)
class Change:
    family: str
    metric: str
    term: int | None
    label: str  # label in the newer snapshot
    old: Fact
    new: Fact


def build_snapshot(snapshot, extractors) -> SnapshotFacts:
    """Canonicalize pages (later fetched_at wins on a URL clash), then run every extractor on
    every table of every page."""
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
        if "|" not in page.markdown:
            continue
        for table in parse_tables(page.markdown):
            for extract in extractors:
                sf.facts.extend(extract(table, page, sf.snapshot_id))
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
