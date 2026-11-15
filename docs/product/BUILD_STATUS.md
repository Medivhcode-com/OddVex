# Build status (milestone 1 and the approval-free part of milestone 2)

What exists on the branch, and the evidence for it. Everything runs on synthetic data with fictional teams, players
and sportsbooks. Nothing has been deployed, purchased or published.

## Verified by automated checks (run locally in the build session)

| Area | Check | Result |
|---|---|---|
| API | `pytest` in `services/api` (SQLite) | 569 passed |
| API | Same suite on PostgreSQL 16 | 570 passed (run once locally by the backend build; now a CI job) |
| API | `ruff check`, `ruff format --check`, OpenAPI export `--check` | Clean |
| Web | Playwright end to end, real API + production build, desktop and phone viewports, including automated WCAG A/AA checks in both themes | 149 passed |
| Web | ESLint, `tsc --noEmit`, Vitest | Clean, 12 unit tests passed |
| Mobile | `tsc --noEmit`, `expo lint`, Jest | Clean, 42 tests passed |
| Mobile | `expo export` for iOS and Android (JS bundle only) | Bundled |

## Built

- **Marketing site:** home, features, four product pages, pricing (no prices set), about, blog (three posts),
  contact, help, privacy and terms (preview drafts), responsible gambling, methodology, download, sitemap, robots.
- **Web app:** dashboard, games, game detail with odds comparison and line movement, odds board, prop board, prop
  analyzer, calculators (convert, no-vig, EV, CLV), parlay research with correlation warning, bet tracker, mock
  sportsbook sync, OddVex AI (rule-based), settings with account deletion, login and signup with 21+ confirmation.
- **API:** quant engine, synthetic provider behind a provider contract, auth, bets, sync layer with mock provider,
  assistant, admin overview endpoint, audit log, rate limiting, Alembic migration, demo seed script.
- **Mobile:** games list, game detail with odds comparison, settings.
- **Foundation:** constitution, agent guides, CODEOWNERS, PR and issue templates, CI workflow, Docker files, ADRs,
  design system and showcase page with a visual regression baseline.

## Added after milestone 1 (no approval gate involved)

- **Watchlist:** follow teams, players and games; watched games appear on the dashboard.
- **Research to tracking:** add a bet to the tracker from a game page at the best current price.
- **Auto-settlement:** bets tied to a game and side settle from the final score, through the same payout math as
  manual settlement. Bets entered as free text still need settling by hand.
- **Tracker:** edit an open bet, record closing odds, settle a parlay leg by leg.
- **Account:** change password (signs out other sessions), download your data as JSON.
- **Refresh:** games, odds and game detail re-fetch on an interval the user can pause.
- **Accessibility:** axe checks on every main screen in dark and light themes.
- **Operations:** request size limit, bet list sorting and filters in the API, Docker images built and smoke-tested
  in CI, PostgreSQL test job in CI.

## Milestone 2 items that need Founder approval and are not started

Licensed data provider, production infrastructure, counsel review of legal pages and age gating, closed beta, real
email (verification, password reset), historical odds storage against a real feed.

## Not verified

- `docker-compose.yml` has not been started. The two images build and answer requests in CI.
- The mobile app has not been run on a device or simulator.
- Accessibility has automated checks only. No screen reader or keyboard-only walkthrough has been done.
- Competitor and provider research relied on search extracts, not direct page visits. Re-check every price.

## Not built

Real data provider, alerts and notifications, community, premium billing and entitlements, admin console
UI, LLM-backed assistant, model projections and backtesting, password reset by email, refresh tokens, production
infrastructure, store submission, analytics instrumentation, error monitoring.

## Known gaps inside what is built

- The assistant matches keywords. It handles a small set of question types and declines the rest.
- Prices refresh on a timer, not by push.
- The mobile app does not have the watchlist, tracker or calculators yet.
- Watchlist items do not trigger alerts.
- Legal pages are unreviewed drafts and say so. The contact page has no address until one is configured.
