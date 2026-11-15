# OddVex — Screen Map

Last updated: 2026-11-15 · Feature IDs reference [MASTER_FEATURE_INVENTORY.md](./MASTER_FEATURE_INVENTORY.md)

Surfaces: **Web app** (Next.js, authenticated, `/app/*`), **Auth** (`/login`, `/signup`), **Marketing site** (Next.js, public), **Mobile app** (Expo React Native), **Admin** (endpoint only in M1; console planned M5).

## Global conventions (apply to every data screen)

| State | Rule |
|---|---|
| **Loading** | Skeletons matching final layout; no layout shift; `aria-busy` on the region. |
| **Empty** | Explain why it's empty and offer one next action. Never show zeros as if they were results. |
| **Stale** | Keep last known data, show "Stale — last updated {time}" badge; exclude stale prices from best-line logic. |
| **Error** | Plain-language message, retry action, no stack traces; partial failures are scoped to the failing module. |
| **Demo data** | While fixtures are in use: persistent "Demo data — synthetic fixtures; teams, players and sportsbooks are fictional". |
| **RG footer** | "21+. OddVex does not accept wagers. Gambling problem? Call 1-800-GAMBLER." on app shell and marketing footer. |
| **Auth guard** | `/app/*` requires a session; unauthenticated users go to `/login?next=…`. |

MS column: milestone in which the screen first ships. Screens marked M1 are in build; others are planned.

---

## 1. Web app (authenticated)

App shell: left nav (desktop) / bottom or drawer nav (narrow), top bar with search placeholder, data-status indicator, account menu.

| # | Route | Screen | Purpose | Key components | States (loading / empty / stale / error) | Entry points | MS |
|---|---|---|---|---|---|---|---|
| W-01 | `/app` | Dashboard | At-a-glance start | Today's games module; best-line gaps module; tracker snapshot; quick actions; data-status banner | Per-module skeletons / "No games today", "No bets logged yet — Log a bet" / per-module stale badge / per-module error card with retry | Post-login default; logo; nav "Home" | M1 |
| W-02 | `/app/games` | Games & live scores | Browse games by sport/date | Sport/league tabs; date picker; status filter; game cards (teams, time/score, period, best ML snapshot) | Card skeletons / "No games for this date" + jump to next date with games / stale badge on live scores / error with retry | Nav "Games"; dashboard module | M1 |
| W-03 | `/app/games/[id]` | Game detail | One game: score, odds, props | Score header; odds table (ML/spread/total × books); related props list; "Compare all odds" and "Add to parlay" actions | Header + table skeletons / "Odds not yet posted" , "No props for this game" / stale badge per block / not-found (bad id) and fetch-error variants | Game card; odds grid row; assistant answer link | M1 |
| W-04 | `/app/odds` | Odds comparison | Compare prices across sportsbooks | Filters (sport, league, market, books); comparison grid with sticky outcome column; best-line highlight; format toggle; no-vig/hold row; per-price timestamp | Grid skeleton / "No markets match these filters — Clear filters" / stale cells dimmed + badge / error with retry; missing market cell "—" (not offered) | Nav "Odds"; dashboard; game detail; marketing CTA after signup | M1 |
| W-05 | `/app/props` | Prop analyzer (list) | Find props to research | Filters (game, player search, market); prop rows (player, market, line, best over/under price, recent hit rate n/N) | Row skeletons / "No props match" / stale badge / error with retry | Nav "Props"; game detail | M1 |
| W-06 | `/app/props/[playerId]` | Player prop detail | Research one player's props | Player header (fictional in M1); market selector; line-vs-results chart with table alternative; last-N game log; hit rate n/N; prices across books; "historical, not predictive" note; "Add to parlay" | Chart/table skeletons / "Limited sample" or "No game history" / stale badge / not-found and error variants | Prop row; game detail; assistant link | M1 |
| W-07 | `/app/tools` | Calculators | Run betting maths | Tabs or cards: Implied probability, No-vig, EV, CLV, Parlay; inputs with validation; result panel; "How this is calculated" disclosure linking `/methodology` | Instant (client-side), no remote loading / initial state shows example placeholders, not results / n/a (no remote data) / inline input errors; never NaN | Nav "Tools"; odds grid "Open in calculator"; marketing | M1 |
| W-08 | `/app/parlay` | Parlay research | Build and understand a parlay | Leg list; add-leg picker (from odds/props); combined odds, payout, implied probability; per-leg breakdown; **correlation warning**; "Send to tracker"; "OddVex does not place bets" note | Picker skeleton / "Add at least two legs to see combined odds" / stale leg flagged with "price may have changed" / error loading legs; invalid-leg message | Nav "Parlay"; "Add to parlay" on game/prop screens; tools | M1 |
| W-09 | `/app/tracker` | Bet tracker | Log, settle, review bets | Summary tiles (net P/L, ROI, record, pending); results-over-time chart; breakdown by sport/book/market; bet table (filter/sort); add/edit bet dialog; settle action; sync connections panel (connect mock, status, last synced, disconnect) | Tiles/table skeletons / "No bets yet — Log your first bet or connect a demo sportsbook" / sync "Last synced {time}" + stale connection state / save-failed toast with retry; sync error banner | Nav "Tracker"; dashboard snapshot; parlay "Send to tracker" | M1 |
| W-10 | `/app/assistant` | OddVex AI | Ask questions answered from verified data | Message list; composer; suggested prompts; per-answer source + "as of" chips; AI disclosure; "rule-based, demo data" note (M1); RG footer | Typing indicator / empty: intro + suggested prompts + capability list / answer shows stale chip when source data is stale / "I couldn't reach the data tools — try again"; unsupported-question message | Nav "Assistant"; dashboard quick action | M1 |
| W-11 | `/app/settings` | Settings | Account and preferences | Profile (email); odds format; time zone; responsible-gambling resources; legal links; sign out. Later: notifications (M3), subscription (M4), delete account/export (M2), connected sportsbooks summary | Form skeleton / n/a / n/a / save error inline | Account menu; nav | M1 |

Planned web-app additions (no routes committed yet): watchlists (M2), alerts centre (M3), subscription/billing (M4), community (M5).

## 2. Auth

| # | Route | Screen | Purpose | Key components | States | Entry points | MS |
|---|---|---|---|---|---|---|---|
| A-01 | `/login` | Log in | Authenticate | Email, password, submit, link to signup; generic error on bad credentials | Submitting spinner / n/a / n/a / "Email or password is incorrect" (no account enumeration); rate-limit message | Marketing "Log in"; auth guard redirect | M1 |
| A-02 | `/signup` | Sign up | Create account | Email, password with requirements, **21+ attestation checkbox (required)**, Terms/Privacy acceptance, submit | Submitting / n/a / n/a / validation errors; "must confirm you are 21 or older" block; generic message if email already registered | Marketing CTAs; `/login` link | M1 |
| A-03 | (TBD) | Verify email | Confirm address | Status + resend | — | Email link | M2 |
| A-04 | (TBD) | Reset password | Recover access | Request + set-new forms | — | `/login` link | M2 |

## 3. Marketing site (public)

Shared: header (logo, Features, Pricing, Help, Log in, Get started), footer (legal links, RG statement with 1-800-GAMBLER, "OddVex does not accept or place wagers", © Medivh Code). Screenshots and examples must show **fictional** data and be labelled illustrative. Mostly static: loading/stale states are not applicable unless noted.

| # | Route | Page | Purpose | Key components | States / notes | Entry points | MS |
|---|---|---|---|---|---|---|---|
| M-01 | `/` | Home | Explain the product; drive signup | Hero with tagline; product pillars; illustrative UI; "not a sportsbook" statement; CTA | Static | Direct, search, links | M1 |
| M-02 | `/features` | Features overview | Summarise all areas | Feature sections with links to detail pages; "available now" vs. "planned" labelling | Static; planned features must be labelled as planned | Header nav | M1 |
| M-03 | `/odds-comparison` | Odds comparison | Explain feature / SEO | How it works; best-line illustration; freshness explanation; CTA | Static | Features; search | M1 |
| M-04 | `/player-props` | Prop analyzer | Explain feature / SEO | Game-log-vs-line illustration; sample-size note; CTA | Static | Features; search | M1 |
| M-05 | `/bet-tracking` | Bet tracker & sync | Explain feature / SEO | Tracker illustration; sync explained as "via authorized partners — demo only today" | Static | Features; search | M1 |
| M-06 | `/ai` | OddVex AI | Explain assistant | Grounding promise ("answers from verified data, never invents numbers"); limits; current rule-based status | Static | Features | M1 |
| M-07 | `/pricing` | Pricing | Set expectations | Free plan description; "Premium is not available yet"; no unapproved prices | Static; no checkout | Header nav | M1 |
| M-08 | `/about` | About | Company and principles | Mission; principles; Medivh Code attribution | Static | Footer | M1 |
| M-09 | `/blog` | Blog index (+ posts) | Education / SEO | Post list; categories | Empty: "Articles coming soon" | Header/footer | M1 (shell) |
| M-10 | `/contact` | Contact | Reach the team | Contact options. A working form that sends email requires Founder approval (G-06) | Form: submitting / success / error (when enabled) | Footer; help | M1 (static) |
| M-11 | `/help` | Help centre | Self-serve answers | FAQ groups: account, data, calculators, tracker, sync, AI, responsible gambling | Static; search later | Header/footer; app | M1 |
| M-12 | `/privacy` | Privacy Policy | Legal | Draft policy, version/date, "draft pending legal review" until signed off | Static | Footer; signup | M1 (draft) |
| M-13 | `/terms` | Terms of Service | Legal | Draft terms incl. 21+, informational-only, no wagering | Static | Footer; signup | M1 (draft) |
| M-14 | `/responsible-gambling` | Responsible gambling | RG resources | Commitments; warning signs; 1-800-GAMBLER; links to support resources; how OddVex features support awareness | Static | Footer; app shell; settings | M1 |
| M-15 | `/methodology` | Methodology | Transparency | Formulas (implied probability, no-vig, EV, CLV, parlay); data sourcing and freshness; current synthetic-data statement; assistant grounding rules | Static | Calculators; footer; assistant | M1 |
| M-16 | `/download` | Download | Mobile app | "Mobile apps are in development"; store badges only after store approval (G-04) | Static | Header/footer | M1 (placeholder) |
| M-17 | (system) | 404 / 500 | Recover | Friendly message, links home | — | Any bad URL | M1 |

## 4. Mobile app (Expo React Native)

M1 ships the **first slice only: games + odds.** Everything else is planned. Route names follow Expo Router conventions and are proposals for engineering to confirm.

| # | Route (proposed) | Screen | Purpose | Key components | States | Entry points | MS |
|---|---|---|---|---|---|---|---|
| N-01 | `(tabs)/games` | Games | Browse games/scores | Sport chips; date strip; virtualised game list; pull-to-refresh; demo-data banner | Skeleton rows / "No games for this date" / stale badge + last updated / error with retry; offline notice | App launch (default tab) | M1 |
| N-02 | `games/[id]` | Game detail | Score + odds snapshot | Score header; odds by sportsbook; link to full comparison | Skeleton / "Odds not yet posted" / stale badge / not-found, error | Game row | M1 |
| N-03 | `(tabs)/odds` | Odds comparison | Compare prices | Market segmented control; game list with horizontally scrolling book prices; best-line marker; format toggle | Skeleton / "No markets" / stale cells marked / error with retry | Tab bar; game detail | M1 |
| N-04 | `(auth)/login`, `(auth)/signup` | Auth | Account access incl. 21+ attestation | Same fields as web | As web | Launch (when required) | M2 |
| N-05 | `(tabs)/props`, `props/[playerId]` | Prop analyzer | Research props | As web, mobile layout | As web | Tab bar; game detail | M3 |
| N-06 | `tools` | Calculators | Betting maths | Calculator cards | As web | Tab/More | M3 |
| N-07 | `parlay` | Parlay research | Build/understand parlay | As web incl. correlation warning | As web | Add-to-parlay actions | M3 |
| N-08 | `(tabs)/tracker` | Bet tracker | Log/settle/review | As web | As web | Tab bar | M3 |
| N-09 | `assistant` | OddVex AI | Ask questions | As web | As web | Tab/More | M4 |
| N-10 | `settings` | Settings | Preferences, RG resources, legal, **in-app account deletion** | List settings | — | Profile/More | M2 |
| N-11 | `alerts` | Alerts centre | Manage alerts | Alert rules, history, push permission primer | — | Tab/More; push tap | M3 |
| N-12 | `paywall` | Premium | Upgrade | Plan details with renewal disclosure, restore purchases | — | Gated features | M4 |

Mobile-specific requirements: safe areas; Dynamic Type / font scaling; 44 pt targets; dark and light themes; VoiceOver/TalkBack labels on prices (e.g. "Northgate −110 at Book A, best price"); no push permission prompt until alerts exist (M3).

## 5. Admin

| # | Route / endpoint | Screen | Purpose | Key components | States | Entry points | MS |
|---|---|---|---|---|---|---|---|
| D-01 | API: admin overview endpoint (exact path owned by engineering) | — (no UI) | Basic aggregates and health for operators | JSON: aggregate counts, data-source status, build info; **no per-user personal data** | 401 unauthenticated / 403 non-admin / 200 | Authenticated admin API client | M1 |
| D-02 | `/admin` (proposed) | Overview | Operational snapshot | Health tiles, data freshness, recent errors | Standard | Admin login | M5 |
| D-03 | `/admin/users` | Users | Lookup, suspend, deletion/export requests | Search, user detail, action dialogs with reason capture | Standard; every action audit-logged | Admin nav | M5 |
| D-04 | `/admin/data` | Data health | Provider status & freshness | Per-feed last update, error rates | Standard | Admin nav | M2 (basic) / M5 |
| D-05 | `/admin/moderation` | Moderation | Review reported content | Queue, context, actions, appeal notes | Standard | Admin nav | M5 |
| D-06 | `/admin/flags` | Feature flags | Toggle features/kill switches | Flag list, change history | Standard | Admin nav | M3 |
| D-07 | `/admin/audit` | Audit log | Review admin actions | Filterable immutable log | Standard | Admin nav | M2 (data) / M5 (UI) |
| D-08 | `/admin/subscriptions` | Subscriptions | Support entitlements | Lookup, status, adjustments | Standard | Admin nav | M5 |

## 6. Navigation summary

```
Marketing (/ …) ──CTA──▶ /signup ──▶ /app (dashboard)
                └─────▶ /login  ──▶ /app
/app ─▶ /app/games ─▶ /app/games/[id] ─▶ /app/odds | /app/props/[playerId] | /app/parlay
/app ─▶ /app/odds ─▶ /app/tools (prefilled) | /app/parlay
/app ─▶ /app/props ─▶ /app/props/[playerId] ─▶ /app/parlay
/app/parlay ─▶ /app/tracker (send to tracker)
/app ─▶ /app/assistant ─▶ deep links to games / odds / props / tracker
/app/settings ─▶ /responsible-gambling | /privacy | /terms | /help
```
