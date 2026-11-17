"""Markdown table parser: header, cleaned rows, product context and effective date."""

import re
from dataclasses import dataclass
from datetime import date

from kb.normalize import clean_cell, clean_text, effective_dates

SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")


@dataclass
class Table:
    context: str  # nearest short line above the table: the product when no column names it
    context_up: int  # how many lines above the table the context line is
    header: list[str]
    rows: list[list[str]]
    effective: date | None  # first "Rates effective" line after the table, before the next one
    raw_rows: list[str]  # cleaned source lines, used as quotes
    above: list[tuple[int, str]]  # (lines up, text) for up to 30 lines above; links -> their text


def _cells(line: str) -> list[str]:
    return [clean_cell(c) for c in line.strip().strip("|").split("|")]


def _above(lines: list[str], start: int) -> list[tuple[int, str]]:
    out = []
    for up in range(1, min(30, start) + 1):
        line = lines[start - up]
        s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)  # "- [HSA Rates](...)" -> "- HSA Rates"
        s = re.sub(r"[#*_]", "", s).strip(" -")
        if s and not line.lstrip().startswith("|") and len(s) <= 80:
            out.append((up, s))
    return out


def _context(lines: list[str], start: int) -> tuple[str, int]:
    for up in range(1, min(15, start) + 1):
        s = re.sub(r"[#*_]", "", lines[start - up]).strip()
        if not s or s.startswith(("[", "- [", "!", "|")):
            continue
        return (s, up) if len(s) <= 80 else ("", 0)
    return "", 0


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
            j = i + 1
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                # a header row (followed by a separator) starts a new table even without a gap
                if j + 1 < len(lines) and SEPARATOR.match(lines[j + 1].strip()) and j > i + 1:
                    break
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
        context, context_up = _context(lines, i)
        tables.append(
            Table(
                context=context,
                context_up=context_up,
                header=_cells(body[0]),
                rows=[_cells(r) for r in body[1:]],
                effective=eff,
                raw_rows=[" | ".join(_cells(r)) for r in body[1:]],
                above=_above(lines, i),
            )
        )
    return tables
