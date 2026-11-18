import re

from kb.facts import Page, SnapshotFacts
from kb.longtail import REFUSAL, long_tail_answer
from kb.retrieval import Index

MD = """# Using your Dupaco cards

Yes! Add your Dupaco cards to Apple Pay, Google Pay or Samsung Pay. Set one as your default.

# Overdraft Privilege

The Overdraft Privilege service fee is $30 per overdraft, with a maximum of one fee per day.
"""


def snapshot() -> SnapshotFacts:
    sf = SnapshotFacts("05", "2026-09-28")
    url = "https://www.dupaco.com/online-and-mobile-banking/mobile-payments"
    sf.pages[url] = Page(url, "/online-and-mobile-banking/mobile-payments", "product", "t", MD, "x")
    for n in range(30):  # unrelated pages, so word weights look like a real site's
        filler = f"# Topic {n}\n\nBudget tips number {n} about saving for goals and planning ahead."
        u = f"https://www.dupaco.com/learn/tip-{n}"
        sf.pages[u] = Page(u, f"/learn/tip-{n}", "product", "t", filler, "x")
    sf.index = Index(sf)
    return sf


def test_extractive_answer_cites_its_page():
    a = long_tail_answer(snapshot(), "Can I add my Dupaco cards to a mobile wallet like Apple Pay?")
    assert "Apple Pay, Google Pay or Samsung Pay" in a.text and a.confident
    assert a.sources[0].url.endswith("/mobile-payments")


def test_refusal_has_no_digits_and_answers_are_deterministic():
    sf = snapshot()
    r = long_tail_answer(sf, "What is Dupaco's SWIFT code?")
    assert r.text == REFUSAL and not r.confident and not re.search(r"\d", r.text)
    q = "How much is the overdraft fee?"
    assert long_tail_answer(sf, q).text == long_tail_answer(sf, q).text
    assert "$30" in long_tail_answer(sf, q).text
