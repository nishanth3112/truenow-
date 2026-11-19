"""Entity claims and answers on synthetic release/page text shaped like traced pages."""

from kb.answer_entities import entity_answer, matches
from kb.extract.entities import entity_claims
from kb.facts import Page, SnapshotFacts

RELEASE = """# Dupaco celebrates East Washington Avenue branch ribbon cutting

November 02, 2022

MADISON, Wis.–Dupaco opened its branch located at 3762 E. Washington Ave in Madison.

The phone number for the East Washington branch is (608) 282-6000. Branch hours are:

**Lobby**

Monday-Friday: 9 a.m.–5 p.m.

Saturday-Sunday: Closed

**Drive-up** Monday-Friday: 9 a.m.–5 p.m.

It has over 600 employees and 23 branch office locations.

#### [Some other release](https://www.dupaco.com/newsroom/other)

GRIMES, Iowa–It has 99 branch office locations.
"""
CLOSURE = """# Dupaco evolves with purpose and member needs, plans Hy-Vee branch closure

June 20, 2025

DUBUQUE, Iowa—Dupaco has made the decision. This location will close March 31, 2026.

“Hy-Vee branch members can use Dupaco full-service branches at Key West and Sycamore Street,”
"""
NEWER = """# Dupaco helps homebuyers

May 05, 2026

In 2026, Dupaco employees helped. It has over 600 employees and 22 branch office locations.
"""
CONTACT = """### Dupaco Credit Union
Dupaco Branch
1465 Sycamore St., Dubuque, IA, 52001
Closed
### Dupaco ATM @ Fareway Food Store
Surcharge-Free ATM
2050 JFK Rd., Dubuque, IA, 52001
Our routing number (273974581). Call 800-373-7600.
"""


def snapshot() -> SnapshotFacts:
    sf = SnapshotFacts("05", "2026-09-28")
    for path, kind, md in [
        ("/newsroom/east-washington", "release", RELEASE),
        ("/newsroom/hy-vee-closure", "release", CLOSURE),
        ("/newsroom/homebuyers", "release", NEWER),
        ("/contact", "landing", CONTACT),
    ]:
        url = "https://www.dupaco.com" + path
        sf.pages[url] = Page(url, path, kind, "t", md, "2026-09-28T00:00:00Z")
    entity_claims(sf)
    return sf


def test_hours_name_their_branch_and_skip_teasers():
    sf = snapshot()
    hours = {(c.subject, c.key): c.value for c in sf.claims if c.kind == "hours"}
    assert hours == {
        ("East Washington branch (3762 E. Washington Ave)", "lobby"): (
            "Monday-Friday: 9 a.m.-5 p.m.; Saturday-Sunday: Closed"
        ),
        (
            "East Washington branch (3762 E. Washington Ave)",
            "drive-up",
        ): "Monday-Friday: 9 a.m.-5 p.m.",
    }
    assert not any("99 branch" in c.value for c in sf.claims)  # teaser for another release


def test_closure_and_alternatives():
    a = entity_answer(snapshot(), "Is the Hy-Vee branch still open today?", "2026-10-31")
    assert a.text.startswith("No. The Hy-Vee branch closed on March 31, 2026")
    assert "Key West and Sycamore Street" in a.text
    before = entity_answer(snapshot(), "When does the Hy-Vee branch close?", "2026-01-15")
    assert "is scheduled to close on March 31, 2026" in before.text


def test_count_takes_newest_release_and_ignores_years():
    a = entity_answer(snapshot(), "How many branches does Dupaco have?", None)
    assert "22 branch office locations" in a.text and "May 5, 2026" in a.text


def test_addresses_identifiers_and_refusals():
    sf = snapshot()
    assert (
        "1465 Sycamore St."
        in entity_answer(sf, "Address of the Sycamore Street branch?", None).text
    )
    assert "273974581" in entity_answer(sf, "What is the routing number?", None).text
    assert "800-373-7600" in entity_answer(sf, "How do I update my contact information?", None).text
    mullan = entity_answer(sf, "What are the lobby hours at the Mullan Avenue branch?", None)
    assert mullan.confident is False
    assert matches(["sycamore", "street"], "1465 Sycamore St., Dubuque")


VTO_2024 = """# Volunteering pays off

April 19, 2024

Logging over 7,200 volunteer hours in 2023, Dupaco employees helped.

In 2023 alone:

- Nearly 700 Dupaco employees volunteered 7,260 hours.
- 294 Dupaco employees used a new paid benefit in 2023 called Volunteer Time Off.
"""
VTO_2025 = """# Volunteering pays off again

April 21, 2025

In 2024 alone:

- 256 Dupaco employees used a paid benefit in 2024 called Volunteer Time Off.
- Dupaco's 602 employees volunteered a total of 6,187 hours.
"""


def yearly() -> SnapshotFacts:
    sf = snapshot()
    for path, md in [("/newsroom/vto-1", VTO_2024), ("/newsroom/vto-2", VTO_2025)]:
        url = "https://www.dupaco.com" + path
        sf.pages[url] = Page(url, path, "release", "t", md, "2026-09-28T00:00:00Z")
    sf.claims = []
    entity_claims(sf)
    return sf


def test_named_year_gets_that_years_figure_only():
    sf = yearly()
    a = entity_answer(sf, "How many employees used Volunteer Time Off in 2023?", None).text
    assert "294" in a and "256" not in a
    hours = entity_answer(sf, "How many volunteer hours did employees log in 2023?", None).text
    assert "7,260" in hours and "6,187" not in hours  # exact figure beats "over 7,200"


def test_relative_year_the_site_does_not_report():
    a = entity_answer(yearly(), "How many employees used Volunteer Time Off last year?", None).text
    assert a.startswith("The site doesn't give a 2025 figure.")
    assert "In 2024: 256" in a and "In 2023: 294" in a


def test_reported_relative_year_most_recent_and_current_counts():
    sf = yearly()
    then = entity_answer(sf, "How many volunteer hours did employees give last year?", "2025-06-01")
    assert "6,187" in then.text and "7,260" not in then.text
    latest = entity_answer(
        sf, "How many employees used VTO in the most recent year reported?", None
    )
    assert "256" in latest.text and "294" not in latest.text
    assert "22 branch office" in entity_answer(sf, "How many branches does Dupaco have?", None).text


JOIN_NEW = """You can find us in Iowa, Illinois and Wisconsin.

## You're Eligible to Join If Any of These Sound Like You

- You live or work within our [charter area](https://x/map.jpg).
- You have an immediate family member who's a member.

To join Dupaco, simply open a savings account with $25 or more.

[Join Dupaco](https://join.dupaco.com/)
"""
JOIN_OLD = """You can find us in Iowa, Illinois and Wisconsin.

## You're Eligible to Join Dupaco If ...

You live or work within our charter area or have an immediate family member who's a member. \
To join, simply open a savings account with $25 or more.

[Join Dupaco](https://join.dupaco.com/)
"""


def with_pages(*pages) -> SnapshotFacts:
    sf = snapshot()
    for path, kind, md in pages:
        url = "https://www.dupaco.com" + path
        sf.pages[url] = Page(url, path, kind, "t", md, "2026-09-28T00:00:00Z")
    sf.claims = []
    entity_claims(sf)
    return sf


def test_eligibility_both_layouts_and_join_link_routing():
    for md, criteria in [
        (JOIN_NEW, "you live or work within our charter area; or you have an immediate family"),
        (JOIN_OLD, "you live or work within our charter area or have an immediate family member"),
    ]:
        sf = with_pages(("/about/join", "product", md))
        a = entity_answer(sf, "Who is eligible to become a Dupaco member?", None)
        assert criteria in a.text and "Iowa, Illinois and Wisconsin" in a.text
        assert a.sources[0].url.endswith("/about/join") and "$25" not in a.text
        assert "join.dupaco.com" in entity_answer(sf, "How do I join Dupaco online?", None).text


def test_hours_cite_release_then_locator():
    locator = "[Find a branch](https://www.dupaco.com/contact#dupaco-locator-widget_1)"
    sf = with_pages(("/personal", "product", locator))
    a = entity_answer(sf, "What are the drive-up hours at the East Washington branch?", None)
    assert [s.url.rsplit("/", 1)[-1] for s in a.sources] == ["east-washington", "contact"]
