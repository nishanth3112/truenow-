"""Trace a regex across all five snapshots: one line per hit with snapshot, fetched_at, nearest
"effective" date after the hit, URL and the matching line (a table row when the hit is in a table).

    uv run python dev/trace.py "60 Months"
    uv run python dev/trace.py "0\\.35%" --url savings --snap 05
"""

import argparse
import json
import re
from pathlib import Path

SNAPS = Path(__file__).resolve().parents[1] / "snapshots"
EFF = re.compile(r"effective (?:as of )?(\d{1,2}/\d{1,2}/\d{2}(?:\d{2})?)\b", re.IGNORECASE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pattern")
    ap.add_argument("--url", default="", help="only URLs containing this substring")
    ap.add_argument("--snap", default="", help="only snapshot ids starting with this, e.g. 05")
    ap.add_argument(
        "-g",
        "--group",
        action="store_true",
        help="one line per distinct (url, line, eff) with its snapshots",
    )
    ap.add_argument("-w", "--width", type=int, default=160, help="max chars of the matching line")
    args = ap.parse_args()
    rx = re.compile(args.pattern, re.IGNORECASE)
    hits, groups = 0, {}
    for d in sorted(p for p in SNAPS.iterdir() if (p / "manifest.json").exists()):
        m = json.loads((d / "manifest.json").read_text())
        if not m["snapshot_id"].startswith(args.snap):
            continue
        for p in sorted(m["pages"], key=lambda p: p["url"]):
            if args.url not in p["url"]:
                continue
            md = (d / p["file"]).read_text(encoding="utf-8").replace("\xa0", " ")  # tables use NBSP
            effs = [(e.start(), e.group(1)) for e in EFF.finditer(md)]
            for h in rx.finditer(md):
                line_start = md.rfind("\n", 0, h.start()) + 1
                line_end = md.find("\n", h.end())
                line = md[line_start : line_end if line_end >= 0 else None].strip()
                if len(line) > args.width:  # centre long prose lines on the hit
                    c = h.start() - line_start
                    line = "…" + line[max(0, c - args.width // 2) : c + args.width // 2] + "…"
                # footnotes follow their table: take the next date, else the last one before
                after = [e for e in effs if e[0] > h.start()]
                eff = after[0][1] if after else (effs[-1][1] if effs else "-")
                hits += 1
                if args.group:
                    groups.setdefault((p["url"], line, eff), []).append(m["snapshot_id"][:2])
                else:
                    sid, fetched = m["snapshot_id"][:13], p["fetched_at"][:10]
                    print(f"{sid}  {fetched}  eff={eff:<10}  {p['url']}\n    {line}")
    for (url, line, eff), sids in groups.items():
        path = url.removeprefix("https://www.dupaco.com")
        print(f"[{','.join(dict.fromkeys(sids))}] eff={eff:<10} {path}  ::  {line}")
    print(f"{hits} hits")


if __name__ == "__main__":
    main()
