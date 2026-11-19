"""In-house BM25 over heading chunks of one snapshot, with an authority boost (rule 2)."""

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from kb.extract.entities import release_body
from kb.facts import SnapshotFacts
from kb.normalize import clean_text

STOP = set(
    "a an the of to for in on at by and or is are was were be been do does did have has had i you "
    "your we our my me us what which who when where how can could would should will it its this "
    "that there their with from about any all if so as not no yes more most also than then just "
    "get got much many dupaco dupaco's".split()
)
# Authority multipliers by page kind: product pages and rate sheets first, releases last.
BOOST = {"product": 1.0, "rate_sheet": 1.0, "landing": 0.85, "pdf": 0.7, "release": 0.6}
NAV = re.compile(r"^\s*(?:[-*]\s*)?(?:\[[^\]]*\]\([^)]*\)\s*)+$|^\s*!\[|^\s*\|?\s*-{3}")
K1, B = 1.2, 0.75
PRODUCT_NOUNS = {"mortgage", "loan", "bond", "card", "account", "certificate", "ira", "insurance"}
GENERIC = {"rate", "apr", "apy", "interest", "fee", "current", "today", "new", "best", "lowest"}
GENERIC |= {"highest", "cheapest", "good", "great", "offer", "kind", "type", "much", "need"}
WINDOW = 80  # tokens per chunk: long FAQ sections are split so one answer is not drowned out


def stem(word: str) -> str:
    if word.endswith(("ibility", "ability")):  # "flexibility" ~ "flexible"
        return word[:-5] + "le"
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokens(text: str) -> list[str]:
    return [
        stem(w) for w in re.findall(r"[a-z0-9$]+(?:[.'][a-z0-9]+)*", text.lower()) if w not in STOP
    ]


@dataclass(frozen=True)
class Chunk:
    url: str
    kind: str
    heading: str
    text: str
    pos: int  # order of the chunk within its page


def _keep(best: dict[str, Chunk], page, heading: str, lines: list[str], pos: int) -> None:
    body = re.sub(r"!\[[^\]]*\]\([^)]*\)|\*\s\*\s\*", " ", " ".join(lines))  # images, rules
    body = re.sub(r"\s+", " ", re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", body))
    body = body.replace("\\*", "*").replace("**", "")
    body = re.sub(r"(?<!\w)[_*]+|[_*]+(?!\w)", "", body).strip()  # stray emphasis marks
    if len(tokens(body)) >= 6:
        c = Chunk(page.url, page.kind, heading, body, pos)
        old = best.get(body)
        if old is None or BOOST[c.kind] > BOOST[old.kind]:
            best[body] = c


def statement(line: str) -> str:
    """A table row reads as a statement ('|Rush fee for debit card|$50.00*|' ->
    'Rush fee for debit card: $50.00*.'), and so does a plain line stating an amount, so
    retrieval and sentence picking can find one row of a fee or price list."""
    if not line.lstrip().startswith("|"):
        line = line.strip()
        # a line that states an amount ('Rush fee for debit card $50.00*') is its own statement
        if re.search(r"\$\d|\d%", line) and not re.search(r"[.!?:]$", line):
            line += "."
        return line
    cells = [c.strip() for c in line.strip().strip("|").split("|") if c.strip()]
    if len(cells) < 2:
        return " ".join(cells)
    return f"{cells[0]}: {' '.join(cells[1:])}."


def chunks(sf: SnapshotFacts) -> list[Chunk]:
    """Split pages at headings (and every ~WINDOW tokens); drop navigation lines; keep each
    repeated text once, on the most authoritative page that shows it."""
    best: dict[str, Chunk] = {}
    for page in sf.pages.values():
        md = release_body(page) if page.kind == "release" else clean_text(page.markdown)
        heading, lines, size, n = page.title, [], 0, 0
        for line in md.split("\n"):
            if line.startswith("#"):
                _keep(best, page, heading, lines, n)
                n += 1
                heading, lines, size = line.lstrip("#").strip(), [], 0
            elif line.strip() and not NAV.match(line):
                lines.append(statement(line))
                size += len(tokens(line))
                if size >= WINDOW:
                    _keep(best, page, heading, lines, n)
                    n += 1
                    lines, size = [], 0
        _keep(best, page, heading, lines, n)
    return list(best.values())


class Index:
    """Built once per snapshot at ingest; search is a dictionary walk over the query's terms."""

    def __init__(self, sf: SnapshotFacts):
        self.chunks = chunks(sf)
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.lengths = []
        self.toks = [tokens(c.heading + " " + c.text) for c in self.chunks]
        for i, toks in enumerate(self.toks):
            tf = Counter(toks)
            self.lengths.append(sum(tf.values()))
            for term, n in tf.items():
                self.postings[term].append((i, n))
        self.avg = sum(self.lengths) / max(1, len(self.lengths))
        n = len(self.chunks)
        self.idf = {
            t: math.log(1 + (n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.postings.items()
        }

    def phrase_seen(self, first: str, second: str, window: int = 3) -> bool:
        """Does `first` occur up to `window` words before `second` anywhere in the snapshot?"""
        both = {i for i, _ in self.postings.get(first, ())} & {
            i for i, _ in self.postings.get(second, ())
        }
        for i in both:
            toks = self.toks[i]
            at = [j for j, t in enumerate(toks) if t == second]
            if any(first in toks[max(0, j - window) : j] for j in at):
                return True
        return False

    def unseen_product(self, query: str) -> str | None:
        """A product the site never names: a word directly before a product noun in the question
        ('reverse mortgage', 'savings bonds') that never occurs near that noun in this snapshot."""
        # every adjacent pair, overlapping: "cash savings bonds" -> cash savings, savings bonds
        for m, noun in re.findall(r"\b(?=([A-Za-z]{3,})\s+([A-Za-z]+)\b)", query):
            pair = tokens(f"{m} {noun}")
            if len(pair) != 2 or pair[1] not in PRODUCT_NOUNS or pair[0] in PRODUCT_NOUNS:
                continue
            if pair[0] not in GENERIC and not self.phrase_seen(*pair):
                return " ".join(pair)
        return None

    def unseen(self, query: str) -> list[str]:
        """Query words the snapshot never uses: the site cannot answer about them."""
        return [t for t in tokens(query) if t not in self.idf]

    def search(self, query: str, k: int = 5) -> list[tuple[float, Chunk, float]]:
        """Top k as (boosted BM25 score, chunk, coverage): coverage is the share of the query's
        idf mass that the chunk contains, used by the refusal policy."""
        q = list(dict.fromkeys(tokens(query)))
        mass = sum(self.idf.get(t, max(self.idf.values(), default=1.0)) for t in q) or 1.0
        scores: dict[int, float] = defaultdict(float)
        hit: dict[int, float] = defaultdict(float)
        for t in q:
            for i, n in self.postings.get(t, ()):
                norm = n + K1 * (1 - B + B * self.lengths[i] / self.avg)
                scores[i] += self.idf[t] * n * (K1 + 1) / norm
                hit[i] += self.idf[t]
        ranked = sorted(scores, key=lambda i: (-scores[i] * BOOST[self.chunks[i].kind], i))[:k]
        return [
            (scores[i] * BOOST[self.chunks[i].kind], self.chunks[i], hit[i] / mass) for i in ranked
        ]
