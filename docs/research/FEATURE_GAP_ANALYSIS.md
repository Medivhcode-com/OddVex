# OddVex Feature Gap Analysis

- **Research date:** 2026-11-15
- **Inputs:** `COMPETITOR_MATRIX.md`, `PRICING_RESEARCH.md`, `DATA_PROVIDER_EVALUATION.md` (evidence and URLs live there; this file is synthesis).
- **Tags:** **[Verified]** = rests on a tagged finding in the matrix. **[Assumption]** = my judgement or general knowledge. Most strategic conclusions here are assumptions by nature and are labelled so.
- **Status:** Recommendations for Founder review, not decisions.

## 1. Table stakes, differentiators, whitespace

### 1.1 Table stakes (users will expect these on day one)

| Capability | Evidence it is standard | Tag |
|---|---|---|
| Best-price odds comparison across major US books | Present in every product reviewed except pure model apps | **[Verified]** |
| Player-prop research: hit rates over recent games, splits, matchup context | BettingPros, Outlier, Props.Cash, Linemate all lead with it | **[Verified]** |
| A bet tracker with basic P/L | BettingPros, Action Network, Pikkit, OddsJam, Juice Reel give it away free | **[Verified]** |
| iOS app; web for research-heavy screens | All consumer products have iOS; most have web | **[Verified]** |
| Free tier or a 7-day trial | Universal | **[Verified]** |
| Major US leagues: NFL, NBA, MLB, NHL, college football and basketball | Standard coverage lists | **[Verified]** |
| Injury and lineup context next to the numbers | Outlier, Stat Sniper, SportsDataIO-fed apps | **[Verified]** |
| Responsible-gambling messaging and "we do not take wagers" clarity | Props.Cash, Pikkit, Outlier, Rithmm all state it | **[Verified]** |

### 1.2 Differentiators (some have them; they separate tiers and brands)

| Capability | Who has it | Cost to match | Tag |
|---|---|---|---|
| Automatic sportsbook sync | Pikkit, Action Network, BettingPros, OddsJam, Juice Reel | High: vendor from $500/mo metered, plus reliability and security burden | **[Verified]** |
| CLV analysis with selectable benchmark | Pikkit Pro, OddsJam, Juice Reel, Unabated | Medium: needs closing-line history | **[Verified]** |
| Live +EV / arbitrage / middles scanners | OddsJam, Outlier Pro, Unabated, SharpStack, DarkHorse | Very high: sub-second data, quotes in the thousands per month | **[Verified]** price bands; cost is **[Assumption]** from third-party estimates |
| AI assistant | BettingPros Sharp AI, Action Playbook, Outlier AI Analysis, Rithmm Scout, Stat Sniper Chad | Medium: model cost per query, quality control | **[Verified]** |
| Backtested systems / custom models | BettingPros Elite, Action PRO/Labs, Rithmm | Medium–high | **[Verified]** |
| Social graph, copy-betting, picks marketplace | Pikkit, Juice Reel, Action Network | High; network effects favour incumbents | **[Verified]** existence; **[Assumption]** on difficulty |
| Public betting / money percentages | Action Network | Requires sportsbook data partnerships | **[Verified]** existence; **[Assumption]** on sourcing |
| Prediction-market prices alongside sportsbook odds | Action Network, Linemate, Unabated, DarkHorse | Low–medium | **[Verified]** |
| SGP line shopping | Pikkit Pro, Juice Reel | Needs an SGP-capable feed (OddsBlaze, OpticOdds) | **[Verified]** |

### 1.3 Whitespace (not found in any product reviewed)

"Not found" means it did not appear in the store listings, help centres and reviews the search tool surfaced. It is absence of evidence. Each item needs a hands-on check of the competitor apps before it is used in positioning.

| Whitespace | What was (not) observed | Tag |
|---|---|---|
| **Visible freshness on every number** ("price seen 40s ago at Book X") | No listing or help article mentions per-price timestamps as a feature | **[Assumption]** |
| **Published methodology** for hit rates, fair odds, projections and EV | Only Pikkit documents a method choice (CLV benchmark). Rithmm reportedly does not publish aggregate accuracy/ROI. | **[Verified]** for those two points; generalisation is **[Assumption]** |
| **Calibrated uncertainty** (sample size, confidence range, "not enough data") | Hit-rate UIs lead with "8 of last 10" style stats; no evidence of sample-size warnings. A 2026 audit cites user complaints about wrong hit rates (Outlier) and inaccurate AI predictions (BettingPros). | Complaints **[Verified · 3P]**; the gap is **[Assumption]** |
| **AI that explains and cites rather than picks** | Assistants are framed around picks, signals or slips. Outlier's "supporting and opposing" analysis is the closest to balanced explanation. | **[Verified]** framing; **[Assumption]** on depth |
| **A closed research → decide → track → learn loop** | Research apps (Outlier, Props.Cash, Linemate) lack trackers; trackers (Pikkit, Juice Reel) lack deep prop research. BettingPros and Action Network have both, with no evidence the tracker feeds back into research. | **[Verified]** per-product; "no feedback loop" is **[Assumption]** |
| **Beginner-to-pro progression in one product** | Linemate targets novices; OddsJam and Unabated target sharps; the price gap between them is ~10–30x | **[Verified]** positioning and price; **[Assumption]** that the middle is underserved |
| **Honest framing of EV for normal users** (limits, variance, account restrictions) | EV tools are marketed on profit potential | **[Assumption]** |

## 2. Where OddVex can credibly win

Ordered by how well each fits a small team with MVP-grade data.

| # | Bet | Why it is credible | What it requires | Risk | Tag |
|---|---|---|---|---|---|
| 1 | **Freshness labelling as a product principle.** Every price and stat shows its source and age; stale data is visibly marked. | Turns a weakness (polling-grade data) into a trust feature. Cheap vendors can support it if fetch time is stored. | Store fetch timestamps per snapshot; UI standard; staleness thresholds. | Users may read "2 min old" as worse than a rival that hides age. | **[Assumption]** |
| 2 | **Transparent methodology.** A plain-language "how we calculate this" for hit rate, fair odds, EV, projections, plus versioned changelogs. | Needs no extra data. Competitors' opacity is a recurring complaint theme. | Writing discipline; method pages; in-context "why" links. | Exposes methods to copying and criticism. | **[Assumption]** |
| 3 | **Honest uncertainty.** Sample sizes, ranges, and explicit "insufficient data" states; no hit-rate without a denominator and context. | Differentiates directly against "8/10" marketing; reduces the chance of misleading users. | Statistical design; restraint in UI copy. | Looks less exciting than confident picks; may convert worse. | **[Assumption]** |
| 4 | **AI assistant that explains, cites and declines.** Answers grounded in OddVex's own data with visible sources and timestamps; says when it does not know; does not issue "locks". | Incumbent assistants are pick- or slip-oriented and metered. A grounded explainer is achievable with retrieval over own data. | Retrieval layer, evaluation set, cost metering, safety policy. | Hallucinated numbers would damage the core trust claim; cost per query. | **[Assumption]** |
| 5 | **Unified research → track loop.** Save a researched bet in one tap; later see it graded with the price you saw, the closing price, and whether the reasoning held. | Research-only and tracker-only apps each miss half. Works with manual entry; sync not needed at first. | Tracker, closing-line capture, grading feed. | Manual entry friction; Pikkit sets expectations of auto-sync. | **[Assumption]** |
| 6 | **Beginner approachability with pro depth.** Plain-language default; glossary in context; progressive disclosure to no-vig prices, CLV, EV. | Linemate proves demand for approachable research at $15/mo; the sharp tools start at $80–$500. | Design investment; two-level information architecture. | Trying to serve both can serve neither. | **[Verified]** prices; rest **[Assumption]** |
| 7 | **Fair pricing with no dark patterns.** Clear tiers, easy cancel, no perpetual fake discounts. | Promotion-heavy list prices are common (Action Network, OddsJam, Outlier). | Policy decision. | Lower short-term conversion. | **[Verified]** observation; rest **[Assumption]** |

**Suggested MVP wedge (proposal):** props and odds research with freshness labels and method notes, a manual tracker with CLV, and a metered, grounded AI explainer for 2–3 leagues. This avoids the two most expensive dependencies (sub-second odds and account sync). **[Assumption]** — requires Founder approval.

## 3. What NOT to build early

| Do not build yet | Reason | Tag |
|---|---|---|
| Live arbitrage / middles / low-hold scanners | Needs sub-second multi-book data (quotes reportedly in the thousands per month); OddsJam, Outlier Pro and Unabated are entrenched; attracts users who churn when limited by books | Cost estimates **[Verified · 3P]**; rest **[Assumption]** |
| Automatic sportsbook sync | Vendor from $500/mo and metered; top complaint source for BettingPros; sportsbooks warn users against sharing credentials; adds credential-security liability | **[Verified]** |
| Picks marketplace, tout subscriptions, copy-betting | Conflicts with a transparency-first, non-tout brand; moderation, fraud and payout complexity; Juice Reel and Pikkit hold the network effects | **[Assumption]** |
| Bet-slip building / deep-link placement (Playbook-style) | Moves toward facilitating wagers; needs affiliate and book integrations; legal review needed | **[Assumption]** |
| Full social feed, group chat, livestreaming | Network-effect features with high moderation cost and little early value | **[Assumption]** |
| User-built custom models and a model leaderboard (Rithmm-style) | Large surface area; invites overfitting and misleading "top model" claims | **[Assumption]** |
| Proprietary "AI picks" with confidence scores | Hard to do honestly without a long, published track record; contradicts the uncertainty stance | **[Assumption]** |
| DFS pick'em optimizers and lineup tools | A separate product category with its own competitors | **[Assumption]** |
| All sports and international books at launch | Each league multiplies data cost and QA; start with 2–3 leagues | **[Assumption]** |
| Public betting / money percentages | Requires sportsbook data deals | **[Assumption]** |
| In-game / live betting signals | Outlier split this into a separate app (React Live); latency-critical | **[Verified]** that it is separate; rest **[Assumption]** |
| A public OddVex data API | The Odds API terms prohibit redistribution as a data product; most vendors will too | **[Verified]** for The Odds API |

**Worth a cheap look later (not MVP):** prediction-market prices beside sportsbook odds (incumbents are adding them); screenshot-to-tracker entry as a no-credential alternative to sync. **[Verified]** trend; **[Assumption]** on fit.

## 4. Risks

| Risk | Detail | Mitigation idea | Tag |
|---|---|---|---|
| **Data licensing** | Only one vendor's display terms were found publicly. Others may restrict storage, AI use or book branding. | Ask the questions in `DATA_PROVIDER_EVALUATION.md` §6 before building on a feed; keep ingestion provider-agnostic. | **[Verified]** for the one vendor; rest **[Assumption]** |
| **Data cost vs price point** | A $15–$20/mo tier cannot fund $5,000/mo feeds until scale. | Start on low-cost feeds; label freshness; defer live tools. | **[Assumption]** |
| **Freshness honesty backfires** | Showing data age makes polling-grade data look slow next to rivals. | Position it as a feature; set and publish staleness thresholds. | **[Assumption]** |
| **AI errors** | A wrong number from the assistant undermines the core claim. Third-party audits already cite inaccurate AI predictions at an incumbent. | Ground answers in stored data, show sources and timestamps, evaluate before release, allow "I don't know". | Complaint **[Verified · 3P]**; rest **[Assumption]** |
| **AI unit cost** | Every competitor meters AI. | Meter from day one; measure cost per query before pricing. | **[Verified]** metering; rest **[Assumption]** |
| **Regulatory and platform** | State rules on gambling advertising and affiliates, app-store rules for gambling-adjacent apps, age-gating, and consumer-protection rules on performance claims all apply in some form. **None of this was researched this session.** | Commission a legal review before launch and before any affiliate deal. | **[Assumption]** |
| **Responsible gambling** | A research tool can encourage more betting. | RG messaging, limits and reminders in the tracker, no "lock" language, helpline links. | **[Assumption]** |
| **Incumbent response** | BettingPros and Action Network already bundle research, tracker, sync and AI at $30–$50/mo with media reach. | Win on trust and clarity, not breadth. | **[Verified]** bundles; rest **[Assumption]** |
| **Low price anchors** | Linemate at $59.99/yr and Stat Sniper at $7.99/mo cap what beginners will pay. | Free tier plus a clearly better paid tier; avoid racing to the bottom. | **[Verified]** prices |
| **Sync expectation gap** | Pikkit trains users to expect zero-effort tracking. | Make manual entry one tap from research; consider screenshot import. | **[Assumption]** |
| **Sportsbook hostility** | Books warn against credential sharing and may restrict third-party access. | Avoid credential-based sync early. | **[Verified · 3P]** warning; rest **[Assumption]** |
| **Research base** | This analysis rests on search-tool extracts, not direct page reads or hands-on app use. | Before committing to positioning, do a hands-on teardown of the top five apps. | **[Verified]** (limitation of this session) |

## 5. Open questions for the Founder

1. Is the MVP wedge in §2 (research + manual tracker + grounded AI, no sync, no live scanners) acceptable?
2. Which 2–3 leagues first?
3. Is affiliate revenue in or out, given the transparency positioning?
4. How strict is the "no picks" stance? May the AI rank options, or only explain them?
5. Budget ceiling for data in the first six months (drives the vendor shortlist)?
