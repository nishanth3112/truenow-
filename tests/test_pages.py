from datetime import date

from kb.pages import LANDING, OTHER_PRODUCT, OWNER, PDF, RELEASE, page_kind, publish_date, tier

AUTO = ("auto",)


def test_page_kind():
    assert page_kind("/rates") == "rate_sheet"
    assert page_kind("/business-rates") == "rate_sheet"
    assert page_kind("/personal/loans/auto-motorcycle-loans") == "product"
    assert page_kind("/switch-and-earn") == "landing"
    assert page_kind("/calculators/vehicle-affordability") == "landing"
    assert page_kind("/hubfs/fee-schedule.pdf") == "pdf"
    assert page_kind("/newsroom/some-release") == "release"
    assert page_kind("/learn/blog/a-post") == "release"


def test_tier_order_follows_rule_2():
    t = {
        p: tier(page_kind(p), p, AUTO)
        for p in [
            "/rates",
            "/personal/loans/auto-motorcycle-loans",
            "/personal/checking-accounts",
            "/hubfs/x.pdf",
            "/switch-and-earn",
            "/newsroom/x",
        ]
    }
    assert list(t.values()) == [OWNER, OWNER, OTHER_PRODUCT, PDF, LANDING, RELEASE]


def test_publish_date():
    assert publish_date("# Title\n\nApr 6, 2026\n\nBody") == date(2026, 4, 6)
    assert publish_date("no date here") is None
