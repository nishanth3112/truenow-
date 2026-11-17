from datetime import date

from kb.tables import parse_tables

MD = """## Get on the road

Auto Loan Rates

| Loan Program | Term | Annual Percentage Rate (As Low As)1 |
| --- | --- | --- |
| 2024-27 Model Year | 60\xa0Months | 5.39% APR1 |
| 2024-27 Model Year | 84 Months | 5.59% APR1 |

Rates are effective as of 08/31/2026. All loans are subject to approval.

- [Money Market Account Rates](https://example.test/#)

Investor’s Choice

| Balance Tier | Dividend Rate | APY |
| --- | --- | --- |
| $100,000+ | 0.40% | 0.40% |

| Term | APR |
| --- | --- |
| 36 Months | 10.49% |

Rates effective 1/1/2026.
"""


def test_parse_tables():
    auto, mm, loan = parse_tables(MD)
    assert auto.context == "Auto Loan Rates"
    assert auto.header == ["Loan Program", "Term", "Annual Percentage Rate (As Low As)"]
    assert auto.rows == [
        ["2024-27 Model Year", "60 Months", "5.39% APR"],
        ["2024-27 Model Year", "84 Months", "5.59% APR"],
    ]
    assert auto.effective == date(2026, 8, 31)
    assert mm.context == "Investor’s Choice"  # bare tab label, link line skipped
    assert mm.rows == [["$100,000+", "0.40%", "0.40%"]]
    assert mm.effective is None  # the date after the next table belongs to that table
    assert loan.effective == date(2026, 1, 1)
    assert auto.raw_rows[0] == "2024-27 Model Year | 60 Months | 5.39% APR"


def test_nested_or_less_tiers_do_not_overlap():
    from kb.extract.rates import table_facts
    from kb.facts import Page

    md = """Home Loans - Purchase

| Program | Rate | Points | APR |
| --- | --- | --- | --- |
| Purchase: 30-Year Fixed Conventional $832,750 or less | 7.25% | 0 | 7.29% |
| Purchase: 30-Year Fixed Conventional $100,000 or less | 7.13% | 0 | 7.27% |
| Purchase: 15-Year Fixed Conventional | 6.75% | 0 | 6.88% |

Rates are effective as of 09/25/2026.
"""
    page = Page("u", "/personal/loans/home-loans", "product", "t", md, "2026-09-28T00:00:00Z")
    apr = {
        (f.term, f.lo, f.hi): f.value
        for f in table_facts(parse_tables(md)[0], page, "05")
        if f.metric == "APR"
    }
    assert apr == {
        (360, 0.0, 100000.0): "7.27%",
        (360, 100000.01, 832750.0): "7.29%",
        (180, 0.0, float("inf")): "6.88%",
    }
