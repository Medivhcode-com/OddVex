# Milestone 1 status

What exists on the branch, and the evidence for it. Everything runs on synthetic data with fictional teams, players
and sportsbooks. Nothing has been deployed, purchased or published.

## Verified by automated checks (run locally in the build session)

| Area | Check | Result |
|---|---|---|
| API | `pytest` in `services/api` | 422 passed |
| API | `ruff check`, `ruff format --check`, OpenAPI export `--check` | Clean |
| Web | Playwright end to end, real API + production build, desktop and phone viewports | 81 passed |
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

## Not verified

- CI has never run: the remote had no default branch to open a pull request against.
- The Docker images and `docker-compose.yml` have not been built or started.
- The mobile app has not been run on a device or simulator.
- PostgreSQL was exercised once locally by the backend build, not in CI. CI uses SQLite.
- Accessibility has automated structure checks only. No screen reader or contrast audit has been done.
- Competitor and provider research relied on search extracts, not direct page visits. Re-check every price.
- Visual regression baselines were captured in this build container and may need regenerating on CI.

## Not built

Real data provider, alerts and notifications, watchlists, community, premium billing and entitlements, admin console
UI, LLM-backed assistant, model projections and backtesting, password reset, refresh tokens, data export, production
infrastructure, store submission, analytics instrumentation, error monitoring.

## Known gaps inside what is built

- The assistant matches keywords. It handles a small set of question types and declines the rest.
- Prices refresh on page load, not live.
- The tracker UI cannot edit a bet or settle individual parlay legs, though the API supports both.
- Two simultaneous syncs for one user can return a server error instead of a clean conflict.
- Legal pages are unreviewed drafts and say so. The contact page has no address until one is configured.
