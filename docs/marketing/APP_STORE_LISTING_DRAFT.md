# OddVex — App Store and Google Play Listing Draft

Last updated: 2026-11-21 · Status: **DRAFT. Not submitted. Submission requires Founder approval (G-04) and counsel review of copy and policy position.**

Reality check before using this draft:
- The mobile app is **built in code and has not been reported as run on a device or simulator** (see `apps/mobile/README.md` and `docs/product/BUILD_STATUS.md`). In code it covers games and odds comparison, the prop board and analyzer, calculators, parlay research, the bet tracker with mock sync, the watchlist, in-app alerts and notifications, OddVex AI, and account settings with in-app deletion, all on **synthetic data**. The community screens (feed, picks, comments, profiles, follows, blocks, reports, leaderboard) are also compiled into the app and appear when the server's `community` switch is turned on, with no new build; it is off. It has no push notifications, no data export, no profit chart or performance breakdowns, and no paywall. No screenshot below can be produced until the app has been run on real hardware. Store submission is planned for **M6**.
- Listing copy below describes the **intended launch feature set**. At submission, remove any feature that is not actually in the shipped build (store metadata must be accurate).
- Character limits and policy references reflect our understanding and **must be re-verified in App Store Connect / Play Console at submission time**.
- No ratings, awards, user counts or testimonials are included, because none exist.

---

## 1. Shared positioning

| Item | Draft |
|---|---|
| What it is | Sports-betting intelligence: odds comparison, prop research, calculators, bet tracking |
| What it is not | Not a sportsbook. Does not accept or place wagers. No real-money gambling in the app |
| Audience | Adults 21+ in the United States |
| Primary category | Sports |
| Secondary category (iOS) | Reference or Utilities (decide at submission) |
| Availability | United States only at launch (Founder decision pending) |
| Price | Free; in-app subscription only if Premium ships (M4) |

## 2. Apple App Store (iOS)

| Field | Limit (verify) | Draft | Chars |
|---|---|---|---|
| App name | 30 | `OddVex: Odds & Prop Research` | 28 |
| Subtitle | 30 | `Compare lines. Track results.` | 29 |
| Promotional text | 170 | `Every line, side by side. See what each price implies, research player props, and keep an honest record of your bets. OddVex does not accept wagers. 21+.` | 153 |
| Keywords | 100 | `sportsbook,moneyline,spread,parlay,calculator,implied,probability,EV,CLV,vig,player,tracker,sports` | 98 |

Alternates to test (after launch, with approval): name `OddVex – Odds Comparison` (24); subtitle `Every line. Smarter view.` (25).

Keyword notes:
- Do not repeat words already in name/subtitle (odds, prop, research, compare, lines, track, results).
- **Do not use competitor, sportsbook, league or team names** as keywords (trademark and review risk).
- Do not use "picks", "locks", "free bets", "winning" (brand-banned).
- No search-volume data has been purchased; validate with an ASO tool before finalising.

### Description (draft)

```
Every Line. A Smarter Perspective.

OddVex is a sports-betting intelligence app. It helps you see the market clearly: compare prices across sportsbooks, understand what each number means, research player props, and keep an accurate record of your own bets.

OddVex is an information tool. It does not accept or place wagers.

COMPARE ODDS
• Moneyline, spread and total prices side by side
• Best available line highlighted for each outcome
• "As of" time on every price, with stale data clearly marked
• American, decimal or implied-probability view

RESEARCH PLAYER PROPS
• Recent results against the current line
• Hit rates shown with sample sizes, never as bare percentages
• Prices compared across sportsbooks

RUN THE NUMBERS
• Implied probability, no-vig, expected value, closing line value and parlay calculators
• Every formula explained

UNDERSTAND PARLAYS
• Combined odds, payout and the break-even rate: how often the parlay must win to break even
• Warnings when legs may be correlated

TRACK YOUR BETS
• Log bets placed elsewhere and settle them
• Net result, ROI and record by sport, sportsbook and market
• Optional sync through authorized partners; OddVex never stores your sportsbook passwords

ASK ODDVEX AI
• Answers drawn from verified OddVex data, with sources and timestamps
• Never invents numbers and does not predict outcomes

BUILT RESPONSIBLY
• No picks, no "locks", no guarantees
• Help resources always available

For adults 21 and over. OddVex provides information only and does not offer real-money gambling. Odds may be delayed or change; always confirm with your sportsbook. Betting involves risk.

Gambling problem? Call 1-800-MY-RESET (1-800-697-3738) or text 800GAM.

Terms: https://oddvex.com/terms
Privacy: https://oddvex.com/privacy
Responsible gambling: https://oddvex.com/responsible-gambling
```

Remove at submission anything not in the shipped build. Props, calculators, parlay, tracker, mock sync and OddVex AI exist in the mobile code today but have not been run on a device; re-check each against the build that is actually submitted, and remove any mention of push alerts (the app has none). If subscriptions ship, add the required subscription terms paragraph (price, period, auto-renewal, how to cancel) per current store rules and counsel.

### "What's New" template

```
• [Change 1 — plain description]
• [Change 2]
• Fixes and performance improvements
```

### Other iOS fields

| Field | Draft / note |
|---|---|
| Support URL | https://oddvex.com/help |
| Marketing URL | https://oddvex.com |
| Privacy Policy URL | https://oddvex.com/privacy (must be final, counsel-approved) |
| Copyright | © [year] Medivh Code (legal entity name to confirm, Q-10) |
| App Review notes | See §5 |
| Sign-in for review | Demo account with representative data (create at M6) |

## 3. Google Play (Android)

| Field | Limit (verify) | Draft | Chars |
|---|---|---|---|
| App title | 30 | `OddVex: Odds & Prop Research` | 28 |
| Short description | 80 | `Compare odds, research props, run the math, track your bets. No wagering. 21+.` | 78 |
| Full description | 4000 | Use the iOS description above (plain text; within limit) | — |

| Other field | Draft / note |
|---|---|
| Category | Sports |
| Tags | Choose from Play's list at submission (sports-related) |
| Contact email / website | Support mailbox to be created (G-06); https://oddvex.com |
| Privacy Policy | https://oddvex.com/privacy |
| Account deletion URL | Web deletion page (to be built, AUTH-06) |
| Data safety form | Derive from `docs/compliance/PRIVACY_AND_DATA.md` at submission |
| Ads declaration | "No ads" unless that changes |
| Target audience | Adults only (18+ is the highest Play age band; app itself gates at 21+) |
| Gambling declarations | Determine at submission whether Play requires any declaration/application for an odds-information app without wagering (ST-01) |

## 4. Screenshot storyboard

Rules: real app UI only; **fictional teams/players/sportsbooks or licensed data**; no real logos; captions pass BRAND_VOICE; small footer "Illustrative data" when fixtures are used; no device frames that imply unsupported devices; provide all required sizes for iPhone, iPad (if supported) and Android phone.

| # | Screen | Caption (headline) | Sub-caption | Shows | Available in mobile build |
|---|---|---|---|---|---|
| 1 | Odds comparison | "Every line, side by side" | "Best available price highlighted" | Grid with best-line markers and "as of" time | No separate odds board on mobile; the Games tab and game detail show best prices. Built in code, not reported as run on a device |
| 2 | Game detail | "Scores and prices together" | "Know how fresh every number is" | Score header, odds by sportsbook, freshness label | Built in code, not reported as run on a device |
| 3 | Implied probability view | "See what the price implies" | "American, decimal or probability" | Format toggle; no-vig row | Built in code, not reported as run on a device (odds format is set in Settings; no-vig consensus is on game detail) |
| 4 | Player prop detail | "Props, backed by history" | "Results against the line, with sample sizes" | Game-log chart; "6 of 10" | Built in code, not reported as run on a device |
| 5 | Calculators | "Run the numbers" | "No-vig, EV, CLV and parlay maths" | EV calculator with formula link | Built in code, not reported as run on a device ("Show the working" instead of a formula link: verify) |
| 6 | Parlay research | "Understand the whole parlay" | "Break-even rate alongside payout" | Break-even rate and correlation warning visible. Do not show or caption a combined probability: the app shows none | Built in code, not reported as run on a device |
| 7 | Bet tracker | "Your record, honestly" | "Net result, ROI and breakdowns" | Summary tiles incl. a negative number (do not show only wins) | Built in code, not reported as run on a device (breakdowns are web-only) |
| 8 | OddVex AI | "Answers with sources" | "From verified data. No invented numbers." | Answer with source + timestamp chips | Built in code, not reported as run on a device |
| 9 | Responsible gambling | "Information, never pressure" | "21+. No picks. No guarantees." | RG resources screen | Not built as a screen: the app shows the responsible-gambling line and helpline in Settings, on the tracker and on the sync panel, and the staking-reminder notice |

Use only screenshots of features present in the submitted build. Launch set (first five positions) to be chosen from what ships.

App preview video (optional, later): 15–25 s; real UI capture; no claims beyond captions above; no depiction of placing a bet.

Feature graphic (Play): logo + tagline "Every Line. A Smarter Perspective." on brand background; no screenshots of real sportsbooks; no prices that could be read as offers.

## 5. App Review notes (draft)

```
OddVex is a sports-betting information and analytics app for adults 21+.

• OddVex does NOT accept, place, or facilitate wagers and has no real-money
  gambling functionality. No deposits, withdrawals or payments to sportsbooks.
• The app displays odds and statistics obtained from [licensed provider name]
  under licence, plus calculators and a personal bet-tracking ledger for bets
  the user has placed elsewhere.
• [If shipped] Sportsbook sync is provided through [vendor], an authorized
  third-party service. OddVex never collects or stores sportsbook credentials.
• [If shipped] OddVex AI answers questions using only OddVex's internal data
  tools; it does not predict outcomes.
• [If applicable] The app contains no links to sportsbooks / contains outbound
  links to state-licensed sportsbooks only, as follows: [...]
• Users must confirm they are 21 or older at signup.
• Account deletion: Settings > Delete account.

Demo account: [email] / [password]
Contact: [name, phone, email]
```

Bracketed items must be completed truthfully at submission.

## 6. Age rating notes

| Store | Note |
|---|---|
| Apple | Answer the age-rating questionnaire accurately, including gambling-related questions. Even without real-money wagering, the app's theme is sports betting; **expect and accept the highest adult rating tier**. Apple revised its rating tiers in 2025 — verify current tiers and questions at submission. Do not attempt to obtain a lower rating. |
| Google Play | Complete the IARC content-rating questionnaire accurately; disclose gambling-related themes. Set target audience to adults only. Expect a mature rating. |
| Both | App enforces 21+ at signup regardless of store rating. User-generated content screens are in the binary behind a server switch (off); whether they must be declared while switched off is a counsel question (`STORE_SUBMISSION_PREP.md` section 3). If the community is on at submission, declare it and describe moderation (report and block in the app, moderation by staff on the web). If the assistant uses an LLM (M4), check current AI-content disclosure requirements. |
| Open (counsel) | Whether the app is treated as "simulated gambling", "gambling information", or neither under each store's definitions; any regional rating consequences (ST-01, ST-02). |

## 7. Privacy label inputs (to be finalised from the real build)

| Data type | Collected (intended at launch) | Linked to user | Used for tracking |
|---|---|---|---|
| Email address | Yes | Yes | No |
| User ID | Yes | Yes | No |
| User content — bet records | Yes | Yes | No |
| Product interaction (analytics) | Yes (if analytics ships) | Yes / pseudonymous | No |
| Diagnostics (crash, performance) | Yes (if monitoring ships) | TBD | No |
| Device ID / push token | Yes (M3) | Yes | No |
| Purchase history | Yes (M4) | Yes | No |
| Precise location | No | — | — |
| Coarse location | TBD (state availability decision) | TBD | No |
| Contacts, photos, health, financial account info, browsing history | No | — | — |

Position: **no tracking** as Apple defines it (no cross-app/third-party advertising identifiers). Any SDK that changes this needs Founder approval (G-13).

## 8. Pre-submission copy checklist

- [ ] Every feature mentioned exists in the submitted build
- [ ] No banned claims (BRAND_VOICE BC-01…BC-14)
- [ ] "Does not accept wagers" and "21+" present in description
- [ ] National Problem Gambling Helpline present: 1-800-MY-RESET (1-800-697-3738), re-verified on the National Council on Problem Gambling's pages (last checked 2026-11-19). Never 1-800-GAMBLER, which is the New Jersey council's line
- [ ] No combined-probability claim for parlays
- [ ] No third-party trademarks in name, subtitle, keywords or screenshots
- [ ] Character counts re-verified in the store consoles
- [ ] Screenshots use licensed or fictional data and match current UI
- [ ] Subscription terms paragraph added if IAP ships
- [ ] Counsel review complete; Founder approval recorded (G-04)
