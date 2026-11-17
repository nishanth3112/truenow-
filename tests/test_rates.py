"""Extractor cases modelled on traced table shapes (dev/TRACES.md), with synthetic text."""

from datetime import date

from kb.extract.rates import card_prose_facts, table_facts
from kb.facts import Page
from kb.normalize import rate_value
from kb.tables import parse_tables


def page(path, md):
    kind = "rate_sheet" if path in ("/rates", "/business-rates") else "product"
    return Page("https://www.dupaco.com" + path, path, kind, "t", md, "2026-09-28T00:00:00Z")


def facts(path, md):
    p = page(path, md)
    return [f for t in parse_tables(md) for f in table_facts(t, p, "05")]


def test_rate_value():
    assert rate_value("12.50% - 19.50% APR") == "12.50%-19.50%"
    assert rate_value("2.90% APR for 6 mos. (after that 12.50% - 19.50% APR)") == "2.90%"
    assert rate_value("6.125%") == "6.125%"
    assert rate_value("- Up to 3.00% APY on your balance") is None


def test_product_from_tab_link_above_table():
    md = """- [Health Savings Account Rates](https://x/#)

Saving Account Rates

| Balance | Dividend Rate | Annual Percentage Yield (APY)1 | Min. to Open |
| --- | --- | --- | --- |
| $25,000+ | 0.35% | 0.35% | $25 |
"""
    fs = facts("/personal/savings-account", md)
    assert {(f.family, f.metric, f.value, f.lo) for f in fs} == {
        ("hsa", "dividend", "0.35%", 25000.0),
        ("hsa", "APY", "0.35%", 25000.0),
    }


def test_business_variant_and_glued_tables():
    md = """Business 1st Rate Checking Account

| | |
| --- | --- |
| - Up to 3.00% APY on your balance | |
| Balance | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |
| --- | --- | --- | --- |
| $5,000 - $24,999.99 | 2.96% | 3.00% | $5,000 |
"""
    fs = facts("/business-rates", md)
    assert {(f.family, f.variant, f.metric, f.value) for f in fs} == {
        ("first_rate_checking", "business", "dividend", "2.96%"),
        ("first_rate_checking", "business", "APY", "3.00%"),
    }


def test_cards_keep_standard_and_intro_apart():
    md = """Platinum Visa

| Card Type | APR |
| --- | --- |
| Platinum Visa Rate | 12.50% - 19.50%2 |
| Introductory Balance Transfer Rate | 2.90%1 |
"""
    fs = facts("/rates", md)
    assert {(f.family, f.variant, f.value) for f in fs} == {
        ("platinum_visa", "", "12.50%-19.50%"),
        ("platinum_visa", "intro", "2.90%"),
    }


def test_card_fine_print_sentence():
    md = (
        "_\\*Platinum Visa Introductory Balance Transfer Rate: The 2.90% rate expires, at which "
        "time the APR will revert back to the current standard APR, which effective 10/1/2025 is "
        "a variable rate from 13.00% APR to 20.00% APR based on your creditworthiness."
    )
    (f,) = card_prose_facts(page("/personal/credit-cards", md), "01")
    assert (f.family, f.value, f.effective, f.tier) == (
        "platinum_visa",
        "13.00%-20.00%",
        date(2025, 10, 1),
        1,
    )


def test_certificate_variants():
    md = """Special

| Term | Dividend Rate | Annual Percentage Yield (APY) | Min. to Earn |
| --- | --- | --- | --- |
| 10 Month Fixed Jumbo Certificate Special | 3.86% | 3.90%1 | $100,000 |
| 10 Month Fixed Certificate Special | 3.76% | 3.80%2 | $1,000 |
"""
    apy = {
        f.variant: (f.term, f.value, f.minimum) for f in facts("/rates", md) if f.metric == "APY"
    }
    assert apy == {
        "jumbo special": (10, "3.90%", "$100,000"),
        "special": (10, "3.80%", "$1,000"),
    }


def test_landing_page_linked_by_product_name_becomes_owner():
    from kb.extract.rates import named_on_product_pages, promote_linked_landing_pages
    from kb.facts import SnapshotFacts

    landing_md = """Money Market Rates

| Account Type | Balance Tier | Dividend Rate | Annual Percentage Yield (APY) |
| --- | --- | --- | --- |
| Achieve Money Market | $25,000-$99,999.99 | 3.20% | 3.25% |
"""
    sf = SnapshotFacts("05", "2026-09-28")
    for path, kind, md in [
        (
            "/personal/savings-account",
            "product",
            "Choose [Achieve](https://www.dupaco.com/earn-more)",
        ),
        ("/earn-more", "landing", landing_md),
        ("/homebuying-guidance", "landing", "Mortgage Rate Relief Program"),
    ]:
        sf.pages["https://www.dupaco.com" + path] = Page(
            "https://www.dupaco.com" + path, path, kind, "t", md, "2026-09-28T00:00:00Z"
        )
    p = sf.pages["https://www.dupaco.com/earn-more"]
    sf.facts = table_facts(parse_tables(landing_md)[0], p, "05")
    assert {f.tier for f in sf.facts} == {4}
    promote_linked_landing_pages(sf)
    assert {f.tier for f in sf.facts} == {1}
    assert named_on_product_pages(sf, sf.facts[0])
    relief = sf.facts[0].__class__(
        **{**sf.facts[0].__dict__, "family": "mortgage", "variant": "relief"}
    )
    assert not named_on_product_pages(sf, relief)  # named only on a landing page: expired
