# OddVex — Master Feature Inventory

Last updated: 2026-11-15 · IDs match [PRODUCT_REQUIREMENTS.md](./PRODUCT_REQUIREMENTS.md) · Milestones defined in [ROADMAP.md](./ROADMAP.md)

## How to read this table

| Column | Meaning |
|---|---|
| **Tier (proposal)** | `Free` / `Premium` / `Free+limits` / `n/a`. **Proposal only** — no pricing or packaging is approved; Premium does not exist until M4 and needs Founder approval. |
| **MS** | Target milestone M1–M6. |
| **Status** | `Built in M1` = in M1 scope, being built now. `M1 — verify` = assumed M1 scope but not explicitly named in the M1 brief; engineering must confirm at M1 exit. `Planned` = not built. |
| **Dependencies** | What must exist first. "Founder gate" = requires explicit Founder approval (see ROADMAP §Founder-approval gates). |

Important caveats:
- "Built in M1" has **not been verified against code by this document**; reconcile at the M1 exit review.
- Everything built in M1 runs on **synthetic fixtures** with fictional teams, players and sportsbooks.

## A. Home

| ID | Feature | Description | Tier (proposal) | MS | Status | Dependencies |
|---|---|---|---|---|---|---|
| HOME-01 | Dashboard summary | Today's games, notable best-line gaps, tracker snapshot at `/app` | Free | M1 | Built in M1 | Fixtures (DATA-01) |
| HOME-02 | Data-status indicator | "Demo data" label + global freshness | Free | M1 | Built in M1 | DATA-04 |
| HOME-03 | Quick actions | Shortcuts to Odds, Props, Tools, Assistant | Free | M1 | Built in M1 | — |
| HOME-04 | Personalised modules | Modules driven by favorites/watchlists | Free | M2 | Built (watchlist section on the dashboard) | GAME-05, PROP-07 |
| HOME-05 | Movement & alerts feed | Recent line moves and triggered alerts | Free+limits | M3 | Planned | INTL-11; licensed provider |
| HOME-06 | Onboarding checklist | First-run guidance | Free | M2 | Planned | — |

## B. Games & Live Scores

| ID | Feature | Description | Tier (proposal) | MS | Status | Dependencies |
|---|---|---|---|---|---|---|
| GAME-01 | Games list | By sport/league/date with status | Free | M1 | Built in M1 | Fixtures |
| GAME-02 | Live scores | Score, period/clock, "as of" (simulated in M1) | Free | M1 | Built in M1 | Fixtures; real: licensed provider |
| GAME-03 | Game detail | Score, odds snapshot, related props | Free | M1 | Built in M1 | ODDS-01, PROP-01 |
| GAME-04 | Game filters | Sport, league, date, status | Free | M1 | Built in M1 | — |
| GAME-05 | Favorites | Persisted favorite teams/leagues | Free | M2 | Built (teams and games; not leagues) | Persistence; auth |
| GAME-06 | Box score / play-by-play | Detailed in-game and team stats | Free | M2 | Planned | Needs licensed provider |
| GAME-07 | Injuries & lineups | Availability context | Free | M3 | Planned | Needs licensed provider (coverage varies) |
| GAME-08 | Game notifications | Start / final / score alerts | Free | M3 | Built in-app (start and final; no live score alerts, no push) | NOTF-01; store notification policies |
| GAME-09 | Mobile games | List + detail in Expo app | Free | M1 | Built in M1 | MOB-01 |

## C. Odds Comparison

| ID | Feature | Description | Tier (proposal) | MS | Status | Dependencies |
|---|---|---|---|---|---|---|
| ODDS-01 | Comparison grid | Moneyline / spread / total across sportsbooks | Free | M1 | Built in M1 | Fixtures |
| ODDS-02 | Best-line highlight | Best price per outcome, non-colour cue | Free | M1 | Built in M1 | ODDS-01 |
| ODDS-03 | Odds format toggle | American / decimal / implied % | Free | M1 | Built in M1 | Shared odds maths |
| ODDS-04 | Price freshness | Per-price "as of" + stale flag | Free | M1 | Built in M1 | DATA-04 |
| ODDS-05 | Odds filters | Sport, league, market, sportsbook | Free | M1 | Built in M1 | — |
| ODDS-06 | No-vig & hold inline | Fair price and hold % per market | Free | M1 | Built in M1 | INTL-02 |
| ODDS-07 | Line-movement chart | Historical price/line over time | Free+limits | M2 | Planned | DATA-05; licensed provider with history rights |
| ODDS-08 | My sportsbooks | Choose books; state availability | Free | M2 | Planned | Sportsbook-by-state reference data; counsel review |
| ODDS-09 | Outbound sportsbook links | Link out (affiliate or plain) | Free | M3 | Planned | **Founder gate**; affiliate agreements; state affiliate registration review by counsel; ad disclosures |
| ODDS-10 | Alt lines & more markets | Alternates, periods, futures | Premium | M3 | Planned | Provider market coverage |
| ODDS-11 | Mobile odds comparison | Grid adapted for mobile | Free | M1 | Built in M1 | MOB-01 |
| ODDS-12 | Price / line alerts | Threshold alerts | Free+limits | M3 | Built in-app (no push) | INTL-11, NOTF-01 |

## D. Prop Analyzer

| ID | Feature | Description | Tier (proposal) | MS | Status | Dependencies |
|---|---|---|---|---|---|---|
| PROP-01 | Prop list | Props by game/player/market across books | Free | M1 | Built in M1 | Fixtures |
| PROP-02 | Player prop detail | Game log vs. line; hit rate last N | Free | M1 | Built in M1 | Fixtures |
| PROP-03 | Best prop line/price | Across sportsbooks | Free | M1 | Built in M1 | PROP-01 |
| PROP-04 | Splits | Home/away, opponent, rest | Premium | M2 | Planned | Provider stats depth |
| PROP-05 | Sample-size labelling | n/N display; "historical, not predictive" | Free | M1 | Built in M1 | — |
| PROP-06 | Model projections | Projection + uncertainty + methodology | Premium | M4 | Planned | Real historical data; model validation; backtesting (INTL-10); claims review |
| PROP-07 | Prop watchlist | Saved players/props | Free+limits | M2 | Built (players; not individual props) | Persistence |
| PROP-08 | Prop alerts | Line/price change alerts | Premium | M3 | Planned | INTL-11, NOTF-01 |
| PROP-09 | Mobile prop analyzer | Props in Expo app | Free | M3 | Built in code, never run on a device (prop board and analyzer) | MOB-01 |
| PROP-10 | Matchup context | Opponent/positional context | Premium | M3 | Planned | Provider stats depth |

## E. Betting Intelligence

| ID | Feature | Description | Tier (proposal) | MS | Status | Dependencies |
|---|---|---|---|---|---|---|
| INTL-01 | Implied probability calculator | Odds ⇄ probability, format conversion | Free | M1 | Built in M1 | Shared maths module |
| INTL-02 | No-vig calculator | Remove margin from 2+ outcome market | Free | M1 | Built in M1 | Shared maths module |
| INTL-03 | EV calculator | EV from odds, stake, user probability | Free | M1 | Built in M1 | Shared maths module |
| INTL-04 | CLV calculator | Bet price vs. closing price | Free | M1 | Built in M1 | Shared maths module |
| INTL-05 | Parlay calculator | Combined odds/payout | Free | M1 | Built in M1 | Shared maths module |
| INTL-06 | Formula transparency | Formula on each tool + `/methodology` | Free | M1 | Built in M1 | MKT-03 |
| INTL-07 | Hedge & arbitrage calculators | Additional tools | Free | M2 | Planned | — |
| INTL-08 | Bankroll / staking calculator | e.g. fractional staking | Free | M3 | Planned | RG review of framing before build |
| INTL-09 | Market discrepancy / +EV screen | Market-wide scan vs. reference price | Premium | M4 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | Licensed provider; reference-price methodology; claims review |
| INTL-10 | Backtesting | Test projections/strategies on history | Premium | M4 | Planned | Historical data licence; DATA-05 |
| INTL-11 | Alerts engine | Rules, evaluation, delivery | Free+limits | M3 | Built (evaluated on app open or by script; no background worker) | Real-time provider; NOTF-01 |
| INTL-12 | Mobile calculators | Tools in Expo app | Free | M3 | Built in code, never run on a device (converter, no-vig, EV, CLV) | MOB-01 |

## F. Bet Tracker

| ID | Feature | Description | Tier (proposal) | MS | Status | Dependencies |
|---|---|---|---|---|---|---|
| TRKR-01 | Manual bet entry | Book, market, selection, odds, stake, date | Free | M1 | Built in M1 | AUTH-01 |
| TRKR-02 | Manual settlement | Win/loss/push/void/cash-out | Free | M1 | Built in M1 | TRKR-01 |
| TRKR-03 | Performance summary | P/L, ROI, record; by sport/book/market | Free | M1 | Built in M1 | TRKR-02 |
| TRKR-04 | Bet list management | Filter, sort, edit, delete | Free | M1 | Built (edit and delete in UI; filter and sort in API only) | — |
| TRKR-05 | CLV per bet | Manual closing odds in M1 | Free | M1 | Built in M1 (average shown in UI; per-bet value in API only) | INTL-04 |
| TRKR-06 | Auto settlement & auto closing odds | From results/odds feed | Free | M2 | Settlement built on synthetic scores; auto closing odds Planned | Needs licensed provider; DATA-05 |
| TRKR-07 | CSV export / import | Export M2; import M3 | Free | M2/M3 | Planned | — |
| TRKR-08 | Results-over-time chart | Cumulative net result | Free | M1 | Built in M1 | TRKR-03 |
| TRKR-09 | Tags & notes | User annotations | Free | M2 | Planned | — |
| TRKR-10 | Spending-awareness insights | Neutral summaries; optional reminders | Free (never paywalled) | M3 | Planned | RG policy review |
| TRKR-11 | Mobile tracker | Tracker in Expo app | Free | M3 | Built in code, never run on a device (log, settle, edit, delete, settle from final scores, mock sync; profit chart and breakdowns are web-only) | MOB-02 |
| TRKR-12 | Multi-leg bets | Parlays with legs in tracker | Free | M1 | Built in M1 | TRKR-01 |
| TRKR-13 | Advanced analytics | Deeper breakdowns, custom date ranges | Premium | M4 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | PREM-01 |

## G. Sportsbook Sync

| ID | Feature | Description | Tier (proposal) | MS | Status | Dependencies |
|---|---|---|---|---|---|---|
| SYNC-01 | Sync adapter interface | Provider-agnostic contract | n/a | M1 | Built in M1 | — |
| SYNC-02 | Mock sync adapter | Fictional sportsbook, synthetic bets | Free | M1 | Built in M1 | SYNC-01, fixtures |
| SYNC-03 | Connection management | Status, last synced, disconnect | Free | M1 | Built in M1 | SYNC-02 |
| SYNC-04 | De-duplication | Synced vs. manual bet matching | Free | M1 | Built in M1 (re-import de-duplication only; no matching against manual bets) | TRKR-01 |
| SYNC-05 | Real vendor integration | Authorized third-party sync vendor | Free+limits or Premium (undecided) | M3 | Planned | **Founder gate** (paid vendor); vendor due diligence; counsel review of sportsbook ToS exposure |
| SYNC-06 | No credential storage | Vendor-hosted link; tokens only | n/a | M1 design / M3 | Principle (enforced with SYNC-05) | Vendor capability |
| SYNC-07 | Scheduled re-sync | Background sync, retry, error states | as SYNC-05 | M3 | Planned | SYNC-05; job runner |
| SYNC-08 | Sync consent & disclosures | Clear consent before connecting | Free | M1 (mock) / M3 | Built in M1 (mock-only notice; real consent flow Planned) | Counsel-reviewed copy for real vendor |
| SYNC-09 | Delete synced data on disconnect | User choice to purge | Free | M1 | Built in M1 (UI always purges; keep-data option in API only) | AUTH-06 |

## H. OddVex AI

| ID | Feature | Description | Tier (proposal) | MS | Status | Dependencies |
|---|---|---|---|---|---|---|
| AI-01 | Assistant UI | Chat at `/app/assistant` | Free | M1 | Built in M1 | AUTH-01 |
| AI-02 | Rule-based router | Intent → internal tools | Free | M1 | Built in M1 | Internal data tools |
| AI-03 | Grounded answers | Numbers only from tools; source + "as of" | Free | M1 | Built in M1 | DATA-04 |
| AI-04 | Refusal behaviour | No guarantees/picks; honest "no data" | Free | M1 | Built in M1 | — |
| AI-05 | AI disclosure + RG footer | Automated-assistant label | Free | M1 | Built in M1 | — |
| AI-06 | Suggested prompts | Starter questions | Free | M1 | Built in M1 | — |
| AI-07 | LLM-backed assistant | Tool calling under same grounding contract | Free+limits / Premium | M4 | Planned | **Founder gate** (paid API); provider data-processing terms; AI-08 |
| AI-08 | Evaluation suite | Numeric fidelity, refusals, injection tests | n/a | M4 | Planned | AI-07 (M1 has rule unit tests only) |
| AI-09 | Conversation history | Persist + user deletion | Free | M4 | Planned | Retention policy |
| AI-10 | Answer feedback | Helpful / not / report | Free | M2 | Planned | — |
| AI-11 | Usage limits by tier | Quotas | Free+limits | M4 | Planned | PREM-01 |
| AI-12 | Mobile assistant | Assistant in Expo app | Free+limits | M4 | Planned | MOB-02 |

## I. Parlay Research

| ID | Feature | Description | Tier (proposal) | MS | Status | Dependencies |
|---|---|---|---|---|---|---|
| PRLY-01 | Parlay builder | Add legs; combined odds/payout | Free | M1 | Built in M1 | INTL-05 |
| PRLY-02 | Combined probability | Implied probability + per-leg breakdown | Free | M1 | Built in M1 | INTL-01 |
| PRLY-03 | Correlation warning | Rule-based same-game/related-leg warning | Free | M1 | Built in M1 (same-event rule only) | Leg metadata (game/player IDs) |
| PRLY-04 | Parlay price comparison | Across sportsbooks | Premium | M3 | Planned | Provider coverage of parlay/SGP pricing (may not be available) |
| PRLY-05 | Send to tracker / save drafts | Tracker hand-off (M1?), drafts (M2) | Free | M1/M2 | Planned | TRKR-12 |
| PRLY-06 | Quantified correlation | Model-based estimates | Premium | M4 | Planned | Historical data; model validation |
| PRLY-07 | Mobile parlay research | In Expo app | Free | M3 | Built in code, never run on a device (with the correlation warning) | MOB-01 |

## J. Community

| ID | Feature | Description | Tier (proposal) | MS | Status | Dependencies |
|---|---|---|---|---|---|---|
| COMM-01 | Profiles | Pseudonymous handle, avatar | Free | M5 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | UGC policy |
| COMM-02 | Discussions | Threads on games/props | Free | M5 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | COMM-05, COMM-06 |
| COMM-03 | Share tracked bets | "Synced" vs. "self-reported" badge | Free | M5 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | TRKR, SYNC-05 |
| COMM-04 | Follow & feed | Social graph | Free | M5 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | COMM-01 |
| COMM-05 | Report / block / mute | User safety controls | Free | M5 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | Store UGC requirements |
| COMM-06 | Moderation | Queue, actions, appeals | n/a | M5 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | ADMN-05; staffing; counsel |
| COMM-07 | Leaderboards | Only if RG review approves | Free | M5 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | RG review; **Founder decision** |
| COMM-08 | Community guidelines | No pick-selling / guaranteed-win claims | n/a | M5 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | Counsel review |

## K. Premium

| ID | Feature | Description | Tier (proposal) | MS | Status | Dependencies |
|---|---|---|---|---|---|---|
| PREM-01 | Plans & entitlements | Server-side entitlement checks | n/a | M4 | Planned | **Founder gate** (pricing) |
| PREM-02 | Web checkout | Payment processor integration | n/a | M4 | Planned | **Founder gate**; processor acceptance of the business category |
| PREM-03 | In-app purchase | iOS / Android billing | n/a | M4 (ships M6) | Planned | Store accounts; store billing rules |
| PREM-04 | Paywall & upgrade surfaces | Honest, non-deceptive | n/a | M4 | Planned | Auto-renewal disclosure review |
| PREM-05 | Subscription management | Renewal disclosure, cancel, restore | n/a | M4 | Planned | Counsel review (ROSCA / state ARLs) |
| PREM-06 | Trials / promotions | Proposal only | n/a | M4 | Planned | **Founder gate**; counsel |
| PREM-07 | Billing emails | Receipts, renewal reminders | n/a | M4 | Planned | Transactional email (**Founder gate**) |

## L. Admin

| ID | Feature | Description | Tier (proposal) | MS | Status | Dependencies |
|---|---|---|---|---|---|---|
| ADMN-01 | Admin overview endpoint | Role-gated aggregates + health | n/a | M1 | Built in M1 | AUTH-07 |
| ADMN-02 | Admin console UI | Internal web console | n/a | M5 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | ADMN-07 |
| ADMN-03 | User management | Lookup, suspend, deletion/export requests | n/a | M5 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | ADMN-07 |
| ADMN-04 | Data health monitor | Provider status and freshness | n/a | M2 basic / M5 | Planned | DATA-03 |
| ADMN-05 | Moderation queue | For Community | n/a | M5 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | COMM-06 |
| ADMN-06 | Feature flags | Remote config / kill switches | n/a | M3 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | — |
| ADMN-07 | Admin audit log | Immutable record of admin actions | n/a | M2 | Planned | Must precede any admin write action |
| ADMN-08 | Subscription support tools | Entitlement lookup/adjust | n/a | M5 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | PREM-01 |
| ADMN-09 | Assistant quality review | Privacy-preserving sampling | n/a | M4 | Planned | AI-07; privacy review |

## Cross-cutting: Accounts, Settings, Notifications, Data, Marketing, Mobile

| ID | Feature | Description | Tier (proposal) | MS | Status | Dependencies |
|---|---|---|---|---|---|---|
| AUTH-01 | Email/password auth | Signup, login | Free | M1 | Built in M1 | — |
| AUTH-02 | 21+ attestation & legal acceptance | Recorded with timestamp/version | Free | M1 | Built in M1 (attestation timestamp; no legal-version record) | Draft legal pages; counsel to confirm adequacy |
| AUTH-03 | Sessions & logout | Session lifecycle | Free | M1 | Built in M1 | — |
| AUTH-04 | Email verification & password reset | Via transactional email | Free | M2 | Built in code (see BUILD_STATUS; community and leaderboard flags off by default; no billing, no real email) | **Founder gate** (real customer email, paid email service) |
| AUTH-05 | MFA / passkeys / social login | Stronger auth options | Free | M3 | Planned | — |
| AUTH-06 | Account deletion & data export | Self-serve | Free | M1 / M2 | Built | Required before any real user; store account-deletion rules |
| AUTH-07 | RBAC | `user`, `admin` roles | n/a | M1 | Built in M1 | — |
| SET-01 | Settings | Profile, odds format, time zone | Free | M1 | Built in M1 | — |
| SET-02 | Notification preferences | Per-channel, per-type | Free | M3 | Built per type, in-app channel only | NOTF-01/02 |
| SET-03 | RG resources & tools | Links (M1); reminders/time-outs (M3) | Free (never paywalled) | M1/M3 | Built in M1 (links) / Planned | RG policy |
| NOTF-01 | Push notifications | APNs/FCM via Expo | Free | M3 | Planned | Store notification policies; consent |
| NOTF-02 | Email notifications | Digest/alerts | Free | M3 | Planned | **Founder gate** (real email); CAN-SPAM review |
| DATA-01 | Synthetic fixtures | Fictional teams/players/sportsbooks | n/a | M1 | Built in M1 | — |
| DATA-02 | Provider abstraction | Swap fixtures for a real feed | n/a | M1 | Built in M1 | — |
| DATA-03 | Licensed provider integration | Real odds/scores/stats | n/a | M2 | Planned | **Founder gate** (paid data licence); licence terms review |
| DATA-04 | Freshness & provenance metadata | `last_updated`, `is_stale`, `provider`, `fetched_at`, `data_mode` (ADR-0002) | n/a | M1 | Built in M1 | — |
| DATA-05 | Historical odds store | For movement, CLV, backtests | n/a | M2 | Planned | Licence must permit storage/history |
| MKT-01 | Marketing website | Pages listed in SCREEN_MAP | Free | M1 | Built in M1 | Not deployed publicly without Founder approval |
| MKT-02 | Legal pages (draft) | Privacy, Terms, Responsible Gambling | Free | M1 | Built in M1 (draft copy) | Counsel sign-off before launch |
| MKT-03 | Methodology page | Formulas and data notes | Free | M1 | Built in M1 | — |
| MKT-04 | Waitlist capture | Email collection | Free | M2 | Planned | **Founder gate** (real email collection); privacy notice |
| MKT-05 | Programmatic SEO pages | Game/market/tool landing pages | Free | M2+ | Planned | Licensed provider with display/SEO rights |
| MKT-06 | Blog | Educational content | Free | M1 shell / M2 content | Built in M1 (shell) | Editorial review per BRAND_VOICE |
| MOB-01 | Mobile app shell | Expo app, nav, tokens | Free | M1 | Built in M1 | — |
| MOB-02 | Mobile auth & account | Login, settings, deletion in-app | Free | M2 | Built in code, never run on a device (log in, create account with 21+ confirmation, change password, in-app deletion; SecureStore on real hardware unverified) | AUTH-06 |
| MOB-03 | Store submission | App Store / Google Play | n/a | M6 | Planned | **Founder gate**; LAUNCH_READINESS_CHECKLIST |
| PLAT-01 | CI pipeline | Lint, types, tests, scans | n/a | M1 | Built in M1 | — |
| PLAT-02 | Design system | Shared tokens/components | n/a | M1 | Built in M1 | — |
| PLAT-03 | Production infrastructure | Hosting, DB, monitoring, backups | n/a | M2 | Planned | **Founder gate** (paid infra, production deploy) |
| PLAT-04 | Product analytics | Event taxonomy implementation | n/a | M2 | Planned | Vendor choice (**Founder gate** if paid); consent review |

## Summary counts

Counts are intentionally not hard-coded here; derive them from the tables when needed so this document does not drift.
