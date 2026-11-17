# truenow

Answers credit-union member questions from five website snapshots (May–Sep 2026): current value, right tier, a source, honest "I don't know". Scope is exactly the assignment PDF. Plan: `plans/knowledge-system.md`; read it first, update Progress when a step lands.

## How to work

1. **Think before coding.** State assumptions. Trace a topic across all five snapshots before changing a rule. If unclear, ask.
2. **Simplicity first.** Minimum code that passes. Stdlib + `openai` only. No speculative abstractions.
3. **Surgical changes.** Touch only what the step needs. Fix the mechanism, never one question.
4. **Goal-driven execution.** Every step has a verify command; loop until it passes, then log the score.

## Rules

- Never edit `harness/` or `eval/`. Never commit snapshots, zips, the PDF or copied page text.
- Never hard-code answers or question text.
- `Answer.text` holds one current, correctly tiered value; stale values go in `conflict_note`.
- Refusals: "It isn't listed; please contact us." No digits.
- Same question + `as_of` gives identical text.
- No live website calls. Optional OpenAI (`gpt-6-luna`): no tools, 6 s timeout, `max_retries=0`; every number must appear in retrieved text. Must work with `OPENAI_API_KEY` unset.
- Deps: requirements files only, exact pins, Python 3.11. Use `uv venv`, `uv pip install -r`, `uv run`; never pyproject.toml.
- `.claude/` stays gitignored.

## Verify

- `uv run pytest -q`
- `uv run python harness/run_eval.py --submission submission --eval eval/public_eval.jsonl`
