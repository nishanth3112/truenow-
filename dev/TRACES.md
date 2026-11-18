# Topic traces and currency rules

Produced in Step 0.2 with `uv run python dev/trace.py <regex> [-g] [--url ..] [--snap ..]`.
Evidence is cited as URL path (on `www.dupaco.com`) + snapshot(s) + value + effective date.
Snapshots: 01 = 2026-05-12, 02 = 05-19, 03 = 06-09, 04 = 08-27, 05 = 09-28.

## Currency rules (as confirmed by the traces)

1. **Snapshot by date.** `as_of` → latest snapshot with taken_on ≤ as_of; before 2026-05-12 →
   refuse. Within a snapshot, a page's copy may be old (`/switch-and-earn` in 04 and 05 has
   fetched_at 2026-06-09), so the date of a fact comes from its effective date, not the snapshot date.
2. **Authority.** Tier A: the product owner page and the rate sheets (`/rates`, `/business-rates`).
   Tier B: other product pages that carry a copy of the table (`/personal/checking-accounts` in
   01–04 carries old auto, mortgage, HELOC, card and personal-loan tables; `/personal/loans/home-equity`
   carries a refinance table; `/personal/savings/holiday-club-account/` in 05 carries the whole savings sheet).
   Tier C: PDFs. Tier D: landing pages and calculators (`/switch-and-earn`, `/calculators/*`,
   `/homebuying-guidance`, `/mortgage-refi`, `/*-lp`). Tier E: blog, `/learn/*` articles, newsroom.
   Exception: `/learn/master-your-money/homeownership/` in 05 carries the current mortgage table
   (eff 09/25/2026), identical to the owner page; tier E only loses on a disagreement.
3. **Same tier → later effective date wins**, then later fetched_at. The effective date belongs to
   the table: it is the first "Rates (are) effective (as of) D" line *after* the table (footnotes
   follow tables). Dates appear as `M/D/YYYY`, `MM/DD/YYYY` and `MM/DD/YY` (`08/13/25` on
   `/personal/savings-account` in 04).
4. **Dated releases and expired promotions never give a current value.** Press-release boilerplate
   changes over time (branch count 24 → 23 → 22); the newest *publish date* wins for counts and
   recognitions, and only for those (no rates from releases). Promotions that disappear from the
   rate sheet are gone (25-month special after 02; HELOC 1.99% intro after 03; Mortgage Rate Relief
   5.125% after 03; business checking "up to 3.00% APY" after 02).
5. **Qualifiers are part of the key.** Product (incl. personal vs business), term, model-year range,
   balance tier, loan amount, purchase/refinance, rate vs APR vs APY vs dividend rate, standard vs
   intro vs jumbo vs special. The same number in two products is not a conflict (0.35% = Investor's
   Choice MM $25k–$99,999.99 and HSA $25k+).
6. **Missing qualifier.** Lead tier + range within the same product, then ask which one. Never
   values from another product.

Observed conflict patterns, all resolved by rules 2–3 with no special case:
- Owner page and `/rates` agree in every snapshot except one: 03 purchase 30-yr $100k APR,
  `/rates` 6.256% (eff 06/08/2026) vs `/personal/loans/home-loans` 6.262% (eff 06/04/2026) → rule 3
  picks `/rates`. So `/rates` and owner pages are the same tier.
- `/rates` contradicts itself in 01–04: it holds the home-loans refinance table and a copy of the
  home-equity refinance table (different values, older effective date; the copy spells amounts
  without commas, `$832750`). Rule 3 picks the home-loans copy.
- `/personal/credit-cards` in 01–03 contradicts itself: bullets 12.50%–19.50% APR; fine print
  "effective 10/1/2025 … 13.00% APR to 20.00% APR". `/rates` (eff 1/1/2026) says 12.50%–19.50%.
- `/business-rates` + `/business/savings-accounts` in 01–04: Share Savings $10,000–$24,999.99
  dividend 0.20% but APY 0.15% (a dividend rate above its APY is impossible: a typo). Fixed in 05
  (0.15% / 0.15%).

## Parser findings that matter for Phase 1

- Table cells contain non-breaking spaces (`84\xa0Months`; 155 pages in 05). Normalize NBSP first.
- Footnote digits are glued to values: `5.39% APR1`, `0.15%1`, `10.49%1`. Strip them.
- Some tables have no product column; the product is the nearest short line above the table,
  which may be a bare tab label (`Investor's Choice`), not a heading.
- Labels drift: `2023-26 Model Year` (01–04) → `2024-27 Model Year` (05); `2021-22` → `2021-23`;
  en dash vs hyphen; `$832,750` vs `$832750`; `$0 - $99.99` vs `$0.00 - $99.99`. Parse ranges.
- `/contact` is a locator widget: 6 nearest branches with address and crawl-time "Open/Closed"
  status; no schedules.

## Topic traces

### 1. Auto loan 60 / 84 months (dup-016, dup-017)
- 05 owner `/personal/loans/auto-motorcycle-loans` + `/rates` + new alias `/personal/loans/auto-loans/`:
  2024-27 MY 60 mo **5.39%**, 84 mo **5.59%** (eff 08/31/2026). 2021-23 MY 60 mo 5.64%, 84 mo 6.04%.
- 01–04 owner + `/rates`: 2023-26 MY 60 mo 5.19%, 84 mo 5.39% (eff 5/1/2026).
- Stale, all snapshots: `/switch-and-earn`, `/calculators/vehicle-affordability` 2023–26 MY 60 mo
  **5.34%**, 84 mo **5.54%** (eff 1/1/2026); also `/personal/checking-accounts` 01–04.
- 05 older tiers also moved: 2017-20 MY 60 mo 6.14% → 6.34%; 2016 MY 48 mo 8.39% → 8.59%.
- More stale pairs in 05 (owner + alias + `/rates`, eff 08/31/2026, vs `/calculators/vehicle-affordability`
  and `/switch-and-earn`, eff 1/1/2026): 2021-23 MY 72 mo **5.79%** vs 2021-22 MY 5.74%; 2021-23 MY
  84 mo **6.04%** vs 2021-22 MY 5.99%; 2017-20 MY 72 mo **6.49%** vs 6.44%.
  (`dev/trace.py '2021-2[23] Model Year \| (72|84) Months' -g --snap 05`,
  `dev/trace.py '2017-20 Model Year \| 72 Months' -g --snap 05`)

### 2. Mortgage 30 / 15 year by amount (dup-009, dup-011)
- 05 owner `/personal/loans/home-loans` (eff 09/25/2026), Rate / APR: purchase 30-yr $100k
  **7.13% / 7.27%**; $200k, $300k, $832,750 **7.25%** / 7.34%, 7.32%, 7.29%; 20-yr 7.13% / 7.26%;
  15-yr **6.75% / 6.88%**. Refinance same rates, APRs 7.28–7.35%, 15-yr 6.88%.
- History of purchase 30-yr $100k rate / 15-yr rate: 01 5.875% / 5.625% (eff 05/11); 02 6.250% /
  6.000% (05/19); 03 6.125% / 5.875% (06/04); 04 6.375% / 6.000% (08/26); 05 7.13% / 6.75% (09/25).
- Stale, all snapshots: `/homebuying-guidance` (eff 04/22/2026) purchase 30-yr $832,750 6.000% /
  **6.037%**, $300k 6.000% / **6.061%**, $200k 5.875% / **5.954%**; `/mortgage-refi` the refinance twin.
- Full stale set in 05, APR (owner `/personal/loans/home-loans` eff 09/25/2026 vs stale page eff
  04/22/2026): purchase 30-yr $100k 7.27% vs 5.884%; purchase 20-yr **7.26% vs 6.005%**;
  purchase 15-yr 6.88% vs 5.623% (`/homebuying-guidance`); refinance 30-yr $832,750 7.30% vs 6.049%,
  $300k **7.33% vs 6.072%**, $200k **7.35% vs 5.966%**, $100k **7.28% vs 5.896%**; refinance 20-yr
  **7.28% vs 6.021%**; refinance 15-yr **6.88% vs 5.623%** (`/mortgage-refi`).
  (`dev/trace.py '(Purchase|Refinance): (15|20|30)-Year Fixed Conventional' -g --snap 05`)
- `6.7%`: in no snapshot (only 6.74% home-equity loan 5 years). dup-011 prose "15-year 6.25%" is not
  in any mortgage table; 6.25% is the HELOC rate.

### 3. Share Savings tiers (dup-045, dup-046, dup-049)
- All snapshots, `/personal/savings-account` + `/rates`: $25,000+ **0.20%**; $10,000–$24,999.99
  **0.15%**; $2,500–$9,999.99 0.10%; $100–$2,499.99 0.10%; $0–$99.99 0.00% (dividend = APY).
  Eff 01/06/2026 (01–04), 06/15/2026 (05).
- A "0.00%–0.35%" or "up to 0.35%" Share Savings range appears in no snapshot.

### 4. Money market (Investor's Choice)
- All snapshots: $100,000+ 0.40%; $25,000–$99,999.99 **0.35%**; $10,000–$24,999.99 0.30%;
  $2,500–$9,999.99 0.25%; $0.01–$2,499.99 0.20%; min to open $2,500. Unchanged.

### 5. Health Savings Account
- All snapshots: $25,000+ **0.35%**; $10,000–$24,999.99 0.30%; $2,500–$9,999.99 0.25%;
  $0.01–$2,499.99 0.20%. Unchanged. In 01–04 the table has no product column (heading only).

### 5b. Achieve Money Market
- 05: only on `/earn-more` (landing page, no effective date): introductory 4.00% dividend rate /
  3.66% APY for the first 6 months, then 3.20% / 3.25% APY; $25,000 to open; tiers from $25,000.
  `/personal/savings-account` names it in a link "[Achieve](…/earn-more)", so `/earn-more` is its
  owner page. `/membermoneymarket-lp` still shows the pre-intro table (eff 10/01/2025).
  01–04: on `/makethemost-lp`; 04 also on `/personal/savings-account` and `/rates`.
  (`dev/trace.py 'Achieve' -g --snap 05`, `dev/trace.py 'earn-more' -g --snap 05`)
- 05 IRA specials: Roth 10-month jumbo 4.00% APY but Traditional 10-month jumbo 3.90% APY on both
  `/personal/retirement` and `/rates` (different products; not a conflict under rule 5).

### 6. Bright Savings (dup-050)
- All snapshots: $0.01–$1,000,000, dividend 2.23%, **APY 2.25%**; 05 eff 06/02/2026. Also on
  `/savings-account/online-savings-account` (01–05) and `/savings/bright-savings` (01–02).
- "Jump Start" appears in no snapshot.

### 7. Checking (dup-052)
- 1st Rate Checking $5,000–$24,999.99: **3.00% APY** (2.96% div) in 01–02 (eff 07/01/2025);
  **2.50% APY** (2.47%) from 03 (eff 06/02/2026). $25k+ 0.10%; under $5,000 0.00%. Free Checking 0.00%.
  05 sources: `/personal/checking-accounts`, `/checking`, `/rates`.
- Business 1st Rate Checking same tiers (05 `/business/checking-accounts`).
- "3% APY" therefore *does* appear: stale personal tier (01–02) and business checking promo
  "up to 3.00% APY" on `/business/checking-accounts`, `/business-rates` (01–02).

### 8. Certificates: regular, specials, jumbo (dup-001, dup-005, dup-006)
- Regular APY, all snapshots: 6 mo 3.40%; 12 mo **2.90% (01–02) → 3.40% (03+)**; 18 mo 2.70%;
  24 mo 2.50%; 30 mo 2.30%; 36 mo 2.10%; 48 mo 1.90%; 60 mo 1.80%; $1,000 min.
- 10-month special: regular 3.80% / jumbo **3.90%** (01–04) → 3.90% / **4.00%** (05, eff 09/01/2026
  personal, 09/24/2026 business).
- 17-month special: absent in 01–02; 3.85% / 3.95% jumbo (03); 3.95% / 4.05% (04, eff 07/14/2026);
  **4.10% / 4.20%** (05). Jumbo = $100,000 min, regular special = $1,000 min.
- 25-month special: 3.60% / 3.70% jumbo in 01–02 only (expired promo afterwards).
- Same specials in IRA form on `/rates` ("Roth:", "Traditional:" rows).

### 9. Personal loan 36 months (dup-028)
- All snapshots, `/personal/loans/personal-loans` + `/rates`: 24 mo 9.99%, 36 mo **10.49%**,
  48 mo 10.99%, 60 mo 12.49%. Owner eff 10/22/2024 (01–04), 05/01/2026 (05); unchanged value.

### 10. Credit cards (dup-034, dup-035, dup-040)
- Platinum Visa **12.50%–19.50% APR**; intro balance transfer 2.90% APR for 6 months (balances
  posted in the first 90 days); Rewards Visa **15.50%–21.00% APR** (`/rates`, `/personal/credit-cards`).
- Business Platinum Visa variable **15.50%**; Business Rewards Visa variable **20.5%**
  (`/business/credit-cards`, all snapshots).
- Stale fine print 13.00%–20.00% (eff 10/1/2025) on `/personal/credit-cards` 01–03.
- `9.9%`: in no snapshot.

### 11. Routing number (dup-054, dup-055)
- **273974581** on `/contact`, `/business/cash-management`, blog posts, all snapshots.
  271176899: in no snapshot.

### 12. Branch count (dup-073)
- Newsroom boilerplate by publish date (05): 2026-04-03 → 2026-05-05 releases say **22 branch
  office locations**; 2026-01-08 → 2026-03-17 say 23; older releases say 24 (e.g.
  `/newsroom/forbes-ranks-dupaco-as-a-top-credit-union-in-america-3`, 2024) or 20.
  `/about` mentions "18 branches" in an executive bio (not a count claim).

### 13. Forbes (dup-087)
- `/newsroom/forbes-ranks-dupaco-as-a-top-credit-union-in-america-3` (2024-06-18): "**fifth** time".
  `…-america-2` (2023-07-18): "fourth time". `…-america` (2020-06-26): "third year in a row".

### 14. Lobby and drive-up hours (dup-064, dup-065, dup-066, dup-104)
- Not on `/contact` (live Open/Closed status only) and no locations pages exist. The only
  schedules are in newsroom branch-opening releases:
  - `/newsroom/dupaco-celebrates-completion-of-newest-learning-lab`: lobby Mon–Thu 8:30 a.m.–5 p.m.,
    Fri 8:30 a.m.–6 p.m., Sat 8:30 a.m.–12:30 p.m.; also a Sat 9 a.m.–noon line.
  - `/newsroom/dupaco-community-credit-union-celebrates-completion-of-expanded-branch`: lobby
    Mon–Thu 8:30 a.m.–5 p.m., Fri 8:30 a.m.–5:30 p.m.; drive-up Mon–Fri **8 a.m.–6 p.m.**
  - `…-newest-learning-lab`, `-2`, `-3`: Mon–Fri 8:30 a.m.–5:30 p.m., Sat 8:30 a.m.–12:30 p.m.
  - `…-east-washington-avenue-branch-ribbon-cutting`: drive-up Mon–Fri 9 a.m.–5 p.m.
- `/locations/branch-hours`: in no snapshot. `/contact` is the locator URL (dup-080).

### 15. Hy-Vee branch (dup-074, dup-075, dup-076)
- `/newsroom/dupaco-evolves-with-purpose-and-member-needs-plans-hy-vee-branch-closure` (all
  snapshots): closes **March 31, 2026**; members can use full-service branches at **Key West and
  Sycamore Street**.

### 16. Join URL (dup-082)
- **https://join.dupaco.com/** on `/about/join`, `/personal`, all snapshots.
  `info.dupaco.com/how_to_join`: in no snapshot.

### 17. Certificate rates URL (dup-008)
- Calculators link "Compare rates" to **https://www.dupaco.com/personal/savings-account#rates** (05).
  `info.dupaco.com/certificate_account_rates`: in no snapshot.

### 18. Home$tart (dup-031)
- `/newsroom/first-time-homebuyers-get-a-boost-dupaco-offers-fhlb-hometart-grants` (all
  snapshots): FHLB Des Moines program, **up to $15,000** for first-time homebuyers.

### 19. Volunteer Time Off (dup-088)
- `/newsroom/volunteering-pays-off-dupaco-credit-union-employees-reap-the-benefits-of-giving-back`
  (2024 release): **294** employees used VTO in 2023.
- `/newsroom/volunteering-pays-off-dupaco-credit-union-employees-reap-the-benefits-of-giving-back-2`
  (published 2025-04-21): **256** employees used VTO in 2024. Both releases are in all five
  snapshots (`dev/trace.py '\d+ Dupaco employees\*?\*? used' -g`). Rule 4 (newest publish date
  first) answers 256; the public eval item dup-088 expects 294, so it contradicts rule 4.

### 20. HELOC and home equity
- HELOC standard **6.25% APR** all snapshots; 1.99% intro APR for 3 months in 01–03 only.
  Home equity loan 5 yr 6.74%, 10 yr 7.24%; home improvement $10k–$20k 120 mo 8.50%.

### 21. Membership and contact (dup-060, dup-081, dup-094)
- `/about/join`: live or work in the charter area; locations in **Iowa, Illinois and Wisconsin**.
- Phone **800-373-7600** site-wide. Mobile wallets: Apple Pay, Google Pay, Samsung Pay
  (`/learn/blog/mobile-wallets-a-simple-guide-to-faster-safer-payments`).
- Galena branch: 11375 Oldenburg Ln., Galena, IL 61036 (`/contact`).

### 22. Refusal topics (dup-102, dup-145, dup-147)
- Mullan Avenue: named only in `/learn/blog/crew-amanda-clark` and a 2026 PDF (04–05) and a list of
  branch streets in a blog post; no hours or address → refuse.
- No ARM rate and no construction-loan rate anywhere (`(7/1|5/1|adjustable)…%`, `construction…%`: 0 hits).

## Public trap values

| Trap | Where it lives |
| --- | --- |
| 271176899 | nowhere |
| 9.9% | nowhere |
| info.dupaco.com/certificate_account_rates | nowhere |
| info.dupaco.com/how_to_join | nowhere |
| /locations/branch-hours | nowhere |
| 6.7% (dup-011) | nowhere |
| "up to 0.35" / Jump Start | nowhere |
| 3% APY (dup-052) | **exists**: 1st Rate Checking 3.00% APY in 01–02; business checking promo 01–02 |
| 6.037% / 6.061% / 5.954% | `/homebuying-guidance`, all snapshots, eff 04/22/2026 |
| 5.34% / 5.54% | `/switch-and-earn`, `/calculators/vehicle-affordability` (all), `/personal/checking-accounts` (01–04) |
| 0.30% / 0.40% / 0.35% | Money market and HSA tiers (other products) |
| 4.00% (dup-006 as_of) | 10-month jumbo special in 05 |
| 24 branch / fourth / 2020 / 2021 | older newsroom releases |
| ZIP code, member number, CO-OP Shared Branch, coffee table | real page text, but behaviour traps, not values |
