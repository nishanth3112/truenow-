# truenow

Answers credit-union member questions from five website snapshots with the current value, the
right tier, a cited source, and an honest "I don't know". Built for the interface.ai take-home
assignment. How it works, how it decides what is current, and API keys: see
[`submission/NOTES.md`](submission/NOTES.md).

## Setup

1. Put the five snapshot zips from the participant kit in `snapshots_zip/` at the repo root (they
   are not in this repo). The scorer unpacks them into `snapshots/` on its first run.
2. Install into a clean Python 3.11 environment:

   ```bash
   python3.11 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

## Run the scorer

```bash
python harness/run_eval.py --submission submission --eval eval/public_eval.jsonl
```

No API key is needed. An optional, unevaluated model path runs only when both `KB_USE_LLM=1` and
`OPENAI_API_KEY` are set (see the notes).

## Development

`pip install -r requirements-dev.txt`, then `pytest -q`. Local evals live in `dev/` (see
`plans/knowledge-system.md`).
