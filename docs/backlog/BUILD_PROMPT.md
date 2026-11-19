<!-- Supplied by the Founder on 2026-11-19 and saved verbatim. The process and the six hard rules in this file
     are binding for every backlog item. The item list itself is maintained in feature-backlog.md. -->

# OddVex: add the 50-idea feature backlog to the existing application

You are working in the existing OddVex repository. Add the 44 build items below to the application that is already there: the shared backend and API, the web app, and the mobile app wherever a matching surface exists. The 44 build items cover 50 product ideas; six overlapping pairs are merged.

This is many sessions of work. Build one item at a time, in ID order, and leave the repository green after each one. A later session resumes from `docs/backlog/feature-backlog.md` and the tracker.

## The product

OddVex is a sports-betting intelligence platform for US adults 21+. It is not a sportsbook. People use it to research and track bets they place elsewhere. Leagues: NFL, NBA, MLB, NHL, soccer. There is a free tier and a planned Premium subscription with no price set.

Already built. Extend these; do not rebuild them:

- Odds comparison with best price per outcome and stale-price flags
- Line movement history
- Player prop research: lines, best prices, hit rates with confidence intervals, game logs, splits
- A value screen comparing each book with the no-vig consensus of the others
- Calculators: expected value, no-vig, parlay, closing line value (CLV)
- Bet tracker with auto-settlement, ROI analytics and sportsbook sync
- Watchlist, price and line-move alerts, in-app notifications
- A rule-based assistant that answers from the app's own data and math
- Community features (built, switched off)
- Admin tools, feature flags, staking-limit reminders

## Hard rules

Every pull request is checked against all six.

1. **OddVex stays out of the wager.** No code places, pre-fills, routes or submits a bet, and no code holds or moves user money. A link to a sportsbook goes to its home or event page only, and only when the `outbound_links` flag is on (default off).
2. **Honest copy.** Every estimate shows its sample size or uncertainty and its as-of time. The copy guard (P0.6) fails the build on: lock, guaranteed, can't lose, risk-free, sure thing, win either way.
3. **Every number has a source.** A displayed price, probability or projection comes from a deterministic, named, versioned calculation with tests. Language-model text only quotes numbers a calculation produced. When inputs are missing or a match is uncertain, the interface says it cannot price the item.
4. **Responsible gambling first.** Surfaces reward checking, tracking and planning, never placing bets. Every opportunity surface and every notification channel calls the suppression hook (P0.6) before showing anything, so Quiet Mode and Plan Mode silence them everywhere.
5. **Licensed data only.** New data arrives through a provider interface backed by a licensed provider, a regulator or official publication, an open dataset, or the user's own records. Sportsbook credentials stay inside the existing sync provider's hosted flow.
6. **US multi-state, 21+.** Anything that depends on state law reads the user's state from the profile and hides itself when the state or the rule is unknown.

Stop and log an owner question if an item seems to need any of these: bet-slip autofill or pre-filled tickets; in-app trading or wagering; pooled bankrolls, copy-betting or prize contests; language-model picks or confidence numbers; rewards tied to bets placed; bonus-expiry reminders; reading sportsbook pages or private endpoints; offshore books; selling user-level data.

## How to work

**Step 1. Orient.** Read the README, any CLAUDE.md or AGENTS.md, the docs folder, the CI configuration and the feature-flag system. Follow the stack, structure, naming and test style the repository already uses. Write `docs/backlog/orientation.md` with one row per already-built feature: code path, entry points, tests, and the build items that will touch it.
*Done when every already-built feature above has a row.*

**Step 2. Save the backlog.** Copy everything from "Tiers" to the end of this prompt into `docs/backlog/feature-backlog.md`. That file is the source of truth from then on; update it when scope changes. Create one ticket per foundation and per build item in the tracker this repository uses (Linear issues with the MED- prefix if that is what you find; otherwise one markdown file per item under `docs/backlog/tickets/`), each with its phase and blocked-by links.
*Done when the file is merged and 6 foundation tickets and 44 build-item tickets exist.*

**Step 3. Build Phase 0, then the build items in ID order.** Skip an item only when an owner decision blocks it: record the question, build what the interface allows, and move to the next item.

**Step 4. For each item:**

1. Write a short design note in the ticket: data model changes, API endpoints, screens, flag name, entitlement, test plan.
2. Turn each "Done when" line into a failing test, then implement until the tests pass.
3. Deliver it as one branch and one pull request into `main`. CI must pass before the next item starts.
4. Put it behind its own feature flag, default off, and gate it with the entitlement in its Tier.
5. Make it run end to end on synthetic fixtures. If the repository runs on synthetic data, keep it that way; connecting a real provider is an owner decision.
6. Add `docs/features/<item>.md`: what it does, its calculations and their limits, its flag and entitlement.

**Definition of done for an item:** a passing test for every "Done when" line; flag default off; runs on synthetic fixtures; all six hard rules hold; copy guard passes; the web surface works by keyboard and screen reader; feature doc written; pull request merged; ticket closed.

**Step 5. End each session with a report:** items merged, flags added, owner questions raised, next item.

## Owner decisions

For each of these, build to the interface, leave the flag off, and add the question to `docs/backlog/owner-questions.md`:

- Prices, plan names and trial terms
- Which licensed providers supply lineups and news, live box scores, historical odds, house rules and exchange prices
- Redistribution rights for any data shown outside OddVex (F41 to F43)
- Sportsbook affiliate agreements and state affiliate licensing (F30)
- Legal review of tax, complaint and prediction-market content (F05, F36, F39, F40)
- App-store billing set-up (F24)

## Tiers

`free`, `premium`, `pro`, `b2b`. Safety and honesty features are always `free`. Prices and limits live in configuration.

"From" shows the source ideas: A = strategy doc ideas 1 to 20, B = second list, C = deep-research list.

## Phase 0. Foundations

**P0.1 Snapshot archive.** Append-only, timestamped captures of every book price, the consensus inputs, and lineup or news status, queryable as of a time T.
*Done when any stored bet joins to the best price across the user's books at its placement time, and a query for T returns only rows captured at or before T.*

**P0.2 Calculation provenance.** Every displayed number is stored with its method id, method version, inputs and as-of time.
*Done when the odds, value, prop and tracker APIs return provenance for each numeric field and a test reproduces each number from it.*

**P0.3 Entitlements.** Server-side resolution of free, premium, pro, pass and b2b keys.
*Done when one helper answers "may this user use feature X" for API, web and mobile.*

**P0.4 Profile settings.** State, books held, odds format (American, decimal, implied probability), unit size, display mode, quiet and plan state, synced across web and mobile.
*Done when a change on one client appears on the other.*

**P0.5 Provider interfaces with synthetic fixtures** for lineups and news, live box scores, sportsbook house rules, state market catalogs, exchange contract prices and fees, and venue legal status by state.
*Done when each has an interface, a fixture provider and contract tests.*

**P0.6 Copy guard and suppression hook.** A CI check that fails on the banned phrases in user-facing strings, and one function that every opportunity surface and notification sender calls first.
*Done when CI fails on a seeded banned phrase and a test proves a suppressed user receives nothing on any channel.*

## Phase 1. First wave

**F01 Check My Bet.** From A1. Tier: free with a daily cap, premium unlimited. Needs P0.1, P0.2.
The user shares a screenshot, pastes text or types a bet slip, single or parlay. Parse the legs, match each to a market, and return the fair price, the best price at the user's books, and the cost of the offered price per $100. One tap logs the bet to the tracker.
*Done when a fixture set of 50 slips resolves with every leg either matched or reported as "cannot price", no leg is priced on an uncertain match, and same-game legs report "cannot price" until F26 stage 2.*

**F02 Sync & Settlement Inbox.** From B5. Tier: free.
Show which dates and accounts imported, and list gaps, likely duplicates and grading disagreements. Each exception shows what the source and OddVex each recorded; the user confirms a correction to their OddVex record.
*Done when seeded gap, duplicate and mis-grade fixtures each raise exactly one exception, and a confirmed correction is audited and reversible.*

**F03 Leak Report.** From A7. Tier: free headline, premium breakdown and history. Needs P0.1, F02.
A weekly report of what the user's betting cost beyond the vig: dollars paid above the best available price at placement time, results by bet type, and CLV. Each figure carries its sample size and interval. Frame everything as cost.
*Done when every figure reproduces from snapshots for a fixture account and the report is suppressed during Quiet Mode.*

**F04 Today.** From A2 and B1. Tier: free, premium live refresh.
A home screen built by fixed rules, ten cards at most: open bets and settlements needing a look, watchlist changes, threshold crossings, last open research. It states plainly when nothing needs attention.
*Done when card order is deterministic for a fixture user, the empty state renders, and every card passes through the suppression hook.*

**F05 Records Pack & Tax Center.** From A9 and B12. Tier: premium, plus a one-time unlock entitlement.
A tax-year view of winnings and losses by book and day. Import sportsbook statements and other trackers' CSV, reconcile them against the tracker, flag missing periods, and export a preparer packet as PDF and CSV. A separate flag `tax_estimate` (default off) adds an estimate of deductible losses under the 90% rule (the lesser of 90% of losses and total winnings), labelled as an estimate and not tax advice, with the law's last-checked date.
*Done when a fixture year reconciles to the cent against a seeded statement, missing periods are flagged, the estimate matches three worked examples, and the export opens.*

**F06 Dollar View.** From A3. Tier: free.
A toggle that restates every price as dollars risked, dollars won and vig cost per $100 against the fair price, with the fair price labelled a consensus estimate.
*Done when the toggle persists in the profile and applies on odds, value, prop, tracker and calculator screens.*

**F07 Tap to Explain.** From C4. Tier: free. Needs P0.2.
Every number opens a two-line plain explanation plus its formula, inputs, data time and source books. Every card and alert has a "why is this here" link. Explanation copy is reviewed static text.
*Done when every numeric field on the odds, value, prop and tracker screens opens an explanation whose inputs reproduce the displayed value.*

**F08 Clear Mode.** From C1. Tier: free.
A display mode for screen-reader, keyboard-only, high-contrast and colour-blind-safe use. Best and stale prices are conveyed by text or icon with a label. Live updates are announced politely and throttled.
*Done when the odds, value and tracker screens pass automated WCAG 2.2 AA checks with zero serious violations, and live announcements occur at most once per 10 seconds per focused row.*

**F09 Consensus Stress Test.** From B16. Tier: free.
Beside every value figure, show which books fed the consensus, how fresh each quote was, and the value after removing each book in turn. Mark the comparison fragile when one removal erases it or coverage is thin.
*Done when the fragile flag fires on a fixture where one book drives the value, and the thresholds are documented constants.*

**F10 Trend Stress Test.** From B6. Tier: free.
Put a recent hit rate beside a full-season baseline, show how many games the two share, and flag when dropping one game or excluding overtime changes the result materially.
*Done when the leave-one-out and overtime flags fire on seeded logs for each league.*

**F11 Quiet Mode.** From B8. Tier: free.
A user-set break that hides current markets and opportunity screens and stops alerts on web, iOS, Android and email until the user ends it. Records, account controls and support resources stay reachable.
*Done when, with Quiet Mode on, no opportunity surface renders and no notification is sent on any channel.*

**F12 Open Scorecards.** From A16 and B20. Tier: free.
A public page for every signal and model: method, version, every time-stamped past output, performance against the closing line, calibration, sample size, known limits and abstentions. Start with value flags.
*Done when the value-flag scorecard builds from the snapshot archive, records are append-only, and a new method version starts a new series.*

**F13 Plain-English Market Search.** From B2. Tier: free.
Typing a phrase such as "Brunson first-half points" goes to the matching market. An ambiguous phrase asks the user to choose and explains the difference.
*Done when a fixture list of 100 phrases each resolves or disambiguates with no wrong silent match.*

**F14 Import-First Setup.** From A8. Tier: free.
Onboarding asks the user to connect a book or share one slip, then proposes state, books, watchlist and unit size from recent bets for the user to confirm.
*Done when a new fixture user reaches a populated Today screen in one flow and nothing is saved without confirmation.*

**F15 Bet Tags & Source Scorecard.** From C3. Tier: three tags free; unlimited tags, bulk rules and scorecards premium.
Tag bets by reason (own model, a creator, a boost, a hunch) with one tap or a bulk rule. Show results per tag: ROI with a 95% interval and average CLV.
*Done when bulk rules apply to past and newly synced bets, tags with fewer than 30 settled bets show "not enough data", and tags survive CSV export and import.*

## Phase 2. Second wave

**F16 State & Coverage.** From A6 and B7. Tier: free. Needs P0.4, P0.5.
Filter every screen to markets the user can legally and actually bet in their state at their books. Explain each hidden or missing price: not approved in the state, book not held, feed gap, paused market, or unknown. Show regulator market catalogs with last-checked dates.
*Done when a banned-market fixture is hidden with its reason and an unknown state hides state-dependent content.*

**F17 Lineup Check & Line Move Notes.** From A4 and B3. Tier: lineup status free; live chart markers premium, delayed 15 minutes on free.
Show expected, confirmed or unknown status for starters, goalies and pitchers with source and time. Line charts carry timestamped markers for injury, lineup, pitcher and weather reports. Copy states timing only, for example "reported 3 minutes before".
*Done when markers align to snapshot times on fixtures and the delayed view never shows an event younger than 15 minutes.*

**F18 Sweat Screen.** From A5. Tier: free.
A game-night view of every open leg across all books against the live box score, for example "has 7, needs 10, 14:00 left". Add the mobile lock-screen Live Activity and widgets where the mobile app supports them. The screen carries no live odds and no cash-out prompts.
*Done when leg status updates from the fixture box-score provider and the web view works without the mobile pieces.*

**F19 Luck or Skill.** From A17. Tier: free headline, premium detail.
Tell the user what their record can and cannot show: ROI with an interval, the ROI implied by their CLV, how many more bets would separate skill from no edge, and the expected monthly cost of their current pattern.
*Done when outputs match a reference notebook on three fixture accounts and nothing is shown below a documented minimum sample.*

**F20 Cash-Out Checker.** From A12. Tier: one free check, then premium.
The user enters a cash-out offer for an open bet. Show the fair value from current no-vig prices, how much the book keeps, and hedge sizing for a final leg. Pre-game remaining legs first; in-play sits behind a second flag.
*Done when fair value matches hand-worked cases and same-game remaining legs return "cannot price" until F26 stage 2.*

**F21 Worst-Case Map.** From B19. Tier: free.
Show the largest possible loss across the user's verified open bets for one game, including related bets at different books. List the bets that contribute, flag accounts that are not synced, and compare with the user's limit.
*Done when only jointly possible outcomes are counted on fixtures and missing accounts are flagged.*

**F22 Research Receipts.** From B17. Tier: free. Needs P0.1.
A private timestamped snapshot of the price, rule and evidence the user saw, with a note, including a decision to pass. Reopening it shows what has changed since.
*Done when a receipt renders identically after its source data changes and the diff view lists the changes.*

**F23 Plan Mode.** From A20. Tier: free. Extends F11.
A weekly plan across all books: budget, bet count, maximum stake, no-bet hours. When the plan is spent, or stakes rise after losses by a documented rule, start Quiet Mode until the next period and show a check-in with help resources. Detection is rule-based and stays inside the user's account.
*Done when each trigger fires on fixtures and suppresses every channel, and no paid entitlement gates the feature.*

**F24 Season Pass & Pause.** From A10 and B13. Tier: billing.
A fixed-term, non-renewing Premium pass for one league, with the end date shown at purchase. A pause option keeps records under a reduced "data keeper" entitlement, and the cancel flow offers pause first. Records stay exportable on free.
*Done when entitlements start and end on the stated dates in tests, an overlapping pass and subscription resolve predictably, and prices come from configuration.*

**F25 Limit Log.** From A19. Tier: premium.
The user records their stake limit per book and market. Odds screens can filter to books where the user's size fits. Pooled entries appear as user-reported figures with sample sizes. The feature records limits and stops there.
*Done when the filter respects logged limits and pooled figures appear only above a minimum sample without exposing any user.*

**F26 SGP True Cost.** From A18. Tier: stage 1 free, stage 2 premium.
Stage 1: for parlays with legs in different games, show the fair price from no-vig leg prices and the hold being charged, in percent and dollars. Stage 2, built in Phase 3: same-game parlays from a documented correlation model with published coverage and an error band; unsupported leg pairs return "cannot price".
*Done when stage 1 matches hand-worked parlays, and stage 2 has a scorecard under F12 before its flag can be enabled.*

**F27 Same Bet?** From B4. Tier: free. Needs P0.5.
Show grading-rule differences beside prices, such as how each book treats a player who leaves early, each with state, effective date and source. Label comparisons OddVex has not verified. Start with NBA props at two books.
*Done when every rule row has a source and date and unverified markets are labelled.*

**F28 Soccer Market Translator.** From C2. Tier: settlement tables free, cross-market comparison premium. Needs F27.
Convert three-way prices into draw-no-bet, double chance and Asian handicaps in quarter steps from +1.5 to -1.5. Show a settlement table for margins from -3 to +3. Label the cheaper of two equivalent forms with its cost difference per $100.
*Done when conversions match a reference sheet within 0.1% implied probability.*

**F29 Price Sense Trainer.** From C7. Tier: one drill a day free, full trainer premium. Needs F07.
Short drills on markets at least 24 hours old: estimate the fair price, the hold, or the better of two prices. Grade against the stored calculation and explain with Tap to Explain. Progress counts drills completed. Drill screens carry no sportsbook links and no live prices.
*Done when no drill uses a market younger than 24 hours and drill progress is hidden during Quiet Mode.*

**F30 Book Gap Report.** From A11. Tier: free. Needs F03.
From the user's bets and the snapshot archive, show which sportsbook they do not hold most often had the best price, and say so when no extra book would have helped. An offer or link renders only when `outbound_links` is on, the book is licensed in the user's state, and the user is not suppressed.
*Done when the report computes on fixtures and, with the flag off, the response contains no link.*

## Phase 3. Depth

**F31 Research Workspaces.** From B9. Tier: premium, one sample workspace free.
Save a multi-panel research setup with notes, open it on another device, and see which inputs changed.
*Done when a workspace round-trips between web and mobile and changed inputs are marked.*

**F32 Alt-Line Pricer.** From A13. Tier: pro.
Fit a documented distribution per stat type to the no-vig market, price alternate lines and ladders, and show where a book's line sits off the curve, with an error band. A stat type ships only after its scorecard exists under F12.
*Done when fits reproduce reference values and unsupported stats return "cannot price".*

**F33 Context Cohorts.** From B11. Tier: premium.
Compare a player's past games under conditions known before the game, such as a teammate out or the same projected role. Show the full game lists, group sizes and differences in minutes.
*Done when cohorts are defined only from pre-game information in the archive and group sizes are always shown.*

**F34 Historical Replay.** From B18. Tier: premium, sample cases free. Needs P0.1.
Reopen a past slate at a chosen pre-game time showing only what was captured by then. The user writes their reasoning, then reveals later information and the result. Archive gaps are marked.
*Done when no row captured after T is visible before the reveal.*

**F35 Settlement Evidence Packs.** From B10. Tier: premium, single explanations free. Needs F02, F27.
A private PDF for a settled bet with the book record, official result, dated house rule and any discrepancy. Several bets can be grouped, and the user can redact account details. The pack states facts and marks ambiguity.
*Done when a pack generates from fixtures and redaction removes the data from the file.*

**F36 Bettor Rights Desk.** From C10. Tier: guide free, complaint tracking premium. Needs F25, F35.
For the user's state and book, show the regulator's complaint channel, required information and deadlines with a last-verified date, and draft a complaint from the user's records. For Massachusetts, when a limit is logged, track the 48-hour notice window. Drafts are labelled "information, not legal advice", are editable, and are sent only by the user.
*Done when entries older than 90 days are flagged stale and the Massachusetts timer and draft work on fixtures.*

**F37 Model Sandbox.** From C9. Tier: pro.
A no-code builder for a simple pricing model with a walk-forward test against past closing lines. Report in-sample and out-of-sample results separately with intervals, count the variants tested and warn above five, and export a readable model specification. Results stay inside the sandbox.
*Done when a rerun of an exported specification is identical and results below 200 out-of-sample bets are withheld.*

**F38 Verified Creator Pages.** From A14. Tier: creator plan, viewing free.
A public page built only from synced bets: record, CLV, ROI with an interval, all in units. Pages are data only. Reuse the existing community models.
*Done when a page owner can change only display name and visibility.*

**F39 Tax Pro Connect.** From C6. Tier: directory free, secure sharing premium. Needs F05.
A directory of tax professionals with verified credentials. The user shares a read-only, expiring, revocable link to their tax-year report, and every access is logged and visible to the user.
*Done when links expire and revoke in tests and the access log is complete.*

## Phase 4. Gated on owner sign-off

Build these behind flags to their interfaces. They go live only after the owner confirms the licence or legal point in "Owner decisions".

**F40 Event-Contract Translator.** From C8. Tier: legal-status panel free, comparison premium.
Build the venue legal-status registry first: venue by state, with status, source and last-checked date. Then show exchange contract prices as odds after the venue's published fee, with resolution-rule differences from the matched sportsbook market. Prices are hidden where the venue is restricted or under order in the user's state.
*Done when the registry covers every venue-state pair and a test proves prices are hidden by default.*

**F41 OddVex for Sheets.** From C5. Tier: pro add-on.
Read-only spreadsheet functions for the user's own bets and OddVex derived values (fair price, EV, CLV), with timestamps and rate limits. A licence matrix in code decides whether a raw book price may be returned; the default is derived values only.
*Done when sign-in, the rate limit and the licence matrix are tested.*

**F42 OddVex for Discord.** From A15. Tier: b2b per server. Needs F01.
A self-serve bot: a member sends a slip or a command and receives the fair price and best book from F01's API. The server owner subscribes by card. The F41 licence matrix applies.
*Done when bot replies come from F01's API and a server without an active entitlement receives no data.*

**F43 Publisher Explainer Cards.** From B14. Tier: b2b.
An embeddable chart of a past market event with sources, timestamps and a visible correction history at a stable URL. One chart format.
*Done when an embed renders from archive data and shows its correction log.*

**F44 Market Data Quality Monitor.** From B15. Tier: internal.
A weekly internal report of feed gaps, update delays and corrections by league and market, feeding stale-price flags and F16. External reports wait for the owner.
*Done when the report runs on fixtures and is visible in admin.*
