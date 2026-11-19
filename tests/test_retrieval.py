import time

from kb.facts import Page, SnapshotFacts
from kb.retrieval import Index, tokens

OWNER = """# Overdraft Privilege

- [Checking Accounts](https://www.dupaco.com/checking#)
![icon](https://x/icon.svg)

Overdraft Privilege may cover some items. You pay a $30 overdraft fee per item.
"""
LANDING = """# Overdraft Privilege

Overdraft Privilege may cover some items. You pay a $30 overdraft fee per item.

# Wallets

Add your Dupaco debit and credit cards to Apple Pay, Google Pay or Samsung Pay for fast checkouts.
"""


def snapshot(pages) -> SnapshotFacts:
    sf = SnapshotFacts("05", "2026-09-28")
    for path, kind, md in pages:
        url = "https://www.dupaco.com" + path
        sf.pages[url] = Page(url, path, kind, "t", md, "2026-09-28T00:00:00Z")
    return sf


def test_tokens_stem_and_stopwords():
    assert tokens("What are the Fees for my Accounts?") == ["fee", "account"]
    assert tokens("flexibility") == tokens("flexible")


def test_navigation_dropped_and_duplicates_kept_on_authoritative_page():
    ix = Index(
        snapshot(
            [("/personal/checking-accounts", "product", OWNER), ("/checking", "landing", LANDING)]
        )
    )
    texts = [c.text for c in ix.chunks]
    assert not any("Checking Accounts" in t or "icon" in t for t in texts)
    (fee,) = [c for c in ix.chunks if "$30" in c.text]
    assert fee.url.endswith("/personal/checking-accounts")
    top = ix.search("How much is the overdraft fee?", 1)[0]
    assert top[1] is fee and top[2] == 1.0


def test_unseen_words_and_speed():
    ix = Index(snapshot([("/checking", "landing", LANDING)]))
    assert ix.unseen("What is the SWIFT code?") == ["swift", "code"]
    t = time.perf_counter()
    for _ in range(100):
        ix.search("Which mobile wallets work with my debit card?")
    assert (time.perf_counter() - t) / 100 < 0.05


def test_rows_and_amount_lines_are_statements():
    from kb.retrieval import statement

    assert statement("|Rush fee for debit card|$50.00*|") == "Rush fee for debit card: $50.00*."
    assert statement("Rush fee for debit card $50.00*") == "Rush fee for debit card $50.00*."
    assert statement("a wrapped line of prose") == "a wrapped line of prose"


def test_unseen_product_phrase():
    md = "# Loans\n\nCompare our boat & RV loans and fixed-rate mortgage options for every budget."
    ix = Index(snapshot([("/personal/loans", "product", md)]))
    assert ix.unseen_product("What rate do you offer on a reverse mortgage?") == "reverse mortgage"
    assert ix.unseen_product("Can I cash savings bonds?") == "saving bond"  # overlapping pairs
    assert ix.unseen_product("What's the rate on a boat loan?") is None  # 'boat ... loan' nearby
    assert ix.unseen_product("I need a new car - any loan options?") is None  # not adjacent
