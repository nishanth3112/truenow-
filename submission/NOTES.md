# NOTES

## How it works

`ingest` keeps every snapshot (a temporal ledger), not just the latest copy of each page. For each
snapshot it parses every markdown table into dated facts: product, qualifiers (term, model-year
range, balance or loan-amount tier, purchase/refinance, jumbo, business, intro), metric (rate,
APR, APY, dividend rate), value, page, page authority and the table's effective date. It also
extracts identifiers and links (routing number, phone, join and locator URLs, branch addresses)
from site pages, and branch hours, closures, counts and recognitions from newsroom release bodies.
Finally it builds an in-house BM25 index over heading-sized chunks of each snapshot. Loading all
five snapshots takes about 4 seconds.

`answer` picks the snapshot (the `as_of` date, else a date in the question, else the newest), then
routes the question. Rate questions get the resolved value for the requested tier; if a qualifier
is missing, the lead tier plus the range, and a question naming what is missing; if the site lists
no such rate, a refusal. Branch, identifier and dated-claim questions use the extracted claims.
Everything else gets the best retrieved sentences with their page, or "It isn't listed; please
contact us." when the site never mentions the topic. Answers are deterministic and take
milliseconds. Competing older values go in `conflict_note`, never in the answer text.

`conflicts()` lists one conflict per fact across every snapshot, with every page that showed a
competing value as a source, plus releases that restate a branch count or an award count with
different numbers. Each has the winning value and the reason.

## How it decides what is current

1. **Date.** Answer from the latest snapshot taken on or before `as_of`; before the first snapshot
   (2026-05-12), refuse. A later snapshot that shows a value effective on or before `as_of` is
   mentioned only in `conflict_note`.
2. **Authority.** Product pages and the rate sheets (`/rates`, `/business-rates`) beat other
   product pages that copy a table, which beat PDFs, which beat landing pages and calculators,
   which beat blog and newsroom pages.
3. **Same authority: the later effective date wins**, then the later fetch time. A table's
   effective date is the first "Rates (are) effective (as of) …" line after it.
4. **Expired promotions never supply a current value.** An offer seen only on landing pages, PDFs
   or releases is expired unless a product page or rate sheet still names it. Releases may answer
   counts, recognitions, hours, closures and program facts (newest release first), never rates.
5. **Qualifiers are part of the fact.** The same number for two products, terms or tiers is not a
   conflict. A figure stated for a year belongs to that year: a question naming a year gets that
   year's figure, and an unreported "last year" gets the two latest reported years, labelled.
6. **Missing qualifier.** Give the lead tier and the range within the same product, then ask
   which one; never a value from another product.
7. **Cite the highest-authority page that shows the winning value.**

## API keys

**No key is needed.** The system runs fully offline, and every score was measured that way.

There is an optional, opt-in model path that is **not evaluated**: it uses a **paid API, OpenAI**
(model `gpt-6-luna` by default) and runs only when both `KB_USE_LLM=1` and `OPENAI_API_KEY` are
set. A key alone does not turn it on. It only words long-tail answers from retrieved excerpts,
gets no tools and a 6-second timeout, and is not retried (except once, without the temperature
setting, if the model rejects it). Every number in its answer must appear in the question or the
excerpts, and must not be a value the resolver ruled stale; otherwise the extracted answer is
used. `KB_LLM_MODEL` and `KB_LLM_EFFORT` (default `none`) change the model and reasoning effort.

## Known limits

On a frozen set of 20 questions written before the system saw them, it scored 0.85, with three
misses. A fee that sits in a fee-schedule row can lose to a product page about the same service
(the incoming-wire fee came back as the wire-transfer page instead of "$10.00"). A question that
uses "hours" in another sense ("volunteer hours") without "how many" is routed to branch hours.
A question about a product the site never offers (a cryptocurrency trading account) was answered
with a loosely related sentence instead of a refusal. The optional model path has never been
run against a key, so its effect on accuracy, consistency and speed is untested.
