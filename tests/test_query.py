from kb.query import parse


def test_auto_slots():
    q = parse("What's the APR for a 60-month auto loan on a 2025 model-year vehicle?")
    assert (q.intent, q.term, q.year) == ("auto_rate", 60, 2025)
    assert parse("What's the APR for a 5-year car loan?").term == 60


def test_date_phrase_is_not_a_model_year():
    q = parse("As of May 31, 2026, what was the 84-month auto loan rate?")
    assert (q.term, q.year) == (84, None)


def test_not_auto():
    assert parse("What credit cards do you offer and what are their APRs?").intent == "other"
    assert parse("What is the rate on an ATV loan?").intent == "other"
    assert parse("What are the drive-up hours?").intent == "other"
