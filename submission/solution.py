"""truenow: answers member questions from website snapshots with the value that is current as of
the requested date. See NOTES.md."""

import sys
from pathlib import Path

# The harness puts its folder on sys.path before loading us; this covers running from elsewhere.
sys.path.insert(0, str(Path(__file__).resolve().parent))
_kit = next(
    (
        d / "harness"
        for d in Path(__file__).resolve().parents
        if (d / "harness" / "contract.py").exists()
    ),
    None,
)
if _kit:
    sys.path.append(str(_kit))

from kb.answer import answer  # noqa: E402
from kb.conflicts import conflicts  # noqa: E402
from kb.extract.entities import entity_claims  # noqa: E402
from kb.extract.rates import EXTRACTORS, PAGE_EXTRACTORS, POST  # noqa: E402
from kb.facts import Ledger, build_snapshot  # noqa: E402
from kb.retrieval import Index  # noqa: E402


def index(sf) -> None:
    sf.index = Index(sf)


class TrueNow:
    def __init__(self):
        self.ledger = Ledger()

    def ingest(self, snapshot) -> None:
        self.ledger.add(
            build_snapshot(snapshot, EXTRACTORS, PAGE_EXTRACTORS, [*POST, entity_claims, index])
        )

    def answer(self, question, as_of=None):
        return answer(self.ledger, question, as_of)

    def conflicts(self):
        return conflicts(self.ledger)


def build():
    return TrueNow()
