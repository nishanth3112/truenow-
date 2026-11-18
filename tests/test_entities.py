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
