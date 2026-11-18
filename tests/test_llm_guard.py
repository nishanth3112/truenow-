from types import SimpleNamespace

import pytest
from kb import llm

EXCERPTS = [
    "Home$tart: This initiative provides up to $15,000 toward down payment and closing costs."
]


class Fake:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []
        self.responses = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(output_text=reply)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.delenv("KB_USE_LLM", raising=False)
    llm._cache.clear()
    llm._no_temperature = False
    yield
    llm._client = None


def compose(question="What is Home$tart?", stale=frozenset()):
    return llm.compose(question, EXCERPTS, "05", lambda text: set(stale))


def test_grounded_answer_passes_and_is_cached():
    llm._client = fake = Fake("Home$tart gives first-time buyers up to $15,000.")
    assert compose() == "Home$tart gives first-time buyers up to $15,000."
    assert compose() == "Home$tart gives first-time buyers up to $15,000."
    assert len(fake.calls) == 1
    assert "tools" not in fake.calls[0] and fake.calls[0]["timeout"] == llm.TIMEOUT_S


def test_number_not_in_excerpts_or_superseded_is_rejected():
    llm._client = Fake("Home$tart gives up to $20,000.")
    assert compose() is None
    llm._cache.clear()
    llm._client = Fake("Home$tart gives up to $15,000.")
    assert compose(stale={15000.0}) is None


def test_not_found_errors_and_switch():
    llm._client = Fake(llm.NOT_FOUND)
    assert compose() == llm.NOT_FOUND
    llm._cache.clear()
    llm._client = Fake(TimeoutError("slow"))
    assert compose() is None
    llm._cache.clear()


def test_temperature_retry_and_disable(monkeypatch):
    llm._client = fake = Fake(ValueError("temperature is not supported"), "Up to $15,000.")
    assert compose() == "Up to $15,000."
    assert "temperature" in fake.calls[0] and "temperature" not in fake.calls[1]
    llm._cache.clear()
    monkeypatch.setenv("KB_USE_LLM", "0")
    assert compose() is None
