---
authority: decision
status: live
---

# Plan: knowledge system that knows what's true now

Source: interface.ai take-home (assignment PDF + participant kit). Graded by `harness/run_eval.py`
on a hidden question set: accuracy 55%, conflicts 15%, consistency 15%, speed 15%
(consistency and speed are multiplied by accuracy).

**Scope is exactly what the assignment PDF asks for.** No demo, UI or video (dropped 2026-11-17).

## What the assignment PDF requires, and where each item is met

| PDF requirement | Met by |
| --- | --- |
| Folder with `solution.py` whose `build()` returns an object with exactly `ingest`, `answer(question, as_of=None)`, `conflicts()`; shapes from `harness/contract.py`; nothing renamed | Steps 0.1, 1.3 |
| `ingest` called once per snapshot, oldest first; keep history | Steps 1.1, 1.2 |
| `answer` without `as_of` uses the newest snapshot; with a date, the site as it stood that day | Step 1.3, currency rule 1 |
| Current value, right tier, a source, honest "I don't know" ("It isn't listed; please contact us") | Phases 2–4 |
| `conflicts()` lists contradictions with values, sources, resolution, reason | Phase 5 |
| Respect qualifiers (term, rate vs APY, standard vs jumbo, personal vs business) | Currency rule 5, Phase 2 |
| Write the "what is current" rules down | `dev/TRACES.md` (Step 0.2), NOTES.md (Step 6.3) |
| Extra packages in `requirements.txt`; installed into clean Python 3.11 | Step 0.1, Step 6.2 |
| Short NOTES.md: how it works, how it decides what's current, which API keys; say so if a paid API is used | Step 6.3 |
| `python harness/run_eval.py --submission <folder> --eval eval/public_eval.jsonl` runs cleanly from a fresh clone | Step 6.2 |
| Answer only from the snapshots; no live website calls | Rules in `CLAUDE.md`; `tests/test_no_network.py` (Step 4.3) |
| Each answer call < 60 s; loading < 30 min | Step 4.3 timeouts; Step 6.2 timings |
| Don't redistribute the data | `.gitignore`, `tests/test_repo_invariants.py` |
| Public repo, organizers have read access; share URL + commit | Step 6.2, Phase 7 |
| Changing `harness/` or `eval/` has no effect; hard-coding public answers won't help | Rules in `CLAUDE.md`; `tests/test_repo_invariants.py` |

## Evidence this plan is built on (measured 2026-11-16 on the kit)

- Starter baseline on the public eval: final 0.093 (qa 0.093, p95 0.22 s). No conflicts gold ships
  with the public set, so the conflicts pillar is not measured locally without our own gold.
- Snapshots: 637 / 634 / 635 / 683 / 705 pages; 722 unique URLs, 621 present in all five.
  A snapshot is cumulative: pages not re-fetched keep their old copy (`/switch-and-earn` in the
  2026-09-28 snapshot has fetched_at 2026-06-09).
- Latest snapshot: 38 pages carry markdown tables with `%` values; 29 carry "effective as of" text.
  Rate questions are a structured-extraction problem over a small page set.
- Page-level diffing is useless: 615 of 633 shared pages changed between 01 and 02, but e.g.
  `/personal/loans/student-loans` differs only by six chat-widget lines. Diff facts, not pages.
- Trap values that appear in **no** snapshot: routing 271176899, `9.9%`,
  `info.dupaco.com/certificate_account_rates`, `info.dupaco.com/how_to_join`,
  `/locations/branch-hours`, `6.7%`, and "Jump Start" / "up to 0.35%". They catch answers drawn
  from model memory.
- `3% APY` does exist, and is stale: 1st Rate Checking paid 3.00% APY on $5,000–$24,999.99 in
  snapshots 01–02 (2.50% from 03), and a business checking promo said "up to 3.00% APY" in 01–02.
- Same-number-different-product: `0.35%` on `/personal/savings-account` is Investor's Choice
  Money Market ($25,000–$99,999.99) and Health Savings Account ($25,000+), not Share Savings.
- Tier labels drift: auto table went from "2023-26 Model Year" to "2024-27 Model Year";
  parse ranges, never match labels.
- Mortgage table (`/personal/loans/home-loans`) is keyed by purchase/refinance, term and loan
  amount ("$100,000 or less" … "$832,750 or less"); columns Rate | Points | APR | Payment.
  On 2026-09-28: 30-year purchase 7.13% ($100k) to 7.25% ($832,750); 15-year 6.75% rate / 6.88% APR.
- The eval's `expected_answer` prose is not always consistent with the data (dup-011 prose says
  15-year 6.25%; the 2026-09-28 table says 6.75%). Score against `must_include` /
  `must_not_include`; verify everything against snapshots.
- The hidden set is larger than the public one and includes rewordings, `as_of` questions and
  changed facts (assignment PDF). Generalize across every product; never tune to one item.
- What the harness rewards, and why each is also the right product behaviour:
  - A member gets one current value. An answer that also repeats a stale or wrong value scores
    zero, so competing values go in `conflict_note` (the contract's field for explaining a choice).
  - "I don't know" must not carry numbers that look like an answer; the harness treats them as a
    guess.
  - Rewordings and repeats must give the same numbers (consistency), and p95 latency drives speed.
  - Conflicts are scored on precision and recall, so a short accurate list beats an exhaustive one.

## Architecture (target)

Ingest (deterministic, no LLM, untimed, must finish < 30 min):
1. Canonicalize URLs (drop query/fragment/trailing slash, merge `hsLang` variants, drop modal
   privacy-policy URLs, alias `auto-loans/` ↔ `auto-motorcycle-loans`). Strip widget/form noise.
2. Classify each page: kind (rate sheet, product, about/contact, PDF, calculator/landing page,
   blog, newsroom), authority tier, effective dates, publish dates.
3. Parse every markdown table into rows → facts; pattern extractors for routing number, phone,
   addresses, hours, URLs, counts, dated claims.
4. Store per-snapshot fact tables (the temporal ledger) and a fact-level change log across
   snapshots. Build an in-house BM25 index over heading-chunked sections per snapshot.

Answer (in memory):
1. Resolve the snapshot: `as_of` field, else a date phrase in the question, else latest.
2. Normalize the question (number words, units, synonyms), detect intent and slots.
3. Structured path: slot-filled fact lookup → winner by currency rules → template with source.
   Competing values go to `conflict_note`, never `text`.
4. Long tail: BM25 top-k from authoritative pages → OpenAI model composes (if key present) under a
   number-grounding guard, else extractive sentences. Low evidence → refusal with no digits.

Currency rules (tuned in Phase 0 traces, then frozen in NOTES.md):
1. `as_of` → latest snapshot with taken_on ≤ as_of; before 2026-05-12 → refuse.
2. Authority: product owner page or rate sheet > other product pages > PDFs > calculators and
   landing pages > blog and newsroom.
3. Same tier: later effective date wins, then later fetched_at. A table's effective date is the
   first "Rates (are) effective (as of) D" line after the table (footnotes follow tables); formats
   M/D/YYYY, MM/DD/YYYY and MM/DD/YY.
4. Expired promotions never supply a current value. Newsroom and blog releases may answer counts,
   recognitions, hours, closures and program facts, newest publish date first; never rates. Hours
   always name the branch they describe.
5. Qualifiers (term, model-year range, balance tier, loan amount, purchase/refinance, APR/APY/
   dividend rate, personal/business, standard/jumbo/special) are part of the fact key.
6. Missing qualifier: lead tier plus the range within the same product, then ask which one;
   never values from another product.
7. Cite the highest-tier page that holds the winning value.

## Phases

### Phase 0: Setup and ground truth
Verified when: repo invariants test passes, traces document the rules with evidence, and the
starter's dev-eval baseline is logged.

#### Step 0.1: Repo scaffold (Size: S)
- Acceptance criteria: kit files (`harness/`, `eval/`, `starter/`, `snapshots/README.md`) committed
  unchanged; zips, PDF and unpacked snapshots ignored; `submission/` holds a copy of the starter
  `solution.py`, an exact-pinned `requirements.txt` and a stub `NOTES.md`; no `pyproject.toml` or
  `uv.lock` anywhere in the repo.
- Verification command: `uv venv --python 3.11 --allow-existing && uv pip install -r requirements-dev.txt && uv run pytest -q tests/test_repo_invariants.py`
  and `git ls-files | grep -E '^snapshots/0|^snapshots_zip/|\.zip$|\.pdf$|pyproject\.toml|uv\.lock'` returns nothing
  (anchored, because `harness/selftest/snapshots/` holds the kit's own synthetic fixtures and stays committed).
- Files likely touched: `submission/requirements.txt` (runtime: `openai==<exact>`),
  `requirements.txt` (root; one line `-r submission/requirements.txt`), `requirements-dev.txt`
  (`-r requirements.txt` + pytest, ruff, exact pins), `.python-version` (3.11), `.gitignore`,
  `CLAUDE.md`, `plans/knowledge-system.md`, `tests/test_repo_invariants.py` (sha256 of every file
  under `harness/` and `eval/`; no tracked data; `pyproject.toml` and `uv.lock` absent).
- Test seams: repo invariants test.
- Blocked by: none.

#### Step 0.2: Trace tool and topic traces (Size: M)
- Acceptance criteria: `dev/trace.py <regex>` prints value, page, snapshot, fetched_at and
  effective date for every hit; ≥15 topics traced; `dev/TRACES.md` states the currency rules with
  page/snapshot evidence and lists where each public trap value lives (or that it lives nowhere).
  Evidence is cited as URL + snapshot + value, never copied paragraphs (the data must not be
  redistributed).
- Topics: auto 60/84 by model year; mortgage 30/15 by amount; Share Savings tiers; money market;
  HSA; Bright Savings; checking; certificates incl. 10- and 17-month specials and jumbo; personal
  loan 36-month; credit cards (personal + business); routing number; branch count; Forbes count;
  lobby and drive-up hours (not on `/contact`; find where); Hy-Vee closure; join URL; rates URL;
  Home$tart.
- Verification command: `uv run python dev/trace.py "60 Months"`.
- Test seams: none (research step).
- Blocked by: 0.1.

#### Step 0.3: Dev eval and local conflicts gold (Size: M)
- Acceptance criteria: `dev/dev_eval.jsonl` ≈ 118 items (public 40; one paraphrase each with the
  same `group`; ≥10 `as_of` variants; ≥8 refusal probes; ≥20 held-out topics marked
  `"split": "heldout"`); `dev/conflicts_gold_local.json` ≈ 20 entries in the kit's gold format;
  `dev/log_result.py` appends report summaries to `dev/results_log.jsonl`.
- Verification command: `uv run python harness/run_eval.py --submission starter --eval dev/dev_eval.jsonl --conflicts-gold dev/conflicts_gold_local.json --out results/dev && uv run python dev/log_result.py results/dev/report.json`.
- Test seams: harness.
- Blocked by: 0.2.

### Phase 1: Vertical slice — auto loans end to end
Verified when: dup-016 and dup-017 pass, an auto `as_of` variant passes, and the 5.34% vs 5.39%
conflict is emitted with resolution 5.39%.

#### Step 1.1: Ingest core (Size: M)
- Acceptance criteria: URL canonicalization and noise stripping; page kind/tier/date extraction;
  table parser maps headers, strips footnote markers (`5.39% APR1` → 5.39% APR); normalize
  non-breaking spaces; strip glued footnote digits (`0.15%1`, `10.49%1`); take the product from the
  nearest short line above product-less tables (a heading or a bare tab label such as
  `Investor's Choice`); parse ranges (model years, balances, loan amounts with or without commas,
  en dash or hyphen).
- Verification command: `uv run pytest -q tests/test_tables.py tests/test_normalize.py tests/test_pages.py`.
- Files likely touched: `submission/kb/normalize.py`, `submission/kb/pages.py`, `submission/kb/tables.py`.
- Test seams: unit tests on small synthetic markdown fixtures (never real page dumps).
- Blocked by: 0.3.

#### Step 1.2: Fact ledger, resolver, auto extractor (Size: M)
- Acceptance criteria: per-snapshot fact tables plus change log; resolver implements currency
  rules 1–5; model-year ranges parsed to integer bounds.
- Verification command: `uv run pytest -q tests/test_resolve.py`.
- Files likely touched: `submission/kb/facts.py`, `submission/kb/resolve.py`, `submission/kb/extract/rates.py`.
- Test seams: resolver unit tests built from traced cases.
- Blocked by: 1.1.

#### Step 1.3: Query parser, templates, conflicts, wiring (Size: M)
- Acceptance criteria: auto questions answered with value + source; `as_of` honoured; auto
  conflict emitted; result logged.
- Verification command: `uv run python harness/run_eval.py --submission submission --eval eval/public_eval.jsonl`, then
  `uv run python harness/run_eval.py --submission submission --eval dev/dev_eval.jsonl --conflicts-gold dev/conflicts_gold_local.json --out results/dev`.
- Files likely touched: `submission/kb/query.py`, `submission/kb/answer.py`,
  `submission/kb/conflicts.py`, `submission/solution.py`.
- Test seams: harness.
- Blocked by: 1.2.

### Phase 2: Every rate table
Verified when: tier_disambiguation, stale_trap and list_completeness public items pass with zero
trap hits, and held-out rate items do not regress.

#### Step 2.1: Deposits (Size: M)
- Acceptance criteria: Share Savings tiers, money market, HSA, Bright Savings, checking,
  certificates (regular, jumbo, specials).
- Verification command: dev eval; check dup-001, -006, -045, -046, -049, -050, -052.
- Blocked by: 1.3.

#### Step 2.2: Loans and cards (Size: M)
- Acceptance criteria: mortgage (purchase/refinance × term × amount), personal, recreational,
  HELOC, student, credit cards personal + business (standard vs intro APR kept separate).
- Verification command: dev eval; check dup-009, -011, -028, -034, -035, -040.
- Blocked by: 1.3.

#### Step 2.3: Missing-qualifier policy (Size: S)
- Acceptance criteria: currency rule 6 implemented; paraphrase groups for rate items agree.
- Verification command: dev eval paraphrase consistency for rate groups = 1.0.
- Blocked by: 2.1, 2.2.

### Phase 3: Entities and branch info
Verified when: entity_attribution and branch_info items pass and the Mullan Avenue probe refuses.

#### Step 3.1: Identifiers and links (Size: S)
- Acceptance criteria: routing number, phone, join URL, rates URL, locator URL; URL intents put
  the URL in `text`.
- Verification command: dev eval; check dup-008, -054, -055, -060, -080, -082.
- Blocked by: 1.3.

#### Step 3.2: Branches (Size: M)
- Acceptance criteria: addresses, lobby and drive-up schedules (general question → typical
  schedule + variants + ask which branch), branch count, closures with dates and alternatives;
  ignore the crawl-time Open/Closed status on `/contact`.
- Verification command: dev eval; check dup-064, -065, -066, -068, -073, -074, -075, -076, -102, -104.
- Blocked by: 3.1.

#### Step 3.3: Dated claims (Size: S)
- Acceptance criteria: counts and recognitions resolved by newest dated source (Forbes "fifth"
  beats "fourth"; VTO 294).
- Verification command: dev eval; check dup-087, -088.
- Blocked by: 3.1.

### Phase 4: Long tail and honesty
Verified when: refusal probes all pass with no digits, long-tail items pass with and without an
API key, and the LLM path is kept only if it raises dev qa net of speed and consistency.

#### Step 4.1: BM25 retrieval (Size: S)
- Acceptance criteria: in-house BM25 over heading chunks per snapshot with authority boost;
  < 50 ms per query.
- Verification command: `uv run pytest -q tests/test_retrieval.py`.
- Blocked by: 1.3.

#### Step 4.2: Extractive composer and refusal policy (Size: M)
- Acceptance criteria: extractive answers from top chunk; refusal threshold calibrated on dev
  refusal probes; refusal text follows the PDF's example ("It isn't listed; please contact us")
  and has no digits.
- Verification command: `uv run pytest -q tests/test_answers.py` and dev eval should_refuse = 1.0.
- Blocked by: 4.1.

#### Step 4.3: Optional OpenAI composer (Size: M)
- Acceptance criteria: lazy `openai` import; Responses API; model from `KB_LLM_MODEL` (default
  `gpt-6-luna`) and reasoning effort from `KB_LLM_EFFORT` (default `none`); temperature 0 / seed
  only if the model accepts them (check on the first call; the cache provides repeat consistency
  regardless); 6 s timeout with `max_retries=0` (the SDK retries by default,
  which would multiply the worst case) then extractive fallback; no tools passed to the API (no
  web search or fetch); prompt answers only
  from excerpts or returns NOT_FOUND; number guard: every number in an LLM answer must
  appear in the question or in excerpts from the resolved snapshot, and must not equal a value the
  resolver marked as superseded for the same product; in-memory cache keyed by (normalized question, snapshot_id); `KB_USE_LLM=0` disables.
- Verification command: `uv run pytest -q tests/test_llm_guard.py tests/test_no_network.py`, then dev eval with and without
  the key; both logged.
- Blocked by: 4.2.

### Phase 5: Conflicts curation (Size: M)
Verified when: local conflicts F1 and resolution accuracy are logged and stable across a
re-run.
- Acceptance criteria: conflicts from the ledger (same key, different values) checked within
  **every** snapshot, not just the latest (this covers lc-13, the 01–03 card fine print); one
  conflict per fact, listing every page that shows a competing value as its sources (the scorer
  matches conflicts one-to-one, so splitting a fact across entries only costs precision); ranked
  by confidence and capped (start at 40); topics include product + qualifier + metric; values
  carry units; each has resolution and reason. Pure changes between snapshots with no stale copy
  left remain a precision decision made here, against the local gold.
- Verification command: dev eval with `--conflicts-gold dev/conflicts_gold_local.json`.
- Blocked by: 2.3, 3.3.

### Phase 6: Hardening and docs
Verified when: fresh clone on Python 3.11 runs the public eval cleanly with and without a key.

#### Step 6.1: Consistency and speed (Size: S)
- Acceptance criteria: determinism test (same input twice → identical text); deterministic-path
  p95 ≤ 2 s.
- Verification command: `uv run pytest -q tests/test_answers.py` and the `speed` block of the report.
- Blocked by: 4.3, 5.

#### Step 6.2: Fresh-clone check (Size: S)
- Acceptance criteria: clean clone into a temp dir + copied `snapshots_zip/` +
  `uv venv --python 3.11` + `uv pip install -r requirements.txt` (root, as graders do), then the
  literal grader command with plain `python` from the activated venv:
  `python harness/run_eval.py --submission submission --eval eval/public_eval.jsonl`.
  Runs with no errors, repeated with OPENAI_API_KEY unset.
- Ingest time and the slowest single answer are recorded: ingest well under 30 min, every answer
  under 60 s (worst case = deterministic path + one 6 s LLM call).
- The GitHub repo is public (organizers get read access) and the clone was made from the GitHub
  URL, not the local folder.
- Blocked by: 6.1.

#### Step 6.3: NOTES.md and README (Size: S)
- Acceptance criteria: `submission/NOTES.md` is short (a few paragraphs, as the PDF asks) and
  covers how the system works, how it decides what's current (the currency rules), and which API
  keys it needs.
- NOTES.md says plainly that it uses a paid API: OpenAI (`gpt-6-luna` by default), key via
  OPENAI_API_KEY, used only to word long-tail answers, and that the system runs without the key.
- README is setup only: where to place the snapshot zips (they are not in the repo), how to
  install, the grader command, and a pointer to `submission/NOTES.md`.
- Blocked by: 6.2.

### Phase 7: Submit (Size: XS)
- Acceptance criteria: every row of the PDF requirements table above is met; the graded commit is
  tagged; repo URL + commit SHA emailed to assignments@interface.ai.
- Blocked by: 6.3.

## Decision log

| Decision | Chosen option | Why |
| --- | --- | --- |
| Core approach | Temporal fact ledger + currency rules; retrieval fallback | 38 table pages answer most rate questions deterministically; determinism drives consistency |
| LLM at answer time | Hybrid: an LLM composes long-tail answers only; full function with no key | User decision 2026-11-16. Speed cost is small: p95 3 s → speed 0.944 → about −0.007 final at qa 0.8 |
| LLM provider | OpenAI Responses API via the `openai` SDK | User decision 2026-11-17 |
| LLM guard | Every number must appear in retrieved excerpts | Six public trap values exist in no snapshot |
| LLM at ingest | No | Reproducible ingest; graders may have no key |
| Model | `gpt-6-luna`, reasoning effort `none`; overridable by `KB_LLM_MODEL` / `KB_LLM_EFFORT`; step up to `gpt-6.1-terra` only if dev eval shows Luna misses long-tail items | OpenAI's most efficient current model ($0.10 in / $0.50 out per 1M tokens, official pricing page 2026-11-17), built for high-volume latency-sensitive work; the task is short answers from given excerpts, not hard reasoning |
| Dependencies | stdlib + `openai`; in-house BM25 | Clean Python 3.11 install; nothing heavy |
| Dependency files | Requirements files only: `submission/requirements.txt` (runtime, exact pins), root `requirements.txt` (`-r submission/requirements.txt`), `requirements-dev.txt`; no `pyproject.toml` or `uv.lock` | User decision 2026-11-17. Graders install `requirements.txt` into clean Python 3.11; the root file works whether they install from the repo root or the graded folder. uv is used through `uv venv` + `uv pip` |
| Graded folder | `submission/` | Rules forbid `starter/` |
| `as_of` before 2026-05-12 | Refuse, no digits | No data before the first snapshot |
| Ground truth | `must_include` / `must_not_include` over `expected_answer` prose | Prose disagrees with data (dup-011) |
| Scope | Exactly the assignment PDF; demo and video dropped | User decision 2026-11-17 (reverses the 2026-11-16 demo decision) |
| Build environment | Claude Code locally | User decision 2026-11-16; network, git history, Python 3.11 testing |
| Branch hours source | Newsroom branch-opening releases only | Phase 0 traces: `/contact` shows only crawl-time Open/Closed status and no locations pages exist (`dev/TRACES.md` §14) |
| `/rates` vs product owner page | Same tier; later effective date wins | They agree in every snapshot except one APR row in 03, where `/rates` (eff 06/08/2026) is newer than the owner page (06/04/2026) |
| Mortgage headline | Purchase by default: the $100k tier plus the range up to the top tier, and the 15-year rate | 05: 30-yr 7.13% ($100k) to 7.25% (up to $832,750), 15-yr 6.75% / 6.88% APR; 6.037% is a stale landing page, 6.7% is in no snapshot |
| Rule 4 (releases) | Releases answer counts, recognitions, hours, closures and program facts, newest publish date first; never rates | Branch count, Forbes, hours, Hy-Vee closure, Home$tart and VTO exist only in releases (Phase 0 traces) |
| Lint config | `ruff.toml` (py311, line length 100, rules E, F, I, B, UP) | No `pyproject.toml` allowed; a repo config stops the user's global ruff config from applying |
| Local conflicts gold | `dev/conflicts_gold_local.json` is frozen; it changes only with new `dev/TRACES.md` evidence, and each change is logged here | Keeps the conflicts pillar a fixed target instead of being tuned to the system |
| Gold change 2026-11-17 | Added lc-22 (2021-23 MY 72 mo 5.79% vs 5.74%), lc-23 (2021-23 MY 84 mo 6.04% vs 5.99%), lc-24 (2017-20 MY 72 mo 6.49% vs 6.44%); 21 → 24 entries | Re-derived with `dev/trace.py` on snapshot 05: owner page, alias and `/rates` (eff 08/31/2026) vs `/calculators/vehicle-affordability` and `/switch-and-earn` (eff 1/1/2026); `dev/TRACES.md` §1 |
| Gold change 2026-11-17 (2) | Added lc-25 (purchase 20-yr 7.26% vs 6.005%), lc-26/27/28 (refinance 30-yr $300k/$200k/$100k 7.33/7.35/7.28% vs 6.072/5.966/5.896%), lc-29 (refinance 20-yr 7.28% vs 6.021%), lc-30 (refinance 15-yr 6.88% vs 5.623%); 24 → 30 entries | Re-derived with `dev/trace.py` on snapshot 05: owner `/personal/loans/home-loans` (eff 09/25/2026) vs `/homebuying-guidance` and `/mortgage-refi` (eff 04/22/2026); `dev/TRACES.md` §2 |
| Conflict shape | One conflict per fact, with every page showing a competing value as its sources | `harness/scoring.py` `score_conflicts` matches each gold entry to at most one submitted conflict and counts every submission in precision, so one entry per fact is the most precise shape |
| Conflict scope | `conflicts()` checks for contradictions within every snapshot, not only the latest | lc-13 (Platinum Visa 12.50%–19.50% vs fine print 13.00%–20.00%) exists only in 01–03; a member could have read both that day |
| Pure changes between snapshots | Not reported by default; decided in Phase 5 against the local gold | No stale copy remains, so the site never contradicted itself on any one day. The kit's selftest gold (`harness/selftest/conflicts_gold.json`: 2.95% vs 3.50%) counts a stale promo copy still visible next to the new rate, which is evidence for the within-snapshot case only |
| Expired promotions (rule 4) | An offer is expired only when no product page or rate sheet names it (promotional variants must be named as such: "rate relief", "intro", "N-month … special"). A landing page linked from a product page by the product's name is that product's owner page when no product page carries its rates | Achieve Money Market in 05 exists only on `/earn-more`, linked as "[Achieve]" from `/personal/savings-account`; the 5.125% rate-relief row survives only on `/homebuying-guidance` and is named nowhere else |
| Long-tail refusal policy | Refuse when the top BM25 chunk scores below 3.0, or when the question uses a word the snapshot never uses and the chosen evidence covers under half of the question's idf mass (unseen words counted at the highest idf) | Calibrated on dev: the SWIFT-code probe has an unseen word and coverage 0.36; the answerable long-tail items have top scores ≥ 7.1 and the wordiest (no unseen word) covers 0.40, so coverage alone could not separate them |
| Extractive composer | Best sentence (scored with its chunk heading; quoted remarks slightly lower; ties to the earliest position on the page) plus the next sentence, plus one sentence from another chunk if it adds a fifth of the question's weight | Covers definitions that span two sentences (Home$tart) and lists split across chunks (mobile wallets) |
| Year-stamped statistics (rule 5) | A release figure belongs to the year it states, or to the nearest preceding "In YYYY" lead-in; a named year gets that year's figure only; a relative year ("last year", against as_of or the snapshot date) the site does not report gets "the site doesn't give a YYYY figure" plus the two latest reported years, each labelled; "most recent" gets the newest year; questions with no year (current-state counts such as the branch count) keep newest-publish-first | Resolves dup-088: no 2025 VTO figure exists, so the answer gives 2024: 256 and 2023: 294. Within one year an exact figure beats an approximate one ("7,260" over "over 7,200") |
| Synonyms | CD → certificate, car loan → auto loan, home loan → mortgage, ATM/check card → debit card (+ "MoneyCard"), applied to every question before routing and before the unknown-word refusal check | Member wording the site never uses is not an unknown topic |
| Fresh eval | `dev/fresh_eval.jsonl`: 20 items written and frozen (hash in `tests/test_repo_invariants.py`) on 2026-11-18 before the changes it measures; failures seen there are reported, not patched one by one | The dev held-out split scored 1.00 against 0.55 on the fresh set: held-out ho-20 (overdraft) was in the Phase 4 refusal calibration table, so dev no longer measures generalisation |
| Dev eval correction 2026-11-18 | dup-088-p reworded from "…in the most recent year reported?" to "…in the past year?" | Under the year-stamped rule the old wording asks for 2024 only (256), so it was no longer a paraphrase of "last year" (2025 unreported → 2024 and 2023); its copied expectation (294) did not fit its wording |
| Pure changes between snapshots (Phase 5 decision) | Not reported | Local gold (30), cap 40: without them P 1.00, R 0.90, F1 0.947, resolution 0.90 (pillar 0.933); with them P 0.725, R 0.967, F1 0.829, resolution 0.967 (pillar 0.870); uncapped with them F1 0.773. They recover lc-14 and lc-17 but add 13 unmatched entries |
| Dated-claim conflicts | Releases restating a branch-location count, or an "Nth time" recognition, with different numbers; the newest release resolves it | Other boilerplate counts (members, employees, assets, counties) drift with time and are not member-facing contradictions; including every repeated number phrase gave 14 unmatched entries. Criterion chosen with lc-20/lc-21 in view, so it may fit the local gold |
| Conflict ranking and cap | Confidence: stale copy 2.0 (pure change 0.5) + 1.0 if in the newest snapshot + 0.5 if the losing page is a landing page or below; dated claims 2.5; capped at 40 | 27 conflicts emitted today, under the cap |
| Model composer (Phase 7 gate) | Opt-in only: runs when `KB_USE_LLM=1` and `OPENAI_API_KEY` are both set; a key alone does not enable it. Documented as optional and unevaluated in NOTES.md | OPENAI_API_KEY was not set on 2026-11-18, so the gate (higher held-out and fresh accuracy, 0 trap hits, consistency 1.0, p95 ≤ 2 s) could not be run; the measured default is the extractive path (public 0.9333, dev 0.951, fresh 0.75 without a key) |
| Membership eligibility | A site fact from the "You're Eligible to Join" section of `/about/join` ("You …" criteria; one sentence in 01–03, bullets in 04–05) plus its "find us in Iowa, Illinois and Wisconsin" line, answered like the routing number; hours answers also cite `/contact` after the release. Two dev paraphrases added to group dup-081 (fresh set untouched) | `dev/trace.py` on `/about/join`, all snapshots. Fresh accuracy 0.75 before and after; public 0.9333 → 0.969; dev 0.951 → 0.9722 |
| Model composer (Phase 4 decision) | Not evaluated: OPENAI_API_KEY was not set on 2026-11-18, so the six with/without-key runs were skipped; the composer stays off without a key | Keep it only if a with-key run raises held-out and fresh accuracy with 0 trap hits, consistency 1.0 and p95 ≤ 2 s |
| `as_of` semantics | Answer from the latest snapshot with taken_on ≤ as_of. A value that only a later snapshot shows as effective on or before as_of is mentioned in `conflict_note`, never in `text`; NOTES.md explains this | The site as it stood that day is what the member saw; later crawls can reveal backdated effective dates, which are worth noting but not answering with |

## Not yet specified

- Phase 4: whether to keep the LLM composer: needs a dev run with OPENAI_API_KEY set (none
  available yet); the no-key path is measured.
- Phase 5: whether the hidden gold counts pure cross-snapshot changes (no stale copy left) as
  conflicts is unknowable; they are left out on local evidence (decision log).

## Assumptions (correct before execution starts)

1. Public GitHub repo under nishanth3112 (the email requires public).
2. Kit files `harness/`, `eval/`, `starter/`, `snapshots/README.md` are committed unchanged; zips,
   PDF and unpacked snapshots are not.
3. Dev eval items (questions + short expected values, same shape as the public eval) are fine to
   commit; page text and fact caches are not.
4. Graders may or may not set OPENAI_API_KEY; both paths must score.
5. No deadline; quality over speed.

## Always / Never

- Always: answer only from snapshots; deterministic text; run tests + public eval + dev eval after
  each step and log the result; Python 3.11 compatible; uv for all environment work.
- Never: hard-code answers, IDs or question text; commit snapshot data, zips, the PDF, page dumps or
  fact caches; edit `harness/` or `eval/`; put competing values in `text`; digits in refusals;
  live web calls; `pyproject.toml`, `uv.lock`, `uv init`, `uv add` or `uv sync`; embeddings or
  vector DBs unless dev eval shows BM25 retrieval misses (revisit then); demo, UI or video work.

## Progress

| Phase | Status |
| --- | --- |
| 0 Setup and ground truth | done 2026-11-17 (invariants 3/3; 22 topics traced; starter dev eval final 0.0776) |
| 1 Auto loans vertical slice | done 2026-11-17 (public 0.1783, dev 0.2304; dup-016/017 and auto as_of pass; 5.39% conflict emitted) |
| 2 Every rate table | done 2026-11-17 (public 0.5736, dev 0.6678; 0 trap hits; tier_disambiguation 1.00; rate paraphrase groups all agree; conflicts 16/24 matched) |
| 3 Entities and branches | done 2026-11-17 (public 0.8713, dev 0.878; 0 trap hits; branch_info 0.97; Mullan refuses; dup-088 open, see Not yet specified) |
| 4 Long tail and honesty | done 2026-11-18 except the with-key dev run (no key here): public 0.9101, dev 0.9193 without a key; should_refuse 1.00; paraphrase consistency 1.0 |
| 5 Conflicts curation | done 2026-11-18: local conflicts F1 0.947, resolution 0.90 (27 submitted, 27 matched of 30); dev final 0.951 |
| 6 Hardening and docs | done 2026-11-18: determinism test; p95 0.0 s, slowest answer 0.01 s; fresh public clone from GitHub on Python 3.11 runs the grader command with no errors (0.9333, ingest 4.0 s) without a key; NOTES.md and README written. With-key run not possible (no key) |
| 7 Submit | prep done 2026-11-18: the annotated tag `submission` marks the graded commit; email not sent (the owner sends it) |
