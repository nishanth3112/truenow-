from datetime import date

from kb.normalize import (
    canonical_url,
    clean_cell,
    effective_dates,
    money_range,
    strip_noise,
    term_months,
    year_range,
)


def test_canonical_url():
    assert (
        canonical_url("https://www.dupaco.com/rates/?hsLang=en#x") == "https://www.dupaco.com/rates"
    )
    assert canonical_url("https://www.dupaco.com/personal/loans/auto-loans/") == (
        "https://www.dupaco.com/personal/loans/auto-motorcycle-loans"
    )
    assert canonical_url("https://www.dupaco.com/privacy-policy?containerType=MODAL&x=1") is None


def test_clean_cell_strips_nbsp_and_glued_footnotes():
    assert clean_cell("5.39% APR1") == "5.39% APR"
    assert clean_cell("0.15%1") == "0.15%"
    assert clean_cell("84\xa0Months") == "84 Months"
    assert clean_cell("12.50% – 19.50%2") == "12.50% - 19.50%"
    assert clean_cell("Annual Percentage Rate (As Low As)1") == "Annual Percentage Rate (As Low As)"
    assert clean_cell("\\*Payment Example") == "Payment Example"


def test_effective_dates_formats():
    text = (
        "Rates are effective as of 08/31/2026. Rates effective 1/1/2026. "
        "which effective as of 08/13/25"
    )
    assert [d for _, d in effective_dates(text)] == [date(2026, 8, 31), date(2026, 1, 1)]
    assert effective_dates("Rates are effective as of 08/13/25 and")[0][1] == date(2025, 8, 13)


def test_year_range():
    assert year_range("2024-27 Model Year") == (2024, 2027)
    assert year_range("2023–26 Model Year") == (2023, 2026)
    assert year_range("Model Year 2026-23") == (2023, 2026)
    assert year_range("2016 Model Year (and older)") == (1900, 2016)
    assert year_range("Share Savings") is None


def test_money_range():
    assert money_range("$10,000 – $24,999.99") == (10000, 24999.99)
    assert money_range("$10,000-24,999") == (10000, 24999)
    assert money_range("$25,000+") == (25000, float("inf"))
    assert money_range("Purchase: 30-Year Fixed Conventional $832750 or less") == (0, 832750)
    assert money_range("$100,000 or less") == (0, 100000)


def test_term_months():
    assert term_months("60 Months") == 60
    assert term_months("10 Month Fixed Certificate Special") == 10
    assert term_months("5 Years") == 60
    assert term_months("2024-27 Model Year") is None


def test_strip_noise():
    md = (
        "keep\n![i](a.jpg)\nTwitter Widget Iframe\nMessenger\n"
        "[Continue](https://x#) Cancel\nalso keep"
    )
    assert strip_noise(md) == "keep\nalso keep"
