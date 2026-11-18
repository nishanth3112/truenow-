"""Phase 5 conflict rules on a synthetic two-snapshot ledger shaped like traced cases."""

from datetime import date

from kb.conflicts import conflicts
from kb.facts import Claim, Fact, Ledger, SnapshotFacts
from kb.pages import LANDING, OWNER

CARDS = "https://www.dupaco.com/personal/credit-cards"
RATES = "https://www.dupaco.com/rates"
SWITCH = "https://www.dupaco.com/switch-and-earn"


def fact(url, family, value, eff, sid, tier=OWNER, kind="product", label="row", lo=0.0, hi=9e9):
    return Fact(
        family,
        "",
        "APR",
        None,
        lo,
        hi,
        value,
        family.title(),
        label,
        "",
        url,
        kind,
        tier,
        eff,
        f"2026-0{sid[1]}-01T00:00:00Z",
        sid,
        label,
    )


def ledger() -> Ledger:
    led = Ledger()
    old = SnapshotFacts(
        "01_x",
        "2026-05-12",
        facts=[
            # within-snapshot contradiction that only existed in the older snapshot (lc-13 style)
            fact(
                RATES, "platinum_visa", "12.50%-19.50%", date(2026, 1, 1), "01", kind="rate_sheet"
            ),
            fact(CARDS, "platinum_visa", "13.00%-20.00%", date(2025, 10, 1), "01"),
            # stale landing copy present in both snapshots
            fact(RATES, "auto", "5.19%", date(2026, 5, 1), "01", kind="rate_sheet"),
            fact(SWITCH, "auto", "5.34%", date(2026, 1, 1), "01", LANDING, "landing"),
            # pure change: a rate that moved with no stale copy left anywhere
            fact(RATES, "heloc", "6.00%", date(2026, 5, 1), "01", kind="rate_sheet"),
        ],
    )
    new = SnapshotFacts(
        "05_x",
        "2026-09-28",
        facts=[
            fact(
                RATES, "platinum_visa", "12.50%-19.50%", date(2026, 1, 2), "05", kind="rate_sheet"
            ),
            fact(RATES, "auto", "5.39%", date(2026, 8, 31), "05", kind="rate_sheet"),
            fact(SWITCH, "auto", "5.34%", date(2026, 1, 1), "05", LANDING, "landing"),
            fact(RATES, "heloc", "6.25%", date(2026, 8, 1), "05", kind="rate_sheet"),
        ],
        claims=[
            Claim(
                "sentence",
                "",
                "",
                "It has over 600 employees and 23 branch office locations.",
                "https://www.dupaco.com/newsroom/a",
                date(2026, 3, 17),
                "05",
                "q",
            ),
            Claim(
                "sentence",
                "",
                "",
                "It has over 600 employees and 22 branch office locations.",
                "https://www.dupaco.com/newsroom/b",
                date(2026, 5, 5),
                "05",
                "q",
            ),
            Claim(
                "sentence",
                "",
                "",
                "It has 140,000 members.",
                "https://www.dupaco.com/newsroom/c",
                date(2026, 5, 5),
                "05",
                "q",
            ),
        ],
    )
    led.add(old)
    led.add(new)
    return led


def by_topic(cs):
    return {c.topic.split(" APR")[0]: c for c in cs}


def test_one_conflict_per_fact_across_snapshots():
    cs = by_topic(conflicts(ledger()))
    auto = cs["Auto"]
    assert auto.values == ["5.39%", "5.34%"] and auto.resolution == "5.39%"
    assert {s.url for s in auto.sources} == {RATES, SWITCH}
    card = cs["Platinum_Visa"]  # only contradicted in the older snapshot, still reported once
    assert card.values == ["12.50%-19.50%", "13.00%-20.00%"] and card.resolution == "12.50%-19.50%"


def test_pure_changes_only_on_request():
    assert "Heloc" not in by_topic(conflicts(ledger()))
    heloc = by_topic(conflicts(ledger(), include_changes=True))["Heloc"]
    assert heloc.values == ["6.25%", "6.00%"]


def test_dated_claims_newest_release_wins_and_cap():
    cs = conflicts(ledger())
    (branches,) = [c for c in cs if "branch office locations" in c.topic]
    assert branches.resolution == "22 branch office locations"
    assert branches.values == ["22 branch office locations", "23 branch office locations"]
    assert not any("employees" in c.topic or "members" in c.topic for c in cs)
    assert len(conflicts(ledger(), cap=1)) == 1
