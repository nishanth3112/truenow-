"""Append a one-line summary of a harness report to dev/results_log.jsonl.

uv run python dev/log_result.py results/dev/report.json [--note "what changed"]
"""

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report", type=Path)
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    r = json.loads(args.report.read_text())
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    c = r.get("conflicts") or {}
    row = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": commit + ("-dirty" if dirty else ""),
        "report": str(args.report),
        "note": args.note,
        "final": r["final_score"],
        "qa": r["qa_score"],
        "questions": r["questions"],
        "trap_hits": r["stale_trap_hits"],
        "errors": r["errors"],
        "conflicts_f1": c.get("f1"),
        "resolution_acc": c.get("resolution_accuracy"),
        "consistency": r["consistency"]["score"],
        "p95_s": r["speed"].get("p95_s"),
        "ingest_s": r["ingest_seconds"],
        "by_category": {k: v["score"] for k, v in r["by_category"].items()},
    }
    with open(ROOT / "dev/results_log.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    print(json.dumps(row))


if __name__ == "__main__":
    main()
