"""Writes dev/dev_eval.jsonl: the 40 public items, one paraphrase each (same group), as_of
variants, refusal probes and held-out topics. Every value below was traced with dev/trace.py
(see dev/TRACES.md).

    uv run python dev/build_dev_eval.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = "https://www.dupaco.com"

PARAPHRASE = {
    "dup-001": "How much does the 17-month certificate special earn?",
    "dup-009": "What's the current 30-year fixed mortgage rate?",
    "dup-011": "What mortgage rates are you offering today?",
    "dup-016": "What APR would I get on a 60-month auto loan for a 2025 car?",
    "dup-034": "List your credit cards and their interest rates.",
    "dup-045": "If I keep $15,000 in Share Savings, what dividend rate do I get?",
    "dup-054": "What's the ABA routing number for Dupaco?",
    "dup-064": "When are Dupaco branch lobbies open?",
    "dup-066": "What time does the drive-up open and close?",
    "dup-068": "Where is Dupaco's Galena branch located?",
    "dup-073": "How many branch locations does Dupaco have?",
    "dup-075": "Can I still bank at the Hy-Vee branch in October 2026?",
    "dup-087": "What has Forbes said about Dupaco?",
    "dup-008": "Where on the website can I compare certificate rates?",
    "dup-052": "What interest do your checking accounts pay?",
    "dup-035": "What's the regular purchase APR on the Platinum Visa card?",
    "dup-145": "Do you publish a rate for a 7/1 ARM?",
    "dup-065": "What hours is the lobby open?",
    "dup-074": "What date does the Hy-Vee branch close?",
    "dup-050": "What APY does Bright Savings pay?",
    "dup-040": "What are the APRs on your credit cards?",
    "dup-080": "Which page has the branch and ATM finder?",
    "dup-049": "Is there a Share Savings tier that earns 0.35% APY?",
    "dup-031": "Tell me about the Home$tart down payment program.",
    "dup-028": "What's the rate on a personal loan over 36 months?",
    "dup-147": "What's the construction loan interest rate?",
    "dup-076": "The Hy-Vee branch closed; which branches should I use instead?",
    "dup-006": "What APY did the 10-month jumbo certificate special pay at the end of May 2026?",
    "dup-055": "Can you tell me the routing number again?",
    "dup-005": "What are your certificate rates?",
    "dup-017": "What's the 84-month auto loan APR for a 2024 model-year car?",
    "dup-081": "Who can join Dupaco?",
    "dup-060": "How do I change the phone number or address on my Dupaco account?",
    "dup-046": "What's the best APY I can get on Share Savings?",
    "dup-102": "What are the hours at the Mullan Avenue branch?",
    "dup-104": "Are lobby hours the same at every Dupaco branch?",
    "dup-088": "How many employees took Volunteer Time Off in the past year?",
    "dup-101": "Do you have loans for college students?",
    "dup-094": "Which mobile wallets work with Dupaco cards?",
    "dup-082": "Where do I apply for membership online?",
}

# (id, question, as_of, expected_answer, must_include, must_not_include, category, expected_sources)
AS_OF = [
    (
        "asof-01",
        "What was the APR for a 60-month auto loan on a 2025 model-year vehicle?",
        "2026-08-31",
        "5.19% APR (2023-26 model-year tier, rates effective 5/1/2026).",
        ["5.19%"],
        ["5.39%", "5.34%"],
        [f"{D}/personal/loans/auto-motorcycle-loans"],
    ),
    (
        "asof-02",
        "What was the APR on an 84-month auto loan for a 2024 vehicle?",
        "2026-06-01",
        "5.39% APR (2023-26 model-year tier).",
        ["5.39%"],
        ["5.59%", "5.54%"],
        [f"{D}/personal/loans/auto-motorcycle-loans"],
    ),
    (
        "asof-03",
        "What was the 12-month certificate APY?",
        "2026-05-15",
        "2.90% APY (2.88% dividend rate).",
        ["2.90%"],
        ["3.40%"],
        [f"{D}/personal/savings-account"],
    ),
    (
        "asof-04",
        "What was the 12-month certificate APY?",
        "2026-07-01",
        "3.40% APY (3.37% dividend rate).",
        ["3.40%"],
        ["2.90%"],
        [f"{D}/personal/savings-account"],
    ),
    (
        "asof-05",
        "What APY did 1st Rate Checking pay on balances of $5,000 to $24,999.99?",
        "2026-05-25",
        "3.00% APY (2.96% dividend rate).",
        ["3.00%"],
        ["2.50%"],
        [f"{D}/personal/checking-accounts"],
    ),
    (
        "asof-06",
        "What was the APY on the 17-month certificate special?",
        "2026-06-30",
        "3.85% APY ($1,000 minimum); the 17-month jumbo special paid 3.95% APY.",
        ["3.85%"],
        ["4.10%", "4.20%"],
        [],
    ),
    (
        "asof-07",
        "What was the APY on the 17-month certificate special?",
        "2026-09-01",
        "3.95% APY ($1,000 minimum); the jumbo special paid 4.05% APY.",
        ["3.95%"],
        ["4.10%", "3.85%"],
        [],
    ),
    (
        "asof-08",
        "What was the 30-year fixed purchase mortgage rate for loans of $100,000 or less?",
        "2026-05-12",
        "5.875% rate / 6.010% APR (effective 05/11/2026).",
        ["5.875"],
        ["7.13%"],
        [f"{D}/personal/loans/home-loans"],
    ),
    (
        "asof-09",
        "What was the 15-year fixed purchase mortgage rate?",
        "2026-08-31",
        "6.000% rate / 6.125% APR (effective 08/26/2026).",
        ["6.000%"],
        ["6.75%"],
        [f"{D}/personal/loans/home-loans"],
    ),
    (
        "asof-10",
        "What did the 25-month certificate special pay?",
        "2026-05-20",
        "3.60% APY ($1,000 minimum); the 25-month jumbo special paid 3.70% APY.",
        ["3.60%"],
        [],
        [],
    ),
    (
        "asof-11",
        "Was there an introductory rate on a HELOC?",
        "2026-06-01",
        "Yes: 1.99% intro APR for the first 3 months, then a variable rate as low as 6.25% APR.",
        ["1.99%"],
        [],
        [],
    ),
    (
        "asof-12",
        "What was the 10-month certificate special APY (not jumbo)?",
        "2026-05-31",
        "3.80% APY ($1,000 minimum).",
        ["3.80%"],
        ["4.00%"],
        [],
    ),
    (
        "asof-13",
        "What is the APR for a 60-month auto loan on a 2025 model-year vehicle?",
        "2026-10-15",
        "5.39% APR (2024-27 model-year tier; latest snapshot).",
        ["5.39%"],
        ["5.19%", "5.34%"],
        [f"{D}/personal/loans/auto-motorcycle-loans"],
    ),
]

REFUSE = [
    ("ref-01", "What is Dupaco's SWIFT code?", None, "Not on the website; say it isn't listed."),
    (
        "ref-02",
        "What does the 25-month certificate special pay right now?",
        None,
        "The 25-month special was on the rate sheet only until May 2026; it is not offered now.",
    ),
    (
        "ref-03",
        "What is the rate on an 84-month certificate?",
        None,
        "Certificates are listed up to 60 months; there is no 84-month certificate rate.",
    ),
    (
        "ref-04",
        "What is the APR on a jumbo mortgage over $1 million?",
        None,
        "The mortgage table stops at $832,750; other amounts are not listed.",
    ),
    (
        "ref-05",
        "What was the 6-month certificate rate?",
        "2026-03-01",
        "No snapshot before 2026-05-12.",
    ),
    (
        "ref-06",
        "What was the APR on a 60-month auto loan for a 2025 vehicle?",
        "2026-01-15",
        "No snapshot before 2026-05-12.",
    ),
    (
        "ref-07",
        "What was the APY on the 17-month certificate special?",
        "2026-05-15",
        "The 17-month special did not exist yet on that date (first listed on 2026-06-09).",
    ),
    (
        "ref-08",
        "What is the introductory HELOC rate right now?",
        None,
        "No HELOC intro rate is listed since August 2026; only the standard 6.25% APR.",
    ),
]

HELDOUT = [
    (
        "ho-01",
        "What APY does a Health Savings Account earn with $15,000?",
        "0.30% APY ($10,000-$24,999.99).",
        ["0.30%"],
        ["0.15%", "0.35%"],
        [f"{D}/personal/savings-account"],
    ),
    (
        "ho-02",
        "What is the money market rate for balances of $100,000 or more?",
        "Investor's Choice Money Market 0.40% APY ($100,000+).",
        ["0.40%"],
        ["0.35%"],
        [f"{D}/personal/savings-account"],
    ),
    (
        "ho-03",
        "What is the top High-Yield Savings APY?",
        "2.45% APY at $1,000,000+.",
        ["2.45%"],
        ["2.25%"],
        [],
    ),
    (
        "ho-04",
        "What does Launchpad Savings pay?",
        "3.25% APY (3.21% dividend) on $5-$1,000.",
        ["3.25%"],
        [],
        [],
    ),
    ("ho-05", "What APY does a Holiday Club account earn?", "0.20% APY.", ["0.20%"], [], []),
    (
        "ho-06",
        "What is the 24-month certificate APY?",
        "2.50% APY.",
        ["2.50%"],
        ["2.70%", "2.10%"],
        [],
    ),
    ("ho-07", "What is the 60-month certificate APY?", "1.80% APY.", ["1.80%"], ["1.90%"], []),
    ("ho-08", "What is the 6-month certificate APY?", "3.40% APY.", ["3.40%"], [], []),
    (
        "ho-09",
        "What is the HELOC rate?",
        "As low as 6.25% APR (standard).",
        ["6.25%"],
        ["1.99%"],
        [f"{D}/personal/loans/home-equity"],
    ),
    (
        "ho-10",
        "What is the APR on a 10-year home equity loan?",
        "7.24% APR (120 months).",
        ["7.24%"],
        ["6.74%"],
        [],
    ),
    (
        "ho-11",
        "What is the rate on a 180-month boat or RV loan of $40,000 or more?",
        "10.04% APR.",
        ["10.04%"],
        [],
        [f"{D}/personal/loans/recreational-loans"],
    ),
    (
        "ho-12",
        "What is the APR range on the Rewards Visa?",
        "15.50%-21.00% APR.",
        ["15.5", "21"],
        ["12.5"],
        [],
    ),
    (
        "ho-13",
        "What is the APR on the Business Rewards Visa?",
        "Variable 20.50% APR.",
        ["20.5"],
        ["15.5"],
        [f"{D}/business/credit-cards"],
    ),
    (
        "ho-14",
        "What APY does Business 1st Rate Checking pay on $10,000?",
        "2.50% APY ($5,000-$24,999.99).",
        ["2.50%"],
        ["3.00%"],
        [f"{D}/business/checking-accounts"],
    ),
    (
        "ho-15",
        "What is the APR on a 15-year fixed purchase mortgage?",
        "6.88% APR (6.75% rate).",
        ["6.88%"],
        ["6.125%", "5.623%"],
        [f"{D}/personal/loans/home-loans"],
    ),
    (
        "ho-16",
        "What is the 20-year fixed purchase mortgage rate?",
        "7.13% rate / 7.26% APR.",
        ["7.13%"],
        ["5.875%", "6.000%"],
        [f"{D}/personal/loans/home-loans"],
    ),
    (
        "ho-17",
        "What is the APR on a 30-year fixed refinance for a $300,000 loan?",
        "7.33% APR (7.25% rate).",
        ["7.33%"],
        ["6.072%", "6.575%"],
        [f"{D}/personal/loans/home-loans"],
    ),
    (
        "ho-18",
        "What's the APR for a 72-month loan on a 2022 car?",
        "5.79% APR (2021-23 model-year tier).",
        ["5.79%"],
        ["5.74%", "5.59%"],
        [f"{D}/personal/loans/auto-motorcycle-loans"],
    ),
    (
        "ho-19",
        "What is the APR on a 60-month personal loan?",
        "12.49% APR.",
        ["12.49%"],
        [],
        [f"{D}/personal/loans/personal-loans"],
    ),
    (
        "ho-20",
        "How much is the overdraft fee?",
        "$30 per item (Overdraft Privilege).",
        ["$30"],
        [],
        [],
    ),
    (
        "ho-21",
        "What is the address of the Sycamore Street branch?",
        "1465 Sycamore St., Dubuque, IA 52001.",
        ["1465 Sycamore", "52001"],
        [],
        [f"{D}/contact"],
    ),
    (
        "ho-22",
        "What is the APR on a home improvement loan of $20,001 to $50,000?",
        "8.75% APR (180 months).",
        ["8.75%"],
        ["8.50%"],
        [],
    ),
    (
        "ho-23",
        "What does the Achieve Money Market account pay?",
        "Introductory 4.00% dividend rate (3.66% APY) for the first 6 months, then 3.20% dividend "
        "rate (3.25% APY); $25,000 to open. Only on /earn-more (linked from the savings page).",
        ["4.00%", "3.66%", "25,000"],
        [],
        [f"{D}/earn-more"],
    ),
]


def main():
    public = [
        json.loads(line)
        for line in (ROOT / "eval/public_eval.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert set(PARAPHRASE) == {it["id"] for it in public}
    out = []
    for it in public:
        it = {**it, "group": it["group"] or it["id"], "split": "public"}
        out.append(it)
        out.append(
            {**it, "id": it["id"] + "-p", "question": PARAPHRASE[it["id"]], "split": "paraphrase"}
        )
    for i, q, as_of, exp, inc, exc, src in AS_OF:
        out.append(
            {
                "id": i,
                "question": q,
                "as_of": as_of,
                "expected_answer": exp,
                "must_include": inc,
                "must_not_include": exc,
                "category": "temporal_as_of",
                "weight": 1.5,
                "expected_sources": src,
                "group": None,
                "split": "as_of",
            }
        )
    for i, q, as_of, exp in REFUSE:
        out.append(
            {
                "id": i,
                "question": q,
                "as_of": as_of,
                "expected_answer": exp,
                "must_include": [],
                "must_not_include": [],
                "category": "should_refuse",
                "weight": 2.0,
                "expected_sources": [],
                "group": None,
                "split": "refusal",
            }
        )
    for i, q, exp, inc, exc, src in HELDOUT:
        out.append(
            {
                "id": i,
                "question": q,
                "as_of": None,
                "expected_answer": exp,
                "must_include": inc,
                "must_not_include": exc,
                "category": "current_value",
                "weight": 1.0,
                "expected_sources": src,
                "group": None,
                "split": "heldout",
            }
        )
    assert len({it["id"] for it in out}) == len(out)
    (ROOT / "dev/dev_eval.jsonl").write_text("".join(json.dumps(it) + "\n" for it in out))
    print(f"{len(out)} items")


if __name__ == "__main__":
    main()
