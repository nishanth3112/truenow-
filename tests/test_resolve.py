"""Resolver cases modelled on traced auto rows (dev/TRACES.md section 1)."""

from datetime import date

from kb.facts import Fact, Ledger, SnapshotFacts
from kb.pages import LANDING, OTHER_PRODUCT, OWNER
from kb.resolve import changes, cite, groups, lookup

OWNER_URL = "https://www.dupaco.com/personal/loans/auto-motorcycle-loans"
RATES = "https://www.dupaco.com/rates"
SWITCH = "https://www.dupaco.com/switch-and-earn"
CHECKING = "https://www.dupaco.com/personal/checking-accounts"
KEY60 = ("auto", "", "APR", 60)


def fact(
    url, label, rng, term, value, eff, sid="05", tier=OWNER, kind="product", fetched="2026-09-28"
):
    return Fact(
        family="auto",
        variant="",
        metric="APR",
        term=term,
        lo=rng[0],
        hi=rng[1],
        value=f"{value:.2f}%",
        product="Auto & Motorcycle Loan",
        label=label,
        minimum="",
        url=url,
        kind=kind,
        tier=tier,
        effective=eff,
        fetched_at=fetched + "T00:00:00Z",
        snapshot_id=sid,
        quote=label,
    )


LATEST = [
    fact(
        SWITCH,
        "2023-26 Model Year",
        (2023, 2026),
        60,
        5.34,
        date(2026, 1, 1),
        tier=LANDING,
        kind="landing",
        fetched="2026-06-09",
    ),
    fact(RATES, "2024-27 Model Year", (2024, 2027), 60, 5.39, date(2026, 8, 31), kind="rate_sheet"),
    fact(OWNER_URL, "2024-27 Model Year", (2024, 2027), 60, 5.39, date(2026, 8, 31)),
    fact(OWNER_URL, "2021-23 Model Year", (2021, 2023), 60, 5.64, date(2026, 8, 31)),
    fact(
        SWITCH,
        "2021-22 Model Year",
        (2021, 2022),
        60,
        5.59,
        date(2026, 1, 1),
        tier=LANDING,
        kind="landing",
        fetched="2026-06-09",
    ),
]


def test_authority_beats_landing_page():
    g = lookup(LATEST, KEY60, 2025)
    assert g.winner.value == "5.39%"
    assert [f.value for f in g.losers] == ["5.34%"]


def test_cite_prefers_owner_page_then_rate_sheet():
    g = lookup(LATEST, KEY60, 2025)
    assert [f.url for f in cite(g)] == [OWNER_URL, RATES]


def test_model_year_moves_tier_when_labels_drift():
    assert lookup(LATEST, KEY60, 2023).winner.value == "5.64%"


def test_same_tier_later_effective_date_wins():
    older = fact(
        CHECKING,
        "2023-26 Model Year",
        (2023, 2026),
        60,
        5.34,
        date(2025, 10, 22),
        tier=OTHER_PRODUCT,
    )
    newer = fact(
        CHECKING, "2023-26 Model Year", (2023, 2026), 60, 5.19, date(2026, 5, 1), tier=OTHER_PRODUCT
    )
    assert lookup([older, newer], KEY60, 2025).winner.value == "5.19%"


def test_groups_match_stale_rows_by_largest_overlap():
    gs = {g.winner.label: g for g in groups(LATEST)}
    assert set(gs) == {"2024-27 Model Year", "2021-23 Model Year"}
    assert [f.value for f in gs["2024-27 Model Year"].losers] == ["5.34%"]
    assert [f.value for f in gs["2021-23 Model Year"].losers] == ["5.59%"]
    # equal tier, date and fetch time: the owner page wins, the rate sheet supports it
    assert gs["2024-27 Model Year"].winner.url == OWNER_URL
    assert [f.url for f in gs["2024-27 Model Year"].support] == [RATES]


def test_snapshot_selection_and_change_log():
    led = Ledger()
    s4 = SnapshotFacts(
        "04",
        "2026-08-27",
        facts=[
            fact(
                OWNER_URL, "2023-26 Model Year", (2023, 2026), 60, 5.19, date(2026, 5, 1), sid="04"
            )
        ],
    )
    s5 = SnapshotFacts("05", "2026-09-28", facts=LATEST)
    led.add(s5)
    led.add(s4)
    assert led.at(None) is s5
    assert led.at("2026-08-31") is s4
    assert led.at("2026-09-28") is s5
    assert led.at("2026-05-01") is None
    (c,) = [c for c in changes(led) if c.term == 60]
    assert (c.old.value, c.new.value, c.label) == ("5.19%", "5.39%", "2024-27 Model Year")
