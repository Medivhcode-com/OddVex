# OddVex Data Provider Evaluation

- **Research date:** 2026-11-15
- **Status:** Research input only. **No provider has been purchased, trialled or contacted. No account, API key or contract exists. Any purchase, paid trial or signed terms requires Founder approval.**
- **Tags:** **[Verified · official]** / **[Verified · 3P]** = the web-search tool returned that statement from that URL this session (pages could not be opened directly; see `SOURCES.md`). **[Assumption]** = not confirmed.
- **Bias warning:** most cross-vendor comparisons online are written by vendors about their rivals (SportsGameOdds, SharpAPI, OddsPapi, TheRundown). Their claims about *competitors* are marked **3P, competitor** and should be treated as leads, not facts.
- This is not legal advice. Licence terms must be read in full and reviewed before signing.

## 1. What OddVex needs

| Data need | Used for | Freshness needed at MVP |
|---|---|---|
| Pre-game odds, main markets, major US books | Odds comparison, best price | 1–5 min is acceptable if labelled |
| Player props across books | Props analyzer | 1–5 min |
| Scores, schedules, results | Grading, context | Minutes |
| Player/team stats, game logs | Hit rates, splits | Daily (post-game) |
| Historical odds incl. closing lines | CLV, line movement, backtests | Batch |
| Injuries / lineups | Context, AI explanations | Minutes to hours |
| Sportsbook account sync | Auto bet tracking | Optional; not needed for MVP |
| Sub-second odds | Live EV/arb scanning | **Not needed for MVP** |

**[Assumption]** — these are my working requirements, not an approved spec.

## 2. Odds and props vendors

### 2.1 Summary table

| Vendor | Coverage (as stated) | Update model / latency | Public pricing (retrieved 2026-11-15) | Limits | Redistribution / display terms (public) | MVP fit | Scale fit |
|---|---|---|---|---|---|---|---|
| **The Odds API** | Many sports and bookmakers; props as "additional markets"; historical snapshots | REST polling; historical snapshots at 5-min intervals | Free 500 credits/mo; $30 (20K); $59 (100K); $119 (5M); $249 (15M) per month | Credit-metered: markets × regions per call | **Display in commercial apps explicitly allowed; resale as raw data prohibited; no attribution required** | **High** | Medium |
| **SportsGameOdds** | Props on every plan; no futures/outrights (per own comparison) | REST; 3-min updates on Rookie, sub-minute on Pro | Free (2,500 objects/mo); Rookie $149/mo ($99 annual); Pro $499/mo ($299 annual); All-Star custom | 10 / 50 / 300 req/min; per-event billing | Not found | **High** | Medium |
| **TheRundown** | 30+ leagues, 18+ books | REST; WebSocket on Ultra+ | Free (20K data points/day); Starter $49; Pro $149; Ultra $399 (a tracker shows different tiers) | Plans stop at included limits by default | Not found | Medium–High | Medium |
| **SharpAPI** | 2 books free → 5 / 15 / 25 books by tier; built-in EV, arb, middles | REST; streaming is a paid add-on | Free; Hobby $79; Pro $229; Sharp $399; streaming +$99–$149 | 12 req/min free; free data delayed 60s | Not found | Medium | Medium |
| **OddsBlaze** | ~23–24 US-centric books; dedicated SGP pricing endpoint | REST + WebSocket; "<1s" claimed | **Conflicting:** $299–$999/mo (2 sources) vs $29–$249/mo (1 competitor source) | 300 req/min; SGP 30–200/min | Not found | Medium (SGP is the draw) | Medium–High |
| **OddsPapi** | 300–370 books claimed, 69 sports | REST | Free 250 req/mo; paid from ~$49/mo (3P) | — | Not found | Low–Medium | Unknown |
| **Unabated API** | US books + proprietary vig-free line | WebSocket, "no throttling" | Free with Gambly deeplink traffic targets; Concierge $799/mo; Advantage $2,999/mo | — | Free tier is conditional on sending deeplink traffic | Low | Medium–High |
| **OpticOdds** | 100+ / 200+ books (pages differ); grading; deep links; parlay pricing; full line history | REST, SSE streaming, RabbitMQ; "sub-second" claimed | **Contact sales.** Unofficial estimates ~$5,000/mo per sport | Snapshot endpoint 10 req / 15 s | Not found; detailed docs reportedly follow contract | Low (cost) | **High** |
| **SportsDataIO** | Odds (10+ books), props, futures, closing lines + full stats, injuries, projections | REST; replay tool for testing | **Contact sales.** Free trial / last-season sandbox; unofficial "$5,000+/mo typical" | — | Commercial agreement required; some fields licensed separately | Medium (trial for prototyping) | **High** |
| **Sportradar** | 150+ / 400+ books (pages differ); US prematch feed with named books | Push/REST | **Contact sales.** Unofficial "five figures per month" | — | B2B terms; Odds Comparison excludes results | Low | High |
| **Genius Sports** | Official NFL data distributor | — | **Contact sales.** Operator rev-share model reported | — | Official-data licensing | Not applicable for MVP | Only if official data is ever required |
| **SharpSports betPrices** | Odds feed across major leagues/books | Real-time, unlimited calls | $750/mo; betPlace (adds deep links to pre-filled slips) $1,750/mo; Historic Data $3,000/mo | — | See services agreement | Low | Medium |

### 2.2 Evidence per vendor

**The Odds API**
- Plans: free Starter 500 credits/mo; 20K at $30/mo; 100K at $59/mo; 5M at $119/mo; 15M at $249/mo; paid plans include all sports, bookmakers, markets and historical odds. **[Verified · official]** https://the-odds-api.com/ . Caveat: the search tool saw inconsistent tier labels between cached snapshots; confirm on the live page.
- Credit cost = number of markets × number of regions per request. **[Verified · official]** https://the-odds-api.com/sports/nfl-odds.html
- Historical: featured markets from June 2020 (10-min snapshots, 5-min from Sept 2022); additional markets incl. player props from May 2023 at 5-min snapshots; paid plans only. **[Verified · official]** https://the-odds-api.com/historical-odds-data/ . Historical calls cost 10x standard credits. **[Verified · 3P, competitor]** https://sportsgameodds.com/compare/the-odds-api
- Terms: commercial use in sites, apps, dashboards and analytical tools is supported "provided our data is not the primary product being sold or redistributed"; storing data, showing it in a UI, displaying derived values and training statistical/ML models are listed as permitted; reselling or redistributing as an API, feed or downloadable files is prohibited; attribution not required; key can be revoked on suspected violation. **[Verified · official]** https://the-odds-api.com/terms-and-conditions.html
- Latency for live data is polling-based; exact refresh intervals not confirmed. **[Assumption]**: not suitable for arb scanning.
- No scores-grade stats, injuries or account sync. **[Assumption]**

**SportsGameOdds**
- Amateur (free): 10 req/min, 2,500 objects/mo. Rookie: $149/mo or $99/mo billed annually, 100,000 objects/mo, 50 req/min, 3-minute update frequency. Pro: $499/mo or $299/mo billed annually, unlimited objects, 300 req/min, sub-minute updates. All-Star: custom. Shared ceilings of 50,000 requests/hour and 500,000/day. **[Verified · official]** https://sportsgameodds.com/pricing
- Props on every plan from one events endpoint; billing is per event, so a game with hundreds of props counts once. **[Verified · official]** https://sportsgameodds.com/player-props-odds-api
- Historical gating is stated inconsistently on its own pages (Pro+ vs paid plans vs one week on free). **[Verified · official]** (conflict noted)
- Redistribution terms: not found.

**OpticOdds**
- Real-time aggregation, grader endpoint (Won/Lost/Refunded/Half), deep links where available, `/parlay/odds`, historical endpoint with every price change, lock and settlement event; snapshot endpoint limited to 10 requests per 15 seconds. **[Verified · official]** https://developer.opticodds.com/docs/odds-api-getting-started-guide
- Offers an MCP connector for querying odds from an AI assistant. **[Verified · official]** https://opticodds.com/sportsbook-ai
- Customers include Pikkit, Linemate, Kalshi, Dabble. **[Verified · official]** https://opticodds.com/customers
- Pricing not public; "~$5,000/month per sport" is a community estimate reported by rivals. **[Verified · 3P, competitor]** https://sportsgameodds.com/compare/opticodds ; https://odds-api.io/blog/odds-api-vs-opticodds
- Delivery "under 800ms" is vendor-reported, not benchmarked. **[Verified · 3P, competitor]** https://sportsgameodds.com/blog/optic-odds-vs-sports-game-odds

**SportsDataIO**
- Odds product covers pre-match, in-play, historical and closing lines with props and futures. **[Verified · official]** https://sportsdata.io/live-odds-api
- Stats side: NFL/NBA injuries (status, body part, note), player stats, play-by-play, projections, DFS salaries; some fields (e.g. headshots) need a separate licence and some trial fields are scrambled. **[Verified · official]** https://sportsdata.io/developers/api-documentation/nfl ; https://sportsdata.io/developers/data-dictionary/nfl
- Access: some self-serve, production via sales; free trial is league-limited / last-season. **[Verified · official]** https://sportsdata.io/developers/getting-started ; **[Verified · 3P]** https://sportsapis.dev/apis/sportsdata-io
- Publishes a "Bet Tracker Implementation Guide" and has a (2021) partnership with SharpSports for bet tracking. **[Verified · official, title]** https://sportsdata.io/developers/bet-tracker-guide ; **[Verified · 3P]** https://sbcamericas.com/2021/11/24/sportsdataio-enters-into-bet-tracking-solution-partnership-with-sharpsports/
- "$5,000+/month typical" comes from a rival. **[Verified · 3P, competitor]** https://sportsgameodds.com/compare/sportsdataio

**Sportradar**
- Enterprise contracts; estimates of five figures per month or "$10,000+" come from directories and rivals. **[Verified · 3P]** https://sportsapis.dev/apis/sportradar ; **[Verified · 3P, competitor]** https://sharpapi.io/compare/sportradar-alternative
- Trial: a marketplace sign-up reportedly allows trial keys for some products, but Live Odds trial goes through a sales rep. **[Verified · 3P]** https://oddspapi.io/blog/?p=3926
- Odds Comparison does not include results; a separate sports-data feed is needed for grading. **[Verified · 3P, competitor]** https://sportsgameodds.com/compare/sportradar

**Genius Sports**
- Exclusive distributor of official NFL data to sportsbooks; reported operator terms are a revenue share (1.5% pre-game, 5% live) rather than a flat fee. **[Verified · 3P]** https://www.legalsportsreport.com/101363/huddle-genius-sports-signs-sports-betting-data-deal/ ; https://www.legalsportsreport.com/123307/genius-extends-nfl-betting-data-deal-at-least-five-years/
- No startup or media tier found. Relevance to a non-wagering research product is unclear. **[Assumption]**

**OddsBlaze**
- Entry price conflicts: $299/mo with 300 req/min, SGP and historical included (directory); $299 → $999 → Enterprise with a 1-day trial (rival); $29–$249/mo with a delayed lowest tier (another rival). **[Verified · 3P]** https://sportsapis.dev/apis/oddsblaze ; **[Verified · 3P, competitor]** https://oddspapi.io/blog/oddsblaze-alternative/ ; https://sharpapi.io/compare/oddsblaze-alternative
- SGP endpoint with a short book list (DraftKings, ESPN, Fanatics, FanDuel, Hard Rock and others). **[Verified · 3P, docs mirror]** https://oddsblaze-docs.pages.dev/endpoints/same_game_parlay (a pages.dev host, not confirmed as the official docs domain)

**TheRundown / SharpAPI / OddsPapi / Unabated**
- TheRundown: free plan, 20,000 data points/day; Starter $49, Pro $149, Ultra $399; props, extra books, in-play and streaming need eligible paid plans; also offers an MCP server. **[Verified · official]** https://therundown.io/pricing/api ; https://therundown.io/compare/the-odds-api . A tracker lists different tiers. **[Verified · 3P]** https://pricingsaas.com/companies/therundown
- SharpAPI: tiers and limits as in the table. **[Verified · official]** https://sharpapi.io/pricing
- OddsPapi: free 250 requests/month; own pages disagree on whether historical is free. **[Verified · official]** https://oddspapi.io/blog/odds-api-pricing-2026-comparison/
- Unabated: free API returns Gambly deeplinks and stays free while traffic targets are met; Concierge $799/mo; Advantage $2,999/mo. **[Verified · official]** https://unabated.com/odds-api ; https://unabated.com/odds-api/free ; https://unabated.com/odds-api/concierge

## 3. Stats, scores, schedules, injuries

| Vendor | What it covers | Public pricing | Notes | Tag |
|---|---|---|---|---|
| **BALLDONTLIE** | NBA, NFL and other leagues: games, stats, box scores, standings; top tier adds odds and player props | Per sport: free (5 req/min), $9.99/mo (60 req/min), $39.99/mo (600 req/min); 7-day trial of top tier | Tiers do not carry across sports. Props are live-only, not stored, so no history. Commercial terms not checked. | **[Verified · official]** https://www.balldontlie.io/account/ ; **[Verified · 3P]** https://sportsapis.dev/apis/balldontlie ; https://highlightly.net/blogs/best-nba-apis-in-2026 |
| **SportsDataIO** | Stats, injuries, projections, play-by-play, schedules | Contact sales; trial | One contract could cover stats + odds | **[Verified · official]** (section 2.2) |
| **MySportsFeeds** | Stats feeds; free for personal use (no real-time) | Not published | Commercial terms unknown | **[Verified · 3P]** https://datarade.ai/data-providers/mysportsfeeds/profile |
| **Goalserve** | NFL/NBA feeds | Published per-sport price pages (figures not captured) | FAQ: raw feeds may not be resold; commercial products allowed | **[Verified · official]** https://www.goalserve.com/sport-data-feeds/nfl-api/prices |
| **Sportradar** | Full official-grade stats | Contact sales | Enterprise | **[Verified · 3P]** |
| Open-source (nflverse, nba_api, etc.) | Historical stats | Free | **No formal commercial licence; league site terms may prohibit commercial scraping.** Not verified this session. | **[Assumption]** |
| Injuries specifically | SportsDataIO has dedicated endpoints. Outlier, Stat Sniper and others surface injuries, vendor unknown. | — | A dedicated news/injury feed (e.g. a fantasy-news provider) was **not researched**. | **[Verified · official]** for SportsDataIO; rest **[Assumption]** |

## 4. Sportsbook-account sync vendors

| Vendor | What it offers | Public pricing | Evidence | Tag |
|---|---|---|---|---|
| **SharpSports (betSync)** | Plaid-style account linking via a hosted "BookLink" UI; returns balances and bet history; async refresh with webhooks; sandbox; per-book on/off; some books limit how far back bets sync | **betSync "starting at $500/mo"**; the services agreement says fees are metered by linked accounts and/or refreshes | Used by OddsJam's tracker; BettingPros announced tracking with SharpSports; SportsDataIO partnership (2021) | **[Verified · official]** https://app.sharpsports.io/ ; https://app.sharpsports.io/services-agreement ; https://docs.sharpsports.io/docs/overview ; https://docs.sharpsports.io/docs/linking-accounts ; https://docs.sharpsports.io/reference/book ; https://oddsjam.com/betting-education/how-to-sync-sportsbooks-with-oddsjam-bet-tracker |
| **OpticOdds** | A case study says Pikkit integrated its "odds and bet-tracking API". Public docs found this session show grading, not account linking. Whether OpticOdds sells account sync is **unconfirmed**. | Contact sales | — | **[Verified · official]** https://opticodds.com/customers/pikkit ; gap is **[Assumption]** |
| **In-house sync** | Action Network (BetSync), Pikkit (BookSync), Juice Reel (300+ books claimed) present sync under their own names; whether these are built in-house or white-labelled is unknown | n/a | — | **[Assumption]** |
| **No-sync alternatives** | Manual entry; bet-slip screenshot parsing (Action Network supports parlays from screenshots; Playbook reads picks from images) | Own build cost | — | **[Verified · official]** https://www.actionnetwork.com/general/faq |

No other dedicated third-party sync vendor was found this session. That is weak evidence that SharpSports is close to a single-supplier market, not proof. **[Assumption]**

**Risks specific to sync** (apply to any vendor):
- Sportsbooks have advised customers not to share passwords with third-party bet-tracking sites after account-takeover fraud (reported Sept 2026). **[Verified · 3P]** https://frontofficesports.com/major-betting-sites-fortifying-security-after-scammers-steal-thousands
- Credential-based linking may conflict with sportsbook terms of use and can break when a book changes its login flow. **[Assumption]**
- BettingPros reviews cite broken sync as the top complaint. **[Verified · 3P]** https://marlvel.ai/intel-report/sports/com-bettingpros-app
- Handling users' sportsbook credentials or tokens raises OddVex's security and privacy obligations. **[Assumption]**

## 5. Recommended shortlist (for Founder decision; nothing purchased)

| Stage | Odds + props | Stats / scores / injuries | Historical | Sync | Indicative public cost |
|---|---|---|---|---|---|
| **Prototype (free tiers only)** | The Odds API free; SportsGameOdds free; TheRundown free | BALLDONTLIE free; SportsDataIO trial | The Odds API (needs paid plan) | None; manual entry | $0 |
| **MVP** | **The Odds API** ($59–$119/mo) *or* **SportsGameOdds Rookie** ($99–$149/mo) | BALLDONTLIE paid per sport ($9.99–$39.99 each), pending a check of its commercial terms | The Odds API historical for CLV and line history | None, or screenshot/manual | Roughly $100–$350/mo |
| **Growth** | SportsGameOdds Pro ($299–$499/mo) or OddsBlaze (for SGP) | SportsDataIO (quote) | Same + own stored snapshots | SharpSports betSync (from $500/mo, metered) | Roughly $1,000–$3,000+/mo; quotes needed |
| **Scale / live EV** | OpticOdds (quote) | SportsDataIO or Sportradar (quote) | Vendor history | SharpSports or in-house | Unofficial estimates are $5,000+/mo per vendor |

**Why The Odds API is first on the MVP list:** it is the only vendor found whose public terms explicitly permit commercial display, storage, derived values and ML training, and its public price is the lowest. **[Verified · official]** terms URL above. **Why it may not be enough:** polling-only, credit-metered props, no stats, no injuries, no grading. **[Assumption]**

**Illustrative credit maths (not a quote):** one call for 3 featured markets in 1 region costs 3 credits **[Verified · official]**. Polling one sport every 60 seconds around the clock is about 3 × 1,440 × 30 ≈ 130,000 credits/month, already above the $59 plan. Props are requested per event and multiply quickly, so the 5M plan ($119) is the realistic MVP floor if props refresh every few minutes across several leagues. The per-event prop cost formula is **[Assumption]**; measure it on the free tier before choosing a plan.

**Design implication:** build a provider-agnostic ingestion layer and store every snapshot with its fetch time. This supports freshness labels, own-built line history, and switching vendors later. **[Assumption]**

## 6. Questions to ask vendor sales (before any purchase)

**Licensing and display**
1. May we display your odds to end users in a paid consumer app (iOS, Android, web)? Any per-user or per-MAU fee?
2. May we store snapshots indefinitely and show our own line-movement charts built from them? What happens to stored data if we cancel?
3. May we feed your data into an AI assistant (LLM prompts and generated explanations)? May we train or fine-tune models on it?
4. Any attribution, logo, or "odds provided by" requirement? Any required delay or disclaimer?
5. Any restriction on showing specific sportsbooks' names, logos or prices? Do you hold rights from the books, or are these collected prices?
6. Any restriction tied to official league data (NFL, NBA) for stats or live scores?
7. Are affiliate deep links allowed or required alongside your data?

**Coverage and quality**
8. Exact book list per US state, per market type (main, alt, props, SGP), per league. Which books are delayed?
9. Median and p95 delay from a book changing a price to it appearing in your API, pre-game and live. Is there a timestamp for when *you* observed the price?
10. How are suspended/locked markets represented? How are player and market IDs kept stable across books?
11. Historical depth for props and closing lines; snapshot interval; cost multiplier.
12. Do you grade props and settle markets, or do we need a separate results feed?
13. Injury/lineup data: source, update lag, and licence.

**Commercial**
14. Price for our expected volume at MVP and at 10x; overage behaviour (hard stop or billing).
15. Startup or pre-revenue pricing; monthly vs annual commitment; notice period; price-increase caps.
16. Is there a free or paid trial on production data? Sandbox?
17. SLA, status page, incident history, support channel.

**Sync vendors (SharpSports or equivalent)**
18. Current supported books by state, and how each is linked (credentials, OAuth, token). Which require re-authentication and how often?
19. Do the sportsbooks consent to this access? Has any book blocked you or sent a legal notice in the last 24 months?
20. Where are user credentials stored, who can access them, and what are your security attestations?
21. Exactly how is betSync metered (per linked account, per refresh)? What does 1,000 / 10,000 linked users cost?
22. Sync success rate and median time-to-refresh per book; history depth per book.
23. Liability and indemnity if a user's sportsbook account is restricted or compromised after linking.

## 7. What was not verified

- No vendor page was opened directly; no API was called; no latency, coverage or accuracy claim was tested.
- No full terms-of-service document was read end to end. The Odds API terms are quoted from search-tool extracts only.
- OpticOdds, SportsDataIO, Sportradar and Genius prices are unknown; third-party estimates are not reliable.
- OddsBlaze's own pricing page and official docs domain were not confirmed.
- League official-data rules and state-level requirements for a non-wagering information product were not researched.
