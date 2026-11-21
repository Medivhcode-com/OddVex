# OddVex — Screen Map

Last updated: 2026-11-21 (status notes, the responsible-gambling line, sections 4 and 5 checked against the code at commit `2b0c7c1`) · Feature IDs reference [MASTER_FEATURE_INVENTORY.md](./MASTER_FEATURE_INVENTORY.md)

Surfaces: **Web app** (Next.js, authenticated, `/app/*`), **Auth** (`/login`, `/signup`), **Marketing site** (Next.js, public), **Mobile app** (Expo React Native), **Admin** (web console at `/app/admin`, administrators only; see section 5).

## Global conventions (apply to every data screen)

| State | Rule |
|---|---|
| **Loading** | Skeletons matching final layout; no layout shift; `aria-busy` on the region. |
| **Empty** | Explain why it's empty and offer one next action. Never show zeros as if they were results. |
| **Stale** | Keep last known data, show "Stale — last updated {time}" badge; exclude stale prices from best-line logic. |
| **Error** | Plain-language message, retry action, no stack traces; partial failures are scoped to the failing module. |
| **Demo data** | While fixtures are in use: persistent "Demo data — synthetic fixtures; teams, players and sportsbooks are fictional". |
| **RG footer** | "21+. OddVex does not take wagers. Gambling problem? Call 1-800-MY-RESET (1-800-697-3738)." (`RESPONSIBLE_GAMBLING_LINE` in `apps/web/src/lib/site.ts`) on the app shell at every width and in the marketing footer. The number is the National Problem Gambling Helpline, checked on 2026-11-19. |
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
| W-08 | `/app/parlay` | Parlay research | Build and understand a parlay | Leg list; add-leg picker (from odds/props); combined odds, payout, break-even rate (no chance that every leg wins is shown); per-leg breakdown; **correlation warning**; "Send to tracker"; "OddVex does not place bets" note | Picker skeleton / "Add at least two legs to see combined odds" / stale leg flagged with "price may have changed" / error loading legs; invalid-leg message | Nav "Parlay"; "Add to parlay" on game/prop screens; tools | M1 |
| W-09 | `/app/tracker` | Bet tracker | Log, settle, review bets | Summary tiles (net P/L, ROI, record, pending); results-over-time chart; breakdown by sport/book/market; bet table (filter/sort); add/edit bet dialog; settle action; sync connections panel (connect mock, status, last synced, disconnect) | Tiles/table skeletons / "No bets yet — Log your first bet or connect a demo sportsbook" / sync "Last synced {time}" + stale connection state / save-failed toast with retry; sync error banner | Nav "Tracker"; dashboard snapshot; parlay "Send to tracker" | M1 |
| W-10 | `/app/assistant` | OddVex AI | Ask questions answered from verified data | Message list; composer; suggested prompts; per-answer source + "as of" chips; AI disclosure; "rule-based, demo data" note (M1); RG footer | Typing indicator / empty: intro + suggested prompts + capability list / answer shows stale chip when source data is stale / "I couldn't reach the data tools — try again"; unsupported-question message | Nav "Assistant"; dashboard quick action | M1 |
| W-11 | `/app/settings` | Settings | Account and preferences | Profile (email); odds format; time zone; responsible-gambling resources; legal links; sign out. Later: notifications (M3), subscription (M4), delete account/export (M2), connected sportsbooks summary | Form skeleton / n/a / n/a / save error inline | Account menu; nav | M1 |

Routes built since this table was written (code at `2b0c7c1`; see `apps/web/src/app/app`): `/app/alerts`, `/app/value` (flag `value_screen`, on), `/app/tracker/analytics` (flag `tracker_analytics`, on), `/app/community` with guidelines, leaderboard, picks, profiles and settings (flag `community`, off; the leaderboard also needs `community_leaderboard`, off), and the admin console (section 5). Not built: subscription and billing.

## 2. Auth

| # | Route | Screen | Purpose | Key components | States | Entry points | MS |
|---|---|---|---|---|---|---|---|
| A-01 | `/login` | Log in | Authenticate | Email, password, submit, link to signup; generic error on bad credentials | Submitting spinner / n/a / n/a / "Email or password is incorrect" (no account enumeration); rate-limit message | Marketing "Log in"; auth guard redirect | M1 |
| A-02 | `/signup` | Sign up | Create account | Email, password with requirements, **21+ attestation checkbox (required)**, Terms/Privacy acceptance, submit | Submitting / n/a / n/a / validation errors; "must confirm you are 21 or older" block; generic message if email already registered | Marketing CTAs; `/login` link | M1 |
| A-03 | (TBD) | Verify email | Confirm address | Status + resend | — | Email link | M2 |
| A-04 | (TBD) | Reset password | Recover access | Request + set-new forms | — | `/login` link | M2 |

## 3. Marketing site (public)

Shared: header (logo, Features, Pricing, Help, Log in, Get started), footer (legal links, RG statement with the National Problem Gambling Helpline, 1-800-MY-RESET (1-800-697-3738), "OddVex does not accept or place wagers", © Medivh Code). Screenshots and examples must show **fictional** data and be labelled illustrative. Mostly static: loading/stale states are not applicable unless noted.

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
| M-14 | `/responsible-gambling` | Responsible gambling | RG resources | Get help now (1-800-MY-RESET (1-800-697-3738), text 800GAM, 988 and 911 for a crisis, the Council's site, the date the facts were checked; 1-800-GAMBLER named once as the New Jersey council's line); warning signs; practical limits; commitments (draft banner) | Static | Footer; app shell; settings | M1 |
| M-15 | `/methodology` | Methodology | Transparency | Formulas (implied probability, no-vig, EV, CLV, parlay); data sourcing and freshness; current synthetic-data statement; assistant grounding rules | Static | Calculators; footer; assistant | M1 |
| M-16 | `/download` | Download | Mobile app | "Mobile apps are in development"; store badges only after store approval (G-04) | Static | Header/footer | M1 (placeholder) |
| M-17 | (system) | 404 / 500 | Recover | Friendly message, links home | — | Any bad URL | M1 |

## 4. Mobile app (Expo React Native)

**Status: built in code; one Android test build exists (`docs/product/BUILD_STATUS.md`); not reported as run on a device or simulator.** The app covers the web app's signed-in loop, not
only games and odds. It passes the type checker, the linter, its Jest suite and a JS bundle export for both
platforms; nobody has looked at these screens on a phone, in a simulator or in Expo Go. Layout, the native tab bar,
modals, keyboard handling, safe areas, Dynamic Type, screen readers and SecureStore on real hardware are unverified.
`apps/mobile/README.md` is the source of truth for what each screen does; `docs/product/BUILD_STATUS.md` records
what was checked. Routes are the files under `apps/mobile/src/app`. The MS column is the milestone the screen was
planned for.

| # | Route | Screen | Purpose | Key components | States | Entry points | MS | Status |
|---|---|---|---|---|---|---|---|---|
| N-01 | `(tabs)/(games)/index` | Games | Browse games/scores | League chips; Live / Upcoming / Final groups; best moneyline per side with the book's name; pull-to-refresh; "Your watchlist" when logged in; notifications bell with unread count; synthetic-data badge | Loading / empty / stale label / error with retry | App launch (default tab) | M1 | Built, not run on a device |
| N-02 | `(tabs)/(games)/event/[id]` | Game detail | Score + odds comparison | Market switcher; one row per sportsbook with price, freshness, hold, "Best" in words; no-vig consensus; Follow toggles; "Track a bet on this game"; "Set an alert" | Loading / "not offered" / stale / not-found, error | Game row; notification | M1 | Built, not run on a device |
| N-03 | (none) | Odds comparison | Compare prices | No separate odds board on mobile: the Games tab and game detail stand in for it. Odds format is set in Settings | — | — | M1 | Not built as its own screen |
| N-04 | `login`, `signup` | Auth | Account access incl. 21+ attestation | Modals above the tabs; name, email, password (10+ characters), "I am 21 or older" switch | Submitting / validation errors / rate-limit message | Any screen that needs an account | M2 | Built, not run on a device |
| N-05 | `(tabs)/(props)/props`, `(tabs)/(props)/player/[id]` | Prop board and analyzer | Research props | League and stat filters; window and split selectors; over rate with "x of n games" and 95% range; game-log bars labelled Over / Under / Push; per-book offers; Follow toggle | As web | Tab bar | M3 | Built, not run on a device |
| N-06 | `(tabs)/(tools)/tools` | Calculators | Betting maths | Converter, no-vig, EV, CLV; "Show the working" | As web | Tab bar | M3 | Built, not run on a device |
| N-07 | `(tabs)/(tools)/parlay` | Parlay research | Build/understand parlay | Legs from current games or custom; combined odds, payout, break-even; correlation warning with "Not shown" | As web | Tools tab | M3 | Built, not run on a device |
| N-08 | `(tabs)/(tracker)/tracker`, `(tabs)/(tracker)/log-bet` | Bet tracker | Log/settle/review | Summary; open and settled bets; settle, settle a parlay by leg, edit, delete; "Settle from final scores"; mock sync; staking-reminder notice | Signed out: invitation to log in. Otherwise as web | Tab bar | M3 | Built, not run on a device. Profit chart and breakdowns are web-only |
| N-09 | `(tabs)/(games)/assistant` | OddVex AI | Ask questions | Chat, example questions, suggestion chips, sources line and disclaimer | As web | Games tab; Settings | M4 | Built, not run on a device |
| N-10 | `(tabs)/(settings)/settings` | Settings | Preferences, RG line, **in-app account deletion** | Account, odds format, notification switches, weekly staking reminder, change password, delete account (typed DELETE) | — | Tab bar | M2 | Built, not run on a device. Data export and the legal pages are web-only |
| N-11 | `(tabs)/(games)/notifications` | Notifications and alerts | Read notifications, manage alerts | Two segments: notifications (mark read, delete, load more) and alert rules (pause, resume, set again, delete, "Check now") | Signed out: invitation to log in | Bell on Games; Settings | M3 | Built, not run on a device. In-app only: no push, no email, no background checks |
| N-13 | `(tabs)/(games)/community/*` | Community | Research discussion | Feed, pick with comments, profile form, other profiles (follow, block, report), guidelines, leaderboard | As web | Games tab link row; notifications | M5 | Built, behind the `community` switch (off); the leaderboard also needs `community_leaderboard`. Moderation is web-only |
| N-12 | `paywall` | Premium | Upgrade | Plan details with renewal disclosure, restore purchases | — | Gated features | M4 | Planned. Not built; pricing and billing need Founder approval |

Mobile-specific requirements, **all unverified until the app runs on a device**: safe areas; Dynamic Type / font
scaling; 44 pt targets; dark and light themes (the app follows the system setting; there is no in-app toggle);
VoiceOver/TalkBack labels on prices (e.g. "Northgate −110 at Book A, best price"). There is no push permission
prompt because the app has no push notifications.

Not built on mobile: push notifications, automatic refresh, offline cache, token refresh, tablet layouts, final icon
and splash art, store configuration. The EAS project and its `preview` and `production` build profiles exist
(`apps/mobile/eas.json`) and the app identifier is `com.oddvex.app`. On an iPhone the App Store's Expo Go cannot open
this SDK 58 project; see `docs/product/PHONE_TEST_GUIDE.md`. Nothing has been published.

## 5. Admin

Built at `2b0c7c1`: a web console for administrators at `/app/admin` (overview), `/app/admin/users` (search, suspend,
lift a suspension, set plan), `/app/admin/flags`, `/app/admin/audit`, `/app/admin/outbox` and `/app/admin/community`
(report queue, behind the `community` switch). The API also has routes to export or delete an account on its owner's
behalf (`POST /v1/admin/users/{user_id}/export` and `/delete`); their web screens are not in `2b0c7c1`. The table
below is the original plan and is kept for its IDs.

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
