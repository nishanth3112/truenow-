from kb.query import as_of_from, parse


def test_auto_slots():
    q = parse("What's the APR for a 60-month auto loan on a 2025 model-year vehicle?")
    assert (q.intent, q.families, q.term, q.year) == ("rate", ["auto"], 60, 2025)
    assert parse("What's the APR for a 5-year car loan?").term == 60


def test_date_phrase_is_neither_model_year_nor_slot():
    q = parse("As of May 31, 2026, what was the 84-month auto loan rate?")
    assert (q.term, q.year) == (84, None)


def test_as_of_from_question():
    assert as_of_from("What was the 12-month certificate rate as of May 2026?") == "2026-05-31"
    assert as_of_from("What did it pay in June 2026?") == "2026-06-30"
    assert as_of_from("What was it on May 15, 2026?") == "2026-05-15"
    assert as_of_from("What is the routing number?") is None


def test_families_variants_and_amounts():
    q = parse("What dividend rate do I earn on Share Savings with a balance of $15,000?")
    assert (q.families, q.amount) == (["share_savings"], 15000)
    assert parse("What is the APR on a jumbo mortgage over $1 million?").amount == 1_000_000
    assert "arm" in parse("What is your rate on a 7/1 adjustable-rate mortgage?").tags
    cards = parse("What credit cards do you offer and what are their APRs?")
    assert cards.families == ["platinum_visa", "rewards_visa"] and cards.business is None
    assert parse("What is the Business Rewards Visa APR?").business is True
    assert parse("What link shows certificate rates?").intent == "rate_link"
    q = parse("What was the 10-month certificate special APY (not jumbo)?")
    assert "jumbo" not in q.tags and q.excluded == {"jumbo"}
    assert parse("What is the APR on a 30-year fixed refinance for a $300,000 loan?").families == [
        "mortgage"
    ]


def test_routing():
    assert parse("What interest rate do you charge on a construction loan?").families == []
    assert parse("What is the rate on an ATV loan?").families == ["atv"]
    assert parse("What are the drive-up hours?").intent == "other"
    assert parse("Can you repeat the routing number?").intent == "other"


def test_synonyms_map_to_site_words():
    from kb.query import normalize_synonyms

    assert normalize_synonyms("What's the APY on a 12-month CD?") == (
        "What's the APY on a 12-month certificate?"
    )
    assert normalize_synonyms("car loan and home loan rates") == "auto loan and mortgage rates"
    assert normalize_synonyms("lost my ATM card") == "lost my debit card"
    q = normalize_synonyms("What does your online savings account pay?")
    assert q == "What does your Bright Savings account pay?"
    assert parse(q).families == ["bright_savings"]
    assert parse(normalize_synonyms("What are your CD rates?")).families == ["certificate"]
