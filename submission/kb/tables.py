"""Markdown table parser: header, cleaned rows, product context and effective date."""

import re
from dataclasses import dataclass
from datetime import date

from kb.normalize import clean_cell, clean_text, effective_dates

SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")


@dataclass
class Table:
    context: str  # nearest short line above the table: the product when no column names it
    header: list[str]
    rows: list[list[str]]
    effective: date | None  # first "Rates effective" line after the table, before the next one
    raw_rows: list[str]  # cleaned source lines, used as quotes


def _cells(line: str) -> list[str]:
    return [clean_cell(c) for c in line.strip().strip("|").split("|")]


def _context(lines: list[str], start: int) -> str:
    for line in reversed(lines[max(0, start - 15) : start]):
        s = re.sub(r"[#*_]", "", line).strip()
        if not s or s.startswith(("[", "- [", "!", "|")):
            continue
        return s if len(s) <= 80 else ""
    return ""


def parse_tables(markdown: str) -> list[Table]:
    text = clean_text(markdown)
    lines = text.split("\n")
    offsets, pos = [], 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1
    blocks, i = [], 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            blocks.append((i, j))
            i = j
        else:
            i += 1
    dates = effective_dates(text)
    tables = []
    for n, (i, j) in enumerate(blocks):
        body = [ln.strip() for ln in lines[i:j] if not SEPARATOR.match(ln.strip())]
        if len(body) < 2:
            continue
        end = offsets[j] if j < len(lines) else len(text)
        stop = offsets[blocks[n + 1][0]] if n + 1 < len(blocks) else len(text)
        eff = next((d for off, d in dates if end <= off < stop), None)
        tables.append(
            Table(
                context=_context(lines, i),
                header=_cells(body[0]),
                rows=[_cells(r) for r in body[1:]],
                effective=eff,
                raw_rows=[" | ".join(_cells(r)) for r in body[1:]],
            )
        )
    return tables
