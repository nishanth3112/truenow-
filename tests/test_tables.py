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
