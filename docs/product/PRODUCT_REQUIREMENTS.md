# OddVex — Product Requirements Document (PRD)

| | |
|---|---|
| Product | OddVex — sports-betting intelligence platform (https://oddvex.com) |
| Parent company | Medivh Code |
| Tagline | "Every Line. A Smarter Perspective." |
| Market | United States, adults 21+ |
| Doc owner | Product + Compliance documentation |
| Last updated | 2026-11-15 |
| Status | Living document. M1 is in build; everything after M1 is planned, not built. |

Related: [MASTER_FEATURE_INVENTORY.md](./MASTER_FEATURE_INVENTORY.md) · [SCREEN_MAP.md](./SCREEN_MAP.md) · [USER_JOURNEYS.md](./USER_JOURNEYS.md) · [ROADMAP.md](./ROADMAP.md) · [../compliance/COMPLIANCE_OVERVIEW.md](../compliance/COMPLIANCE_OVERVIEW.md) · competitor research in `docs/research/` (owned by another workstream).

---

## 1. Vision

OddVex gives anyone who follows sports betting markets a clear, honest view of every line: where the price is best, what the number implies, how a player has actually performed against a prop, and how the user's own betting has really gone.

OddVex is an **information and analytics product**. It **never accepts, places, routes or settles wagers, and never holds user funds.**

### 1.1 What OddVex is / is not

| OddVex is | OddVex is not |
|---|---|
| Odds comparison across sportsbooks | A sportsbook, exchange, or betting agent |
| Research tools (props, calculators, parlay analysis) | A picks / tout / "locks" service |
| A personal bet tracker and performance ledger | A wallet, payment, or funds-holding product |
| A grounded assistant that explains verified data | A predictor that promises outcomes |

### 1.2 Current-build reality (must stay visible in product and docs)

- All data in the current build is **synthetic fixtures** with **fictional teams, players and sportsbooks**. No real data provider has been purchased.
- Sportsbook sync is a **mock adapter**. No real sportsbook account is ever contacted.
- OddVex AI v0 is **rule-based** (no LLM).
- The product must label demo data in-app (see NFR-01, HOME-02).

---

## 2. Target users and personas

| Persona | Who | Goals | Frustrations | What OddVex must do |
|---|---|---|---|---|
| **P1 — Curious Fan ("Casey")** | Follows sports, bets rarely or not at all; unfamiliar with odds notation | Understand what a line means; follow games | Jargon; intimidating tools; hype-heavy apps | Plain-language explanations, implied probability everywhere, no pressure to bet |
| **P2 — Recreational Bettor ("Riley")** | Bets regularly for entertainment on one to three sportsbooks | Get a fair price; keep track of results; research props quickly | Doesn't know if a price is good; no honest record of results; scattered tabs | Best-line highlighting, simple prop history, low-friction tracker, honest P/L |
| **P3 — Serious / Sharp Bettor ("Sam")** | Treats betting analytically; multiple books; tracks CLV | Fast multi-book comparison; no-vig prices; EV/CLV; exportable records | Stale data; hidden methodology; slow UIs | Dense views, timestamps on every number, transparent formulas, keyboard-friendly web |

Out of audience: anyone under 21; anyone located where use would be unlawful (to be defined with counsel).

---

## 3. Problems we solve

| # | Problem | Personas | Product response |
|---|---|---|---|
| PB-1 | Prices differ across sportsbooks and comparing them manually is slow | P2, P3 | Odds Comparison (C) |
| PB-2 | Odds notation hides the real probability and the bookmaker margin | P1, P2 | Implied probability + no-vig everywhere (C, E) |
| PB-3 | Prop research is scattered and often presented with hype | P2, P3 | Prop Analyzer with sample sizes and neutral labelling (D) |
| PB-4 | Most bettors have no accurate record of results | P2, P3 | Bet Tracker + Sync (F, G) |
| PB-5 | Parlay risk and leg correlation are poorly understood | P1, P2 | Parlay Research with correlation warnings (I) |
| PB-6 | AI tools in this category invent numbers | all | OddVex AI answers only from verified internal tools (H) |
| PB-7 | Users cannot tell how fresh a number is | all | Freshness labelling on every datum (NFR-01) |

---

## 4. Product principles

1. **Information, never wagering.** No bet placement, no funds, no bet-slip hand-off that executes a wager.
2. **Every number has a source and a time.** No unlabelled data; stale data is visibly stale.
3. **No invented numbers.** The assistant and UI display only values produced by internal data tools or deterministic calculators.
4. **No guarantees, no hype.** We describe probability and history; we never promise wins or call anything a "lock".
5. **Show the method.** Every calculation links to its formula (`/methodology`).
6. **Responsible by design.** 21+ only; helpline and RG resources always reachable; no dark patterns that push betting volume.
7. **Dense for experts, clear for newcomers.** Analytics-terminal precision with consumer simplicity.
8. **Privacy-minimal.** Collect only what features need; never store sportsbook credentials.
9. **Honest states.** Loading, empty, stale and error states are first-class designs, not afterthoughts.

---

## 5. Scope by product area

Legend — **MS**: milestone (see ROADMAP). **Status**: `M1` = in M1 scope (in build now); `M1?` = assumed M1 scope, engineering to verify at M1 exit; `Later` = planned, not built. Full detail, tiers and dependencies are in the Master Feature Inventory.

### A. Home (dashboard) — `HOME`

Purpose: a single at-a-glance starting point at `/app`.

| ID | Requirement | MS | Status |
|---|---|---|---|
| HOME-01 | Dashboard shows today's games, notable best-line differences, and a tracker snapshot | M1 | M1 |
| HOME-02 | Persistent data-status indicator: "Demo data — synthetic fixtures" while fixtures are in use, plus global freshness | M1 | M1 |
| HOME-03 | Quick actions into Odds, Props, Tools, Assistant | M1 | M1 |
| HOME-04 | Personalised modules from favorites/watchlists | M2 | Later |
| HOME-05 | Line-movement and alert feed module | M3 | Later |
| HOME-06 | First-run onboarding checklist | M2 | Later |

Acceptance criteria (M1):
- AC-HOME-1: With no bets logged, tracker module shows an empty state with a "Log a bet" action, not zeros presented as results.
- AC-HOME-2: Demo-data indicator is visible on every `/app/*` route while `data_mode` is synthetic.
- AC-HOME-3: Each module handles loading, empty, stale and error states independently (one failing module does not blank the page).

### B. Games & Live Scores — `GAME`

| ID | Requirement | MS | Status |
|---|---|---|---|
| GAME-01 | Games list by sport/league/date with status (scheduled / live / final / postponed) | M1 | M1 |
| GAME-02 | Live score with period/clock and "as of" timestamp (simulated from fixtures in M1) | M1 | M1 |
| GAME-03 | Game detail: score, odds snapshot across sportsbooks, related props | M1 | M1 |
| GAME-04 | Filters: sport, league, date, status | M1 | M1 |
| GAME-05 | Favorite teams/leagues (persisted) | M2 | Later |
| GAME-06 | Box score, play-by-play, team stats | M2 | Later |
| GAME-07 | Injuries and lineups | M3 | Later |
| GAME-08 | Game start / score notifications | M3 | Later |
| GAME-09 | Mobile games list + game detail | M1 | M1 |

Acceptance criteria (M1):
- AC-GAME-1: Times render in the user's local time zone with the zone indicated.
- AC-GAME-2: A live score older than the stale threshold shows a stale badge and the last-updated time.
- AC-GAME-3: Unknown game ID returns a not-found state with a link back to `/app/games`.
- AC-GAME-4: Live-score updates are announced politely to assistive tech (no focus theft).

### C. Odds Comparison — `ODDS`

| ID | Requirement | MS | Status |
|---|---|---|---|
| ODDS-01 | Comparison grid: moneyline, spread, total across sportsbooks | M1 | M1 |
| ODDS-02 | Best available line highlighted per outcome (not colour-only) | M1 | M1 |
| ODDS-03 | Odds format toggle: American / decimal / implied % | M1 | M1? |
| ODDS-04 | Per-price "as of" timestamp and stale flag | M1 | M1 |
| ODDS-05 | Filter by sport, league, market, sportsbook | M1 | M1 |
| ODDS-06 | No-vig fair price and hold % per market | M1 | M1? |
| ODDS-07 | Line-movement history chart | M2 | Later |
| ODDS-08 | "My sportsbooks" selection, with availability by state | M2 | Later |
| ODDS-09 | Outbound links to sportsbooks (affiliate or plain) | M3 | Later — legal gate |
| ODDS-10 | Alternate lines and additional markets (periods, futures) | M3 | Later |
| ODDS-11 | Mobile odds comparison | M1 | M1 |
| ODDS-12 | Price / line alerts | M3 | Later |

Acceptance criteria (M1):
- AC-ODDS-1: For each outcome, the highlighted best line equals the maximum payout price among displayed, non-stale sportsbooks; ties highlight all tied books.
- AC-ODDS-2: Stale prices are excluded from best-line calculation and visually marked.
- AC-ODDS-3: A market missing at a sportsbook renders "—" with an accessible label "not offered", never 0 or blank.
- AC-ODDS-4: Format toggle converts without rounding drift (round-trip American → decimal → American returns the original price).
- AC-ODDS-5: Grid is usable at 360 px width (horizontal scroll with sticky outcome column) and by keyboard.

### D. Prop Analyzer — `PROP`

| ID | Requirement | MS | Status |
|---|---|---|---|
| PROP-01 | Prop list by game / player / market with lines across sportsbooks | M1 | M1 |
| PROP-02 | Player prop detail: recent game log vs. the line, hit rate over last N games | M1 | M1 |
| PROP-03 | Best line and best price across sportsbooks per prop | M1 | M1 |
| PROP-04 | Splits (home/away, opponent, rest) | M2 | Later |
| PROP-05 | Sample-size display and "historical, not predictive" labelling | M1 | M1 |
| PROP-06 | Model projections with published methodology and uncertainty | M4 | Later |
| PROP-07 | Prop watchlist | M2 | Later |
| PROP-08 | Prop alerts | M3 | Later |
| PROP-09 | Mobile prop analyzer | M3 | Later |
| PROP-10 | Matchup context (e.g. defence vs. position) | M3 | Later |

Acceptance criteria (M1):
- AC-PROP-1: Hit rate always shows numerator/denominator (e.g. "6 of 10"), never a bare percentage.
- AC-PROP-2: With fewer than a minimum sample (configurable; proposal: 5 games) the UI shows "limited sample" instead of a rate.
- AC-PROP-3: No copy implies prediction ("will", "lock", "smash"); history is described as history.
- AC-PROP-4: Charts have a text/table alternative.

### E. Betting Intelligence (calculators and analytics) — `INTL`

| ID | Requirement | MS | Status |
|---|---|---|---|
| INTL-01 | Implied probability / odds converter | M1 | M1 |
| INTL-02 | No-vig (fair odds) calculator | M1 | M1 |
| INTL-03 | Expected value (EV) calculator | M1 | M1 |
| INTL-04 | Closing line value (CLV) calculator | M1 | M1 |
| INTL-05 | Parlay calculator | M1 | M1 |
| INTL-06 | Each calculator shows its formula and links to `/methodology` | M1 | M1 |
| INTL-07 | Hedge and arbitrage calculators | M2 | Later |
| INTL-08 | Bankroll / staking calculator (subject to RG review) | M3 | Later |
| INTL-09 | Market-wide discrepancy / +EV screen | M4 | Later |
| INTL-10 | Backtesting of projections/strategies | M4 | Later |
| INTL-11 | Alerts engine (line move, price threshold) | M3 | Later |
| INTL-12 | Mobile calculators | M3 | Later |

Acceptance criteria (M1):
- AC-INTL-1: Calculator maths lives in a shared, unit-tested module used by web, API and the assistant (one source of truth).
- AC-INTL-2: Reference test vectors pass (e.g. American −110 ⇒ implied 52.38 %; +150 ⇒ 40.00 %; two-way −110/−110 ⇒ no-vig 50.00 % each).
- AC-INTL-3: Invalid inputs (0, between −100 and +100 American, non-numeric, negative stake) give inline, described errors; no NaN/Infinity is ever shown.
- AC-INTL-4: EV output states that the result depends on the user's own probability estimate and is not a prediction.
- AC-INTL-5: Results are announced to screen readers when recalculated.

### F. Bet Tracker — `TRKR`

| ID | Requirement | MS | Status |
|---|---|---|---|
| TRKR-01 | Manual bet entry (sportsbook, market, selection, odds, stake, date) | M1 | M1 |
| TRKR-02 | Manual settlement: win / loss / push / void / cash-out | M1 | M1 |
| TRKR-03 | Performance summary: net P/L, ROI, record; by sport / book / market | M1 | M1 |
| TRKR-04 | Bet list: filter, sort, edit, delete | M1 | M1 |
| TRKR-05 | CLV per bet (closing odds entered manually in M1) | M1 | M1? |
| TRKR-06 | Automatic settlement and automatic closing odds | M2 | Later |
| TRKR-07 | CSV export (M2) and import (M3) | M2/M3 | Later |
| TRKR-08 | Results-over-time chart | M1 | M1? |
| TRKR-09 | Tags and notes | M2 | Later |
| TRKR-10 | Spending-awareness insights (RG) | M3 | Later |
| TRKR-11 | Mobile tracker | M3 | Later |
| TRKR-12 | Multi-leg (parlay) bets | M1 | M1? |
| TRKR-13 | Advanced analytics (deeper breakdowns, custom ranges) | M4 | Later |

Acceptance criteria (M1):
- AC-TRKR-1: P/L and ROI are computed only from settled bets; pending bets are shown separately.
- AC-TRKR-2: Losses are displayed as plainly as wins (no hiding, softening or celebratory framing).
- AC-TRKR-3: Edits to a settled bet recalculate summaries immediately and consistently.
- AC-TRKR-4: A user can only read/write their own bets (authorization test required).
- AC-TRKR-5: Money uses decimal arithmetic server-side (no binary floating-point totals).

### G. Sportsbook Sync — `SYNC`

Principle: sync only through **authorized third-party sync vendors**; OddVex never scrapes sportsbooks and never stores sportsbook credentials. M1 ships a **mock adapter only**.

| ID | Requirement | MS | Status |
|---|---|---|---|
| SYNC-01 | Provider-agnostic sync adapter interface | M1 | M1 |
| SYNC-02 | Mock adapter: connect a fictional sportsbook and import synthetic bets | M1 | M1 |
| SYNC-03 | Connection management: status, last synced, disconnect | M1 | M1 |
| SYNC-04 | De-duplication of synced vs. manually entered bets | M1 | M1? |
| SYNC-05 | Authorized third-party vendor integration | M3 | Later — Founder + counsel gate |
| SYNC-06 | No credential storage by OddVex (vendor-hosted link flow, tokens only) | M1 design / M3 enforced | Design principle |
| SYNC-07 | Scheduled re-sync and error recovery | M3 | Later |
| SYNC-08 | Consent screen and disclosures before connecting | M1 (mock) / M3 | M1? |
| SYNC-09 | Delete synced data on disconnect (user choice) | M2 | Later |

Acceptance criteria (M1):
- AC-SYNC-1: Mock flow is labelled "Demo connection — no real sportsbook is contacted".
- AC-SYNC-2: The mock flow never renders a field that asks for a real sportsbook username or password.
- AC-SYNC-3: Synced bets are marked with their source and are distinguishable from manual entries.
- AC-SYNC-4: Disconnect stops further imports and updates connection status immediately.

### H. OddVex AI — `AI`

Contract: the assistant **answers only from verified internal data tools and deterministic calculators; it never invents numbers**; if data is unavailable it says so.

| ID | Requirement | MS | Status |
|---|---|---|---|
| AI-01 | Assistant chat UI at `/app/assistant` | M1 | M1 |
| AI-02 | Rule-based intent router to internal tools (odds, props, calculators, tracker) | M1 | M1 |
| AI-03 | Grounding: every numeric value originates from tool output; answer shows source and "as of" | M1 | M1 |
| AI-04 | Refusals: no guarantees, no "locks", no advice to bet; "I don't have that data" when a tool returns nothing | M1 | M1 |
| AI-05 | AI disclosure label and responsible-gambling footer | M1 | M1 |
| AI-06 | Suggested prompts | M1 | M1 |
| AI-07 | LLM-backed assistant with tool calling under the same grounding contract | M4 | Later — paid API gate |
| AI-08 | Evaluation suite: numeric fidelity, refusal behaviour, prompt-injection resistance | M4 | Later |
| AI-09 | Conversation history persistence and deletion | M4 | Later |
| AI-10 | Answer feedback (helpful / not helpful / report) | M2 | Later |
| AI-11 | Usage limits by tier | M4 | Later |
| AI-12 | Mobile assistant | M4 | Later |

Acceptance criteria (M1):
- AC-AI-1: Automated test: every number in an assistant response is traceable to a tool-call result or calculator output in the same turn.
- AC-AI-2: Unsupported questions return a clear capability message with example supported questions — never a guess.
- AC-AI-3: "Who will win?"-style prompts return available market data (prices, implied probability) plus a statement that OddVex does not predict outcomes.
- AC-AI-4: Tracker questions only ever read the requesting user's data.
- AC-AI-5: The UI states that the assistant is automated and, in M1, that it is rule-based and running on demo data.

### I. Parlay Research — `PRLY`

| ID | Requirement | MS | Status |
|---|---|---|---|
| PRLY-01 | Parlay builder at `/app/parlay`: add legs, see combined odds and payout | M1 | M1 |
| PRLY-02 | Combined implied probability and per-leg breakdown | M1 | M1 |
| PRLY-03 | Correlation warning for same-game / related legs (rule-based) | M1 | M1? |
| PRLY-04 | Parlay price comparison across sportsbooks | M3 | Later — depends on provider coverage |
| PRLY-05 | Send parlay to tracker (M1?) and save parlay drafts (M2) | M1/M2 | M1? / Later |
| PRLY-06 | Quantified correlation estimates (model-based) | M4 | Later |
| PRLY-07 | Mobile parlay research | M3 | Later |

Acceptance criteria (M1):
- AC-PRLY-1: Combined decimal odds equal the product of leg decimal odds; shown with the statement that this assumes independent legs.
- AC-PRLY-2: When two or more legs share a game (or the same player), a warning explains that legs may be correlated, that the independent-legs figure may be inaccurate, and that sportsbooks may price or restrict such combinations differently.
- AC-PRLY-3: The page states that OddVex does not place bets; there is no "place bet" control.
- AC-PRLY-4: Combined probability is shown alongside payout so long-odds parlays are not presented only as a large payout.

### J. Community — `COMM` (M5, not built)

| ID | Requirement | MS |
|---|---|---|
| COMM-01 | Pseudonymous profiles | M5 |
| COMM-02 | Discussion threads on games/props | M5 |
| COMM-03 | Share tracked bets/records (with "synced" vs. "self-reported" badge) | M5 |
| COMM-04 | Follow and feed | M5 |
| COMM-05 | Report, block, mute | M5 |
| COMM-06 | Moderation queue and enforcement (with ADMN-05) | M5 |
| COMM-07 | Leaderboards (only if approved after RG review) | M5 |
| COMM-08 | Community guidelines incl. no pick-selling, no guaranteed-win claims | M5 |

Pre-conditions: UGC policy, moderation staffing, counsel review, app-store UGC requirements (see compliance docs).

### K. Premium — `PREM` (M4, not built)

| ID | Requirement | MS |
|---|---|---|
| PREM-01 | Plans and entitlements service | M4 |
| PREM-02 | Web checkout via payment processor | M4 |
| PREM-03 | iOS / Android in-app purchase | M4 (ships with store release) |
| PREM-04 | Paywall and upgrade surfaces (no deceptive patterns) | M4 |
| PREM-05 | Subscription management: renewal disclosure, easy cancel, restore | M4 |
| PREM-06 | Trials / promotions (proposal only) | M4 |
| PREM-07 | Billing receipts and renewal reminders | M4 |

Tier assignments in the inventory are **proposals only**; pricing and packaging require Founder approval. M1 `/pricing` must state that Premium is not yet available and must not show prices that have not been approved.

### L. Admin — `ADMN`

| ID | Requirement | MS | Status |
|---|---|---|---|
| ADMN-01 | Role-gated admin overview endpoint (basic counts and health) | M1 | M1 |
| ADMN-02 | Admin console UI | M5 | Later |
| ADMN-03 | User management (lookup, suspend, deletion/export handling) | M5 | Later |
| ADMN-04 | Data-provider health and freshness monitor | M2 basic / M5 full | Later |
| ADMN-05 | Moderation queue | M5 | Later |
| ADMN-06 | Feature flags / remote config | M3 | Later |
| ADMN-07 | Audit log of admin actions | M2 | Later |
| ADMN-08 | Subscription / entitlement support tools | M5 | Later |
| ADMN-09 | Assistant quality review (privacy-preserving) | M4 | Later |

Acceptance criteria (M1): AC-ADMN-1: endpoint returns 401 unauthenticated and 403 for non-admin roles; returns aggregates only (no per-user personal data).

### Cross-cutting — `AUTH`, `SET`, `NOTF`, `DATA`, `MKT`, `MOB`

| ID | Requirement | MS | Status |
|---|---|---|---|
| AUTH-01 | Email + password signup and login | M1 | M1 |
| AUTH-02 | 21+ attestation and Terms/Privacy acceptance at signup (recorded with timestamp and document version) | M1 | M1? |
| AUTH-03 | Session management and logout | M1 | M1 |
| AUTH-04 | Email verification and password reset | M2 | Later — real email gate |
| AUTH-05 | MFA / passkeys / social login | M3 | Later |
| AUTH-06 | Self-serve account deletion and data export | M2 | Later — **required before any real user** |
| AUTH-07 | Role-based access control (user, admin) | M1 | M1 |
| SET-01 | Settings: profile, odds format, time zone | M1 | M1 |
| SET-02 | Notification preferences | M3 | Later |
| SET-03 | Responsible-gambling resources in Settings (M1 links; M3 tools) | M1/M3 | M1? / Later |
| NOTF-01 | Push notification infrastructure | M3 | Later |
| NOTF-02 | Email notifications | M3 | Later |
| DATA-01 | Synthetic fixture data layer (fictional teams/players/sportsbooks) | M1 | M1 |
| DATA-02 | Data-provider abstraction interface | M1 | M1 |
| DATA-03 | Licensed data provider integration | M2 | Later — licence gate |
| DATA-04 | Freshness and provenance metadata on every payload (`last_updated`, `is_stale`, `provider`, `fetched_at`, `data_mode`) per ADR-0002 | M1 | M1 |
| DATA-05 | Historical odds storage | M2 | Later |
| MKT-01 | Marketing website (routes in SCREEN_MAP) | M1 | M1 |
| MKT-02 | Legal pages as drafts pending counsel | M1 | M1 (draft copy) |
| MKT-03 | `/methodology` | M1 | M1 |
| MKT-04 | Waitlist capture | M2 | Later — real email gate |
| MKT-05 | Programmatic SEO pages | M2+ | Later |
| MOB-01 | Expo app shell, navigation, design-system tokens | M1 | M1 |
| MOB-02 | Mobile auth and account | M2 | Later (verify) |
| MOB-03 | Store builds and submission | M6 | Later — Founder gate |

---

## 6. Non-goals

| # | Non-goal | Reason |
|---|---|---|
| NG-1 | Accepting, placing, routing or settling wagers | Core product boundary; licensing |
| NG-2 | Holding user funds or processing sportsbook deposits/withdrawals | Same |
| NG-3 | Selling picks, "locks", or guaranteed-outcome content | Brand, consumer-protection and RG risk |
| NG-4 | Scraping sportsbooks or bypassing their access controls | Legal/ToS risk; only licensed data and authorized sync vendors |
| NG-5 | Storing sportsbook usernames/passwords | Security and trust |
| NG-6 | Serving users under 21 or marketing to minors | Policy |
| NG-7 | Markets outside the US at launch | Focus; separate legal analysis needed |
| NG-8 | Daily fantasy contests, casino, poker, sweepstakes products | Out of scope |
| NG-9 | Automated bet execution / bots | Follows from NG-1 |
| NG-10 | Showing real team, league, player or sportsbook names/logos before licences and legal review | Current build is fictional by design |

---

## 7. Non-functional requirements

### 7.1 Data freshness and labelling

| ID | Requirement |
|---|---|
| NFR-01 | Every odds, score and stat payload carries freshness and provenance metadata (`last_updated`, `is_stale`, `provider`, `fetched_at`, response-level `data_mode`; see `docs/architecture/ADR-0002-data-and-freshness.md`). The API, not the client, decides staleness. UI shows an "as of" time for each data block. |
| NFR-02 | Stale thresholds are configurable per data type. Current defaults per ADR-0002: 120 s for live prices, 15 min for pre-game prices (to tune with a real provider). Thresholds for scores and stats are not yet defined — proposal: live scores 120 s; stats 24 h. |
| NFR-03 | Stale data is visibly marked, excluded from "best line", and never silently presented as current. |
| NFR-04 | While fixtures are in use, a "Demo data" indicator is shown on all data screens and in assistant answers. |
| NFR-05 | If the data source is unavailable, show last known data with its age, or an error state — never fabricated placeholders. |

### 7.2 Accessibility — WCAG 2.2 AA

| ID | Requirement |
|---|---|
| NFR-10 | Conformance target: WCAG 2.2 Level AA for web app and marketing site; equivalent platform practices on iOS/Android (VoiceOver, TalkBack, Dynamic Type / font scaling). |
| NFR-11 | Colour is never the only signal (best line, win/loss, up/down movement use icon/text too). Text contrast ≥ 4.5:1; UI components ≥ 3:1. |
| NFR-12 | Full keyboard operability; visible focus not obscured; target size ≥ 24×24 CSS px (WCAG 2.2), 44 pt on mobile. |
| NFR-13 | Data tables use proper header semantics; charts have text/table alternatives. |
| NFR-14 | Live updates use polite live regions; `prefers-reduced-motion` respected. |
| NFR-15 | Automated a11y checks in CI plus manual screen-reader pass before each milestone exit. |

### 7.3 Performance budgets (targets; measured at p75 unless stated)

| ID | Surface | Budget |
|---|---|---|
| NFR-20 | Marketing pages | LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 on mid-tier mobile / 4G |
| NFR-21 | Web app routes | LCP ≤ 2.5 s; route transition ≤ 1 s to meaningful content; odds grid interaction ≤ 100 ms |
| NFR-22 | API (read endpoints) | p95 ≤ 300 ms server time; p99 ≤ 1 s (fixtures; revisit with real provider) |
| NFR-23 | Assistant v0 | Response ≤ 1 s p95 (rule-based) |
| NFR-24 | Mobile app | Cold start to interactive ≤ 3 s on mid-tier device; smooth scrolling in lists (virtualised) |
| NFR-25 | Bundles | Budgets enforced in CI; initial JS for marketing pages kept minimal (exact KB budget to be set by engineering) |

### 7.4 Privacy and security (summary; details in compliance docs)

| ID | Requirement |
|---|---|
| NFR-30 | Data minimisation: collect only fields needed for the feature. No date of birth collected in M1 (attestation only) — to be confirmed by counsel. |
| NFR-31 | No sale of personal data; no advertising trackers in the authenticated app without consent review. |
| NFR-32 | Self-serve deletion and export before any real-user launch (AUTH-06). |
| NFR-33 | Passwords hashed with a modern memory-hard algorithm; secrets never in the repo; TLS everywhere in deployed environments. |
| NFR-34 | Analytics events never contain exact stakes, free-text bet notes, or assistant message text (see ANALYTICS_EVENT_TAXONOMY). |
| NFR-35 | Per-user authorization enforced server-side on every tracker/sync/assistant endpoint. |

### 7.5 Reliability, quality, content

| ID | Requirement |
|---|---|
| NFR-40 | CI gates: lint, type-check, unit tests, a11y checks, dependency scan. |
| NFR-41 | Calculators and odds maths: ≥ 1 reference-vector test per formula; shared implementation across surfaces. |
| NFR-42 | All user-facing copy follows BRAND_VOICE (no banned claims). |
| NFR-43 | Responsible-gambling footer (21+, helpline 1-800-GAMBLER) on marketing and app surfaces. |
| NFR-44 | Availability targets are defined at M2 with production infrastructure (none claimed in M1). |
| NFR-45 | US English at launch; copy externalised to allow later localisation. |

---

## 8. Success measures (proposals; no baselines exist yet)

- North-star proposal: **Weekly Researching Users** — see `docs/marketing/ANALYTICS_EVENT_TAXONOMY.md`.
- We deliberately **do not** optimise for amount wagered, bet count, or deposit behaviour.

## 9. Open questions

See ROADMAP §"Open questions for the Founder" and COMPLIANCE_OVERVIEW §"Open questions for counsel".
