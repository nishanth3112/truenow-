"""Non-rate claims: identifiers and links from site pages; branch hours, closures and dated
sentences (counts, recognitions) from release bodies (rule 4: releases never supply rates)."""

import re

from kb.facts import Claim, Page, SnapshotFacts
from kb.normalize import canonical_url, clean_text
from kb.pages import publish_date

MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
DATE = rf"{MONTH} \d{{1,2}}, 20\d\d"
ROUTING = re.compile(r"(?:routing|ABA) number[^0-9\n]{0,30}(\d{9})\b", re.I)
PHONE = re.compile(r"(?<![\d-])(\d{3}-\d{3}-\d{4})(?![\d-])")
ADDRESS = re.compile(r"^(\d{2,6} [^,\n]{2,40}), ([A-Za-z .]+), (IA|IL|WI),? (\d{5})$", re.M)
LINK = re.compile(r"\[([^\]]{1,80})\]\((https?://[^)\s]+)\)")
DATELINE = re.compile(r"^([A-Z][A-Z .]{2,}), (?:Iowa|Wis\.|Ill\.|Wisconsin|Illinois)\s*[—–-]", re.M)
DAY_LINE = re.compile(
    r"^((?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day(?:\s*[-–]\s*\w+day)?):\s*(.+)$", re.I
)
SECTION = re.compile(r"^\*\*(Lobby|Drive-up|Drive-thru|Drive-through)\*\*\s*(.*)$", re.I)
ORDINALS = "first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth"


def release_body(page: Page) -> str:
    """The release itself, without the teasers for other releases that follow it."""
    text = clean_text(page.markdown)
    cut = text.find("\n#### [")
    return text if cut < 0 else text[:cut]


def _plain(text: str) -> str:
    return re.sub(LINK, r"\1", text).replace("\\*", "*")


def branch_name(body: str) -> str:
    """How the release names the branch it describes."""
    plain = _plain(body)
    for pat in (
        r"phone number for the ([A-Z][\w.]*(?: [A-Z][\w.]*){0,3}) branch",
        r"The ([A-Z][\w.]*(?: [A-Z][\w.]*){0,2}) Dupaco branch",
        r"newest ([A-Z][\w.]*(?: [A-Z][\w.]*){0,2}) Learning Lab",
    ):
        m = re.search(pat, plain)
        if m:
            return f"{m[1]} branch"
    m = DATELINE.search(plain)
    return f"{m[1].title()} branch" if m else ""


def branch_address(body: str) -> str:
    m = re.search(
        r"located at (\d+ [A-Z0-9][\w. ]*?(?:Blvd|Boulevard|Road|Rd|St|Street|Way|Ave|Avenue|"
        r"Highway|Hwy|Drive|Dr)\.?(?: \d+)?)\b",
        _plain(body),
    )
    return m[1] if m else ""


def hours_claims(page: Page, body: str, sid: str) -> list[Claim]:
    out, section, lines = [], None, []

    def flush():
        if section and lines:
            out.append((section, "; ".join(lines)))

    for raw in body.split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = SECTION.match(line)
        if m:
            flush()
            section, lines = ("lobby" if m[1].lower() == "lobby" else "drive-up"), []
            line = m[2].strip()
            if not line:
                continue
        d = DAY_LINE.match(line)
        if section and d:
            lines.append(f"{d[1]}: {d[2]}")
        elif section:
            flush()
            section, lines = None, []
    flush()
    if not out:
        return []
    name, address = branch_name(body), branch_address(body)
    subject = f"{name} ({address})" if address else name
    published = publish_date(body)
    return [
        Claim("hours", subject, sec, value, page.url, published, sid, value) for sec, value in out
    ]


def closure_claims(page: Page, body: str, sid: str) -> list[Claim]:
    plain = _plain(body)
    m = re.search(
        rf"(?:will close|closed on|closing on|last day of service will be)[^.\n]{{0,30}}?({DATE})",
        plain,
    )
    title = re.search(r"^# (.+)$", body, re.M)
    who = re.search(r"([A-Z][\w-]+(?: [A-Z][\w-]+)?) branch", title[1] if title else "")
    if not (m and who):
        return []
    subject = who[1]
    published = publish_date(body)
    out = [Claim("closure", subject, "", m[1], page.url, published, sid, m[0])]
    alt = re.search(
        r"full-service branch(?:es)? at ([A-Z][\w ]+?) and ([A-Z][\w ]+?)(?=[,.—–\"”]| -)", plain
    )
    if alt:
        value = f"{alt[1]} and {alt[2]}"
        out.append(
            Claim("closure_alternative", subject, "", value, page.url, published, sid, alt[0])
        )
    return out


STATED_YEAR = re.compile(r"\b(?:in|during|for)\s+((?:19|20)\d\d)\b", re.I)
LEAD_YEAR = re.compile(r"^\s*In ((?:19|20)\d\d)\b")


def sentence_claims(page: Page, body: str, sid: str) -> list[Claim]:
    """Release sentences that state a number or an ordinal: counts and recognitions. key is the
    year the figure is for: the year the sentence states, else that of the nearest preceding
    'In YYYY' lead-in ('In 2024 alone:' above a bullet list), else ""."""
    published = publish_date(body)
    out, context = [], ""
    # bullets and paragraphs are separate statements; sentences are split inside them
    for block in re.split(r"\n\s*[-*•]\s+|\n\s*\n", _plain(body).replace("**", "")):
        text = re.sub(r"\s+", " ", block).strip()
        lead = LEAD_YEAR.match(text)
        context = lead[1] if lead else context
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z“\"])", text):
            s = s.strip()
            if 20 < len(s) < 400 and (
                re.search(r"\d", s) or re.search(rf"\b({ORDINALS})\b", s, re.I)
            ):
                stated = STATED_YEAR.search(s)
                year = stated[1] if stated else context
                out.append(Claim("sentence", "", year, s, page.url, published, sid, s))
    return out


REGION = re.compile(r"find us in ((?:[A-Z][a-z]+, )*[A-Z][a-z]+,? and [A-Z][a-z]+)")


def eligibility_claims(page: Page, text: str, sid: str) -> list[Claim]:
    """The 'You're Eligible to Join' section: its 'You ...' criteria (one sentence in older
    snapshots, a bullet list in newer ones), up to the 'To join ...' instructions."""
    m = re.search(r"^#+ .*Eligible to Join.*$", text, re.M | re.I)
    if not m:
        return []
    criteria = []
    for line in text[m.end() :].split("\n"):
        line = _plain(line).strip(" -*")
        if line.startswith("#") or line.startswith("To join"):
            break
        for s in re.split(r"(?<=[.!?])\s+", line):
            if s.startswith("To join"):
                break
            if s.startswith("You "):
                criteria.append(s.rstrip("."))
        if line and not line.startswith("You "):
            break
    if not criteria:
        return []
    value = "; ".join(criteria)
    return [Claim("eligibility", "", "", value, page.url, None, sid, m[0].lstrip("# "))]


def site_claims(page: Page, sid: str) -> list[Claim]:
    text = clean_text(page.markdown)
    out = [
        Claim("routing", "", "", m[1], page.url, None, sid, m[0]) for m in ROUTING.finditer(text)
    ]
    out += [Claim("phone", "", "", m[1], page.url, None, sid, m[1]) for m in PHONE.finditer(text)]
    for m in ADDRESS.finditer(text):
        before = [ln.strip() for ln in text[: m.start()].split("\n")[-4:] if ln.strip()]
        # the locator lists branches ("Dupaco Branch") and ATMs ("Surcharge-Free ATM") alike
        key = "branch" if before and before[-1] == "Dupaco Branch" else "other"
        value = f"{m[1]}, {m[2]}, {m[3]} {m[4]}"
        out.append(Claim("address", "", key, value, page.url, None, sid, m[0]))
    for anchor, target in LINK.findall(text):
        if re.match(r"https://join\.dupaco\.com/?$", target) and re.search(
            r"join|member", anchor, re.I
        ):
            out.append(
                Claim("join_url", "", "", "https://join.dupaco.com/", page.url, None, sid, anchor)
            )
        if "locator" in target.lower() and target.startswith("https://www.dupaco.com"):
            url = canonical_url(target)
            out.append(Claim("locator_url", "", "", url, page.url, None, sid, anchor))
    out += eligibility_claims(page, text, sid)
    out += [Claim("region", "", "", m[1], page.url, None, sid, m[0]) for m in REGION.finditer(text)]
    return out


def entity_claims(sf: SnapshotFacts) -> None:
    for page in sf.pages.values():
        if page.kind == "release":
            if page.path.startswith("/newsroom/"):
                body = release_body(page)
                sf.claims += hours_claims(page, body, sf.snapshot_id)
                sf.claims += closure_claims(page, body, sf.snapshot_id)
                sf.claims += sentence_claims(page, body, sf.snapshot_id)
        elif page.kind != "pdf":
            sf.claims += site_claims(page, sf.snapshot_id)
