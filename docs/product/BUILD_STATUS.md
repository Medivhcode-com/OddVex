# Build status

## Founder-action verification — 2026-11-16

The launch-action receipt is [FOUNDER_ACTION_STATUS.md](FOUNDER_ACTION_STATUS.md) (MED-71).

Pull request #10 was merged to `main` on 2026-11-16 after all eight CI jobs passed. The mobile lint failure that the
receipt recorded at commit `c044583` was fixed before the merge. The test counts below are from the merged commit.

A free Neon preview database was provisioned and a read-only connectivity query passed. It has no OddVex schema or
application connection yet. Vercel is connected but medivh-code team access returns 403; no Vercel deployment was
changed. The counsel and provider inquiries are saved drafts, not sent. Organization store enrollment, working
mailboxes and physical-phone testing remain incomplete.

See the dated counsel addendum and phone guide for corrections to the original founder checklist.

What exists on the branch, and the evidence for it. Everything runs on synthetic data with fictional teams, players
and sportsbooks. Nothing has been deployed, purchased or published.

## Verified by automated checks (run locally in the build session)

| Area | Check | Result |
|---|---|---|
| API | `pytest` in `services/api` (SQLite) | 1,209 passed, 1 skipped (PostgreSQL-only concurrency test) |
| API | Same suite on PostgreSQL 16 | 1,214 passed (run locally by the backend build; also a CI job) |
| API | `ruff check`, `ruff format --check`, OpenAPI export `--check` | Clean |
| Web | Playwright end to end, real API + production build, desktop and phone viewports, including automated WCAG A/AA checks in both themes | 325 passed |
| Web | ESLint, `tsc --noEmit`, Vitest | Clean, 50 unit tests passed |
| Mobile | `tsc --noEmit`, `expo lint`, Jest | Clean, 470 tests passed |
| Mobile | `expo export` for iOS and Android (JS bundle only) | Bundled |

## Built

- **Marketing site:** home, features, four product pages, pricing (no prices set), about, blog (three posts),
  contact, help, privacy and terms (preview drafts), responsible gambling, methodology, download, sitemap, robots.
- **Web app:** dashboard, games, game detail with odds comparison and line movement, odds board, prop board, prop
  analyzer, calculators (convert, no-vig, EV, CLV), parlay research with correlation warning, bet tracker, mock
  sportsbook sync, OddVex AI (rule-based), settings with account deletion, login and signup with 21+ confirmation.
- **API:** quant engine, synthetic provider behind a provider contract, auth, bets, sync layer with mock provider,
  assistant, admin overview endpoint, audit log, rate limiting, Alembic migration, demo seed script.
- **Mobile:** games, game detail with odds comparison, props board and analyzer, calculators and parlay research,
  bet tracker with settlement and mock sync, watchlist, OddVex AI, sign-in and account settings. Data export, the
  profit chart and the performance breakdowns are web-only.
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

## Added from milestone 3 (no approval gate involved)

- **Alerts:** rules for a price reaching a threshold, a line moving, a game about to start and a final score, set
  from a game page on web and mobile. One-shot rules can be set again; team rules keep firing for each game.
- **Notifications:** an in-app list with an unread count, mark as read, delete, and per-type on/off preferences.
  Settled bets and sync results also notify.
- **Weekly staking reminder:** a self-set amount. Reaching it produces one reminder a week with the helpline number.
  It is a reminder, not a limit: bets are still saved.
- **Admin overview (web):** a read-only page with service counts, provider health and the recent audit log, visible
  only to accounts the API marks as admin.

Limits: alerts are evaluated when the user opens the app or when `scripts/evaluate_alerts.py` runs. There is no
background worker, and nothing is delivered by push or email, both of which need Founder approval.

## Added from milestones 4 to 6 (code only; nothing deployed, purchased or published)

- **Value screen:** where the best open price beats the no-vig consensus of the other books, with the method and a
  caveat that this is not proof of an edge. Web and mobile.
- **Tracker analytics:** results by odds band, weekday and month, streaks described neutrally, closing line value
  and stake distribution, with a caution when the sample is small. Web and mobile.
- **Feature flags and plans:** flags drive navigation on web and mobile. Plans exist (free, premium) and can be set
  by an admin, but there is no billing and nothing is gated: both plans get the same features.
- **Admin console (web):** users (search, suspend with a reason, set plan), flags, audit log, email outbox.
- **Email flows without sending:** verification and password reset write to an outbox table. No email leaves the
  system. The flag is off by default in production.
- **Community (off by default):** opt-in profiles, structured picks graded from final scores, follows, a feed,
  comments, likes, blocks, reports, automatic content rules and a moderation queue. The leaderboard has a second
  flag, also off. Web and mobile; moderation is web only.
- **Security hardening:** content security policy and HSTS on the web app, visitor address and request id forwarded
  to the API, server-side logout (ends every session for the account), per-account login throttling, a security
  regression suite, and a dependency audit in CI.
- **Launch documents:** deployment plan (not executed), runbook, rollback plan, threat model, counsel review packet,
  store submission prep, go/no-go template, support playbook and decision log.

Before the community flags are turned on anywhere real: legal review of user-generated content, a responsible
gambling review of the leaderboard, and staffed moderation. The content rules are blunt and do not replace people.

## Milestone 2 items that need Founder approval and are not started

Licensed data provider, production infrastructure, counsel review of legal pages and age gating, closed beta, real
email (verification, password reset), historical odds storage against a real feed.

## Not verified

- `docker-compose.yml` has not been started. The two images build and answer requests in CI.
- The mobile app has not been run on a device or simulator. Layout, navigation between tabs, keyboard handling,
  secure token storage on real hardware, VoiceOver and TalkBack are all unobserved.
- Accessibility has automated checks only. No screen reader or keyboard-only walkthrough has been done.
- Competitor and provider research relied on search extracts, not direct page visits. Re-check every price.

## Not built

Real data provider, push and email delivery, a background worker for alerts and pick grading, premium billing, LLM-backed assistant, model projections and backtesting, refresh tokens, multi-factor sign-in, production
infrastructure, store submission, analytics instrumentation, error monitoring.

## Known gaps inside what is built

- The assistant matches keywords. It handles a small set of question types and declines the rest.
- Prices refresh on a timer, not by push.
- Alerts only fire when the app is opened; a start-time alert nobody checks before the game begins expires silently.
- Legal pages are unreviewed drafts and say so. The contact page has no address until one is configured.
