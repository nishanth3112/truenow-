"""The system answers from snapshots only: no socket is ever opened without an API key."""

import socket
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_runs_offline_without_key(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import solution
    from kb import llm
    from run_eval import load_snapshots

    llm._client = None
    ks = solution.build()
    for snap in load_snapshots(ROOT / "harness/selftest/snapshots"):
        ks.ingest(snap)
    for q, as_of in [
        ("What is the 6-month certificate APY?", None),
        ("What was the 6-month certificate APY in January 2026?", "2026-01-31"),
        ("How much is a lost debit card replacement?", None),
        ("What is the SWIFT code?", None),
    ]:
        a = ks.answer(q, as_of)
        assert isinstance(a.text, str)
    assert isinstance(ks.conflicts(), list)
    with pytest.raises(AssertionError):
        socket.create_connection(("example.com", 443))
