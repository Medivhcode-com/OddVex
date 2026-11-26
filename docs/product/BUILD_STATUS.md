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
and sportsbooks. Since 2026-11-18 a private preview runs on the Hostinger VPS (see "Private preview on the Hostinger
VPS" below). Nothing has been purchased or published.

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

The counts above are from 2026-11-16. The squash commit of pull request #19 (`2b0c7c1`, 2026-11-21) reports: API 4,627
tests on SQLite and 4,636 on PostgreSQL, web end to end 387 of 387, mobile 528, infrastructure 168, CI 9 of 9 jobs.
Those figures are quoted from the commit message and were not run again for this page.

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
- **Admin area (web):** an overview page with service counts, provider health and the recent audit log, plus pages
  for users (suspend, unsuspend, plan), feature flags, the email outbox, the audit log and community moderation,
  visible only to accounts the API marks as admin.

Limits: alerts are evaluated when the user opens the app or when `scripts/evaluate_alerts.py` runs. On the Hostinger
preview a `worker` container runs that script, and `scripts/grade_picks.py`, every two minutes
(`infrastructure/hostinger/compose.yaml`); anywhere else nothing runs them on a schedule. Nothing is delivered by push
or email, both of which need Founder approval.

## Added from milestones 4 to 6 (code; on the private preview since 2026-11-18; nothing purchased or published)

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

Licensed data provider, public production infrastructure on `oddvex.com` (the private preview is the only deployment),
counsel review of legal pages and age gating, closed beta, real email (verification, password reset), historical odds
storage against a real feed.

## Not verified

- `docker-compose.yml` has not been started. The two images build and answer requests in CI.
- The mobile app has not been run on a device or simulator. Layout, navigation between tabs, keyboard handling,
  secure token storage on real hardware, VoiceOver and TalkBack are all unobserved.
- Accessibility has automated checks only. No screen reader or keyboard-only walkthrough has been done.
- Competitor and provider research relied on search extracts, not direct page visits. Re-check every price.

## Private preview on the Hostinger VPS (decision D-016)

Deployed with `infrastructure/hostinger/ops.sh`, run by the one-shot ops container (`ops.compose.yaml`). The decision
log records the deploys in D-021. Every deploy so far:

| When (UTC) | Release | What happened |
|---|---|---|
| 2026-11-18 | `d5749e0` | First deploy, with the first version of the ops script. It generated the database password and JWT secret on the server; the `caddy` action run that day generated the preview password |
| 2026-11-19 | `855991c` | Redeploy from `main` |
| 2026-11-19 16:46 | `4092395` | First deploy with the current ops script: the services were renamed to `oddvex-api` and `oddvex-web`, the contact address `support@oddvex.com` was set in `/opt/oddvex/.env`, a pre-deploy dump was taken, no migration was pending |
| 2026-11-21 05:29 | `2b0c7c1` | Database revision 0005 to 0007. Pre-deploy dump `predeploy-20261121T052923Z-4092395-to-2b0c7c1.dump`. Result `ok`. The images of `4092395` are kept on the server for a rollback |
| 2026-11-21 08:21 | `4026ddc` | No migration was pending; the database stays at revision 0007. Pre-deploy dump `predeploy-20261121T082044Z-2b0c7c1-to-4026ddc.dump`. Result `ok`. The images of `2b0c7c1` and `4092395` are kept on the server for a rollback |

Checks after the `2b0c7c1` deploy, at 2026-11-21 05:33 UTC:

- `preview.oddvex.com` answers 401 without the password.
- `api-preview.oddvex.com/health` and `/v1/meta` answer 200.
- `/v1/props?market=*` answers an empty list, and the full prop board still loads.
- An extreme input to a quant calculator answers 422.
- The other sites on the server answer 200 or 307 (their normal redirect).
- The name `api` no longer resolves to an OddVex container on the shared proxy network.

Checks after the `4026ddc` deploy, at 2026-11-21 08:22 UTC:

- `preview.oddvex.com` answers 401 without the password.
- The API health check and the web home page answer 200.
- `/v1/props?market=*` answers an empty list, and the full prop board still loads.
- The other sites on the server answer 200 or 307.
- The name `api` does not resolve to an OddVex container on the shared proxy network.

No deploy has been made since (as of 2026-11-26): the preview runs `4026ddc`.

Earlier records, still true:

- The worker's output showed completed passes at 05:23 and 05:25 UTC on 2026-11-19 (alert evaluation, then pick
  grading; nothing to do). The backup container wrote its first daily dump that day:
  `/backups/oddvex-20261119T052302Z.dump`.
- DNS `A` records `preview` and `api-preview` for `oddvex.com` point at the server.
- One marked block for `preview.oddvex.com` (password-protected) and `api-preview.oddvex.com` (no password) was
  appended to the server's shared Caddyfile on 2026-11-18. Caddy validated the file and reloaded without error. The
  previous file is kept at `/opt/oddvex/Caddyfile.before-oddvex-20261118T074444Z` on the server.
- The Founder opened `https://preview.oddvex.com` on 2026-11-19 and confirmed it works.
- The mailbox `support@oddvex.com` exists (created by the Founder on 2026-11-19) and the domain has MX, SPF, DKIM and
  DMARC records. Since the `4092395` deploy the preview's web image is built with the address (`ODDVEX_CONTACT_EMAIL`,
  passed to the build as `NEXT_PUBLIC_CONTACT_EMAIL`); the live contact page was not checked. That the mailbox receives
  mail is not verified: no test message was sent by the build session.
- `ODDVEX_ADMIN_EMAILS` is empty on the server, so the preview has no administrator.

The API runs in production mode on synthetic data. Its hostname has no password, because the mobile app calls it
directly, so anyone on the internet can create an account there.

Android preview build: EAS build `e0686e6b-192e-460a-a60b-647ad97f7591`, from commit `9bb7677`, finished. It is an APK
built with the `preview` profile of that commit (`withoutCredentials: true`, so it carries the public debug signature
described in `apps/mobile/README.md`) and calls `https://api-preview.oddvex.com`. Its download link expires on
2026-12-03.

Not verified on the server:

- That the build ceiling holds a real build. No build has been seen reaching the 2 GB limit of the build container.
- A restore of a dump (`ACTION=restore`). It is rehearsed in tests against PostgreSQL 16 only.
- That the mailbox `support@oddvex.com` receives mail.
- A rollback (`ACTION=rollback`) and the automatic put-back of the previous release after a failed deploy.
- Whether the Docker Manager page repeats the last action when the ops project is started again.

Not configured: real email from the product, off-server backups, monitoring or alerting. `oddvex.com` itself is
unchanged.

## Replay preview (internal only, decision D-015)

`ODDVEX_DATA_PROVIDER=replay` serves the real 2024 NFL season shifted 104 weeks forward: real teams, players, results,
player statistics and one recorded closing line per game; fictional sportsbooks with simulated prices and prop lines.
It is labelled "Replay" in the web and mobile apps, shows the nflverse credit line, never reveals a result before the
shifted game ends, and refuses to start in production. NFL only. See `data/external/README.md` for how to run it.
The dataset is not committed, so CI tests the provider on a fictional fixture.

## Not built

Real data provider, push and email delivery, premium billing, a language-model assistant, model projections and
backtesting, refresh tokens, multi-factor sign-in, public production infrastructure on `oddvex.com`, store
submission, analytics instrumentation, error monitoring.

## Known gaps inside what is built

- The assistant matches keywords. It handles a small set of question types and declines the rest.
- Prices refresh on a timer, not by push.
- Alerts fire when the app is opened or when `scripts/evaluate_alerts.py` runs: every two minutes on the preview, not
  on a schedule anywhere else. Without that, a start-time alert nobody checks before the game begins expires
  silently.
- Legal pages are unreviewed drafts and say so. The contact page shows `NEXT_PUBLIC_CONTACT_EMAIL` when the web image
  is built with it (the preview is built with `support@oddvex.com`, per the build setting; the live page was not
  checked) and a placeholder otherwise.
