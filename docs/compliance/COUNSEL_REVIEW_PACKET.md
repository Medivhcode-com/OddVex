# OddVex — Counsel review packet

First prepared: 2026-11-16 · Reissued: 2026-11-21, describing the code at commit `2b0c7c1` (the release running on
the private preview since 2026-11-21) · Prepared by: product and engineering documentation, not lawyers · Status:
**not sent. Counsel has not been chosen (ROADMAP Q-09).**

> **Not legal advice.** This packet describes a product and asks questions. It reaches no legal conclusion and none
> should be read into it. Statements about law or store policy elsewhere in this repository are the team's
> unverified understanding. Everything here is for qualified counsel (US gaming, privacy, consumer protection and
> advertising, intellectual property) to review, correct and answer.

Sending this packet and acting on the answers are Founder decisions (gate G-10 in `docs/product/ROADMAP.md`). The
Founder waived the need to ask for approval on 2026-11-19 (`docs/product/DECISION_LOG.md`, D-019); that waiver does
not replace legal review, and nothing in this packet has been reviewed by a lawyer.

## 0. This packet changed after it was marked ready to send

The version of 2026-11-16 was marked "ready to send" and was never sent. A dated addendum
(`COUNSEL_REVIEW_ADDENDUM_2026-11-16.md`) corrected four of its statements. By 2026-11-21 much more of it had stopped
being true, so it has been rewritten from the code at `2b0c7c1`. The addendum is superseded by this version: do not
send either earlier text. What changed:

| Earlier statement (2026-11-16) | Now (code at `2b0c7c1`, preview as recorded in `docs/product/BUILD_STATUS.md`) |
|---|---|
| "Nothing is deployed … No personal data has been collected from anyone" | A private preview runs on a rented server in production mode since 2026-11-18 (section 2.4). Its API is open to the internet and accepts sign-ups from anyone, so it can hold real email addresses, password hashes and IP addresses. Whether anyone outside the team has signed up cannot be seen from the repository |
| "Nothing has been bought. No … hosting, email service or store developer account exists" | The preview runs on a Hostinger server the Founder already paid for (D-016). A Google Play developer account and an Expo project exist (D-018, D-020). The mailbox `support@oddvex.com` exists (D-022). No Apple developer account is recorded. No data licence or email-sending service exists |
| Hosting preference Vercel with Neon (also in the addendum) | Superseded by D-016: the Hostinger server and the `oddvex.com` domain |
| Admin is "a read-only overview for staff"; admin user management is "in progress, unmerged" | Built. Administrators can search users, suspend accounts, set plans, turn feature flags on and off, read the audit log and the email outbox, export or delete an account on its owner's behalf, and moderate community content (section 5.7) |
| "It has no user-generated or community content. Not on `main`" | A community module is merged: profiles, structured picks, comments, follows, likes, blocks, reports and moderation. It is switched off by default and is off on the preview (section 5.5) |
| Real team and player names: not decided | A replay of the real 2024 NFL season with real team and player names exists for internal preview only. It refuses to start in production mode and is not on the preview (section 5.9) |
| "There is no background process"; alerts are evaluated when the user opens the app | On the preview a worker evaluates alerts and grades community picks every two minutes. Delivery is still in-app only (section 5.3) |
| No reporting or blocking flow | Reporting, blocking and a moderation queue are built, behind the community switch (section 5.5) |
| Tables taken from commit `bdd77a5` (11 tables) | 22 tables at `2b0c7c1` (section 3.1) |
| Server logs: retention undecided; no mention of backups | The API logs each request without its query string. Daily database dumps are kept 14 days, plus copies made before each release. Section 3.2 and 3.6 |
| Assistant: answers a small set of question types | Unchanged in substance, plus fixed rules for crisis, distress, under-21 and certainty messages, and a help sentence at the end of every other answer (section 5.8) |
| The helpline given was 1-800-GAMBLER | The product now gives the National Problem Gambling Helpline, 1-800-MY-RESET (1-800-697-3738), and 988 or 911 in a crisis (section 5.2) |
| Contact page: no mailbox exists | `support@oddvex.com` exists; the preview's web build is set to show it. That it receives mail has not been verified (D-022) |
| Value screen "in progress" | Built; its switch is on by default (section 5.4) |
| Synthetic data "has no real edge by construction" | The statement now rests on a test over 3,000 synthetic games (section 2.4) |

## 1. What we are asking for

| # | Request | Needed before |
|---|---|---|
| 1 | Answers to the prioritized questions in section 6 | A closed beta with real users; some (questions 21 to 23) apply to the preview that is running now |
| 2 | Review and redraft of the three public legal pages in section 4 | Any real user |
| 3 | A view on the sensitive features in section 5, each of which is built | Any real user |
| 4 | A list of anything in the product or these documents that should change before real users see it | Any real user |
| 5 | Scope, timeline and fee estimate for the above | Engagement (Founder, G-02 for spend) |

## 2. Product description

### 2.1 What OddVex is

A sports-betting **information** product for adults 21 and over in the United States, owned by Medivh Code (legal
entity name and address to be confirmed by the Founder, ROADMAP Q-10). A website, a web app and a mobile app
(iOS and Android) backed by one API.

### 2.2 What it does today

| Feature | What the user gets |
|---|---|
| Odds comparison | Prices for the same game from several sportsbooks side by side, the best price marked, each price with its age. A price is marked stale, and never best, when it has no time, is older than a threshold, or (in a live game) was quoted before the latest score change |
| Line movement | How a line has moved over time |
| Player prop research | Past results against a line, shown as "x of n games" with a statistical range, labelled as a record and not a forecast |
| Calculators | Odds conversion, no-vig, expected value, closing line value, parlay payout and break-even |
| Parlay research | Combined odds, payout and the break-even rate (how often the parlay must win to break even), with a warning when legs are from the same game. The screens show no chance that every leg wins |
| Value screen | Upcoming games where one sportsbook's price differs from the no-vig consensus of the others (section 5.4). Switched on by default |
| Bet tracker | A personal ledger of bets the user placed elsewhere: stake, odds, sportsbook, result, profit and loss. At most 5,000 bets per account |
| Tracker analytics | Breakdowns of the user's own record, including streaks shown as plain statistics. Switched on by default |
| Auto-settlement | A tracked bet tied to a game can be marked won or lost from the final score |
| Mock sportsbook sync | A demonstration import from a fictional account. No real sportsbook is connected |
| Watchlist | Follow teams, players and games |
| Alerts and notifications | User-set rules (a price reaches a level, a line moves, a game is about to start, a game ends) that produce in-app notifications |
| Weekly staking reminder | A user-set amount; reaching it produces one in-app reminder a week with the helpline number |
| Assistant ("OddVex AI") | Answers a small set of question types from the product's own data. It is rule-based. No language model is connected. Fixed replies for crisis, distress and under-21 messages (section 5.8) |
| Account | Email and password, 21+ confirmation, change password, download your data, delete your account. Email verification and password reset are built but switched off in production, where no email is sent |
| Community | Built and switched off (section 5.5) |
| Staff tools | Administrator screens and routes (section 5.7) |

### 2.3 What it does not do

| Fact | Source in the repository |
|---|---|
| It does not accept, place, route or settle wagers and holds no user funds | `PROJECT_CONSTITUTION.md` section 1 |
| It has no payment, deposit, withdrawal or subscription function | `services/api/README.md` route table |
| It has no links to sportsbooks and no affiliate or referral links | Not built. See section 5.6 |
| It shows no advertising | Not built |
| It collects no sportsbook usernames or passwords | `services/api/src/oddvex_api/db/models.py`; `PRIVACY_AND_DATA.md` section 5 |
| It sends no email, push notification or text message. Emails it would send are written to an internal table (the outbox) | `services/api/README.md`; flag `email_flows`, off in production |
| It makes no predictions, picks or projections of its own. Community picks, when that module is on, are users' opinions | `services/api/README.md`; `services/api/src/oddvex_api/community/guidelines.py` |

### 2.4 State of the build

- **All sports data on the preview is synthetic.** Teams, players, sportsbooks, prices and statistics are fictional
  and generated by the software. The interface and the API label it as synthetic. The statement that synthetic
  prices carry no real edge rests on `services/api/tests/test_audit_board_calibration.py`: over a fixed synthetic
  season of 3,000 games (600 in each of five leagues), every side of every event market must win about as often as
  its no-vig price says, before the start and in play, within a tolerance of 4 standard errors; two further tests
  check game by game that each result is drawn from the same scoring model that prices the market. The test covers
  the synthetic provider's event markets. It says nothing about real data. Book prices add a margin and small noise
  on top of the fair price (decision D-027).
- **A private preview is running.** Since 2026-11-18 the product runs on a rented virtual server (Hostinger) that is
  shared with the operator's other projects (D-016, D-021). `preview.oddvex.com` serves the website and web app
  behind a password; `api-preview.oddvex.com` serves the API with no password, because the mobile test build calls
  it directly. The API runs in production mode. **Anyone who finds the API address can create an account**, so the
  preview can hold real email addresses, password hashes and IP addresses under legal pages that are unreviewed
  drafts. Whether anyone outside the team has signed up cannot be seen from the repository. `oddvex.com` itself is
  not launched.
- **No administrator exists on the preview.** The list of administrator addresses is empty on the server
  (`docs/product/BUILD_STATUS.md`), so nobody can use the staff tools there today, and nobody can switch the community
  on through the product.
- **Bought or created:** the server (already paid for), the domain, the mailbox `support@oddvex.com`, a Google Play
  developer account and an Expo project. **Not bought:** no data licence, no email-sending service, no Apple
  developer account is recorded.
- **The mobile app** has one Android test build (an APK signed with a public debug key, for the Founder's own phone;
  `apps/mobile/README.md`, "Builds"). It has not been reported as run on a phone; nothing is in a store.
- **The legal pages are drafts written by non-lawyers.**

### 2.5 What is planned and would change the analysis

| Planned | Milestone | Decided? |
|---|---|---|
| Licensed real odds, scores and statistics | M2 | No provider chosen. The Founder has deferred the choice (D-006) |
| Real team, league, player and sportsbook names for the public | M2 | No (gate G-12). An internal-only replay with real names exists (section 5.9) |
| Real email: verification, password reset | M2 | Flows are built and write to the outbox without sending. Sending is not approved (gate G-06). The Founder's stated preference for a provider is Resend (D-005, not an approval) |
| Public hosting on `oddvex.com` | M2 | Not decided. The private preview on the Hostinger server is the only deployment |
| Push notifications | M3 | No |
| Real sportsbook account sync through a third-party vendor | M3 | No |
| Outbound or affiliate links to sportsbooks | M3 at the earliest | **No. The Founder has not decided whether affiliate revenue is part of the business** (ROADMAP Q-03) |
| Paid subscription | M4 | No prices set (gate G-07). Accounts carry a plan field; both plans include everything and nothing can be bought |
| Assistant backed by a language model | M4 | No |
| Projections and backtesting | M4 | No |
| Community switched on | M5 | Built, switched off. Turning it on is not decided |
| App Store and Google Play submission | M6 | No (gate G-04) |

## 3. Personal data the software handles

Taken from the database models at commit `2b0c7c1` (`services/api/src/oddvex_api/db/models.py`) and the clients.

### 3.1 Stored in the database

| Table | Fields that are or may be personal | Notes |
|---|---|---|
| `users` | Email, display name, password hash (argon2id), role (`user` or `admin`), active flag, plan (free or premium, no billing), status (active or suspended), time of 21+ confirmation, created time, last sign-in time, time of last password change, time the email was confirmed, a token version, and a folded copy of the email and display name used by the staff search | The 21+ confirmation is a timestamp only. **No date of birth. No record of which version of the terms was accepted** |
| `bets` | Sportsbook name, bet type, sport, stake, odds, payout, profit, result, free-text notes, placed and settled times, how it was settled, source (manual or sync), an optional id the app sends so a retried save is not stored twice | Free-text notes can contain anything the user types |
| `bet_legs` | Selection text, market, league, event, line, odds, closing odds, result | |
| `sync_connections`, `sync_import_runs` | Provider name, status, label, opaque provider state, timestamps, counts, error text | Mock provider only. No credentials |
| `watchlist_items` | Teams, players and games followed | |
| `alert_rules` | The rule: game or team, market, side, threshold, state, timestamps | |
| `notifications` | Title, body, link, kind, read time | At most 500 kept per user |
| `notification_preferences` | Which notification kinds are switched off | |
| `stake_reminders` | The weekly amount the user set; the last week a reminder was created | See section 5.2 |
| `email_tokens` | Purpose, a hash of the token, created, expiry and use times | Verification and reset tokens. Only a hash is stored |
| `email_outbox` | Recipient address, subject, full message body, and for development a link | Emails the product would have sent. Nothing is delivered. Empty on the preview while the email flows are off |
| `feature_flags` | None | Stored on and off overrides of the feature switches |
| `audit_log` | User id, action, the type and id of the item acted on, **IP address**, request id, a small details object, time | Not linked by foreign key, so rows remain after account deletion (section 3.6) |
| `community_profiles` | Handle, bio, public or private, moderation status | Opt-in. A public profile shows the handle, bio, picks and graded record, never the email or name |
| `community_picks` | Game, market, selection, line, price, sportsbook, optional reasoning text, grading result, moderation status | |
| `community_comments` | Comment text, moderation status | |
| `community_follows`, `community_likes`, `community_blocks` | Who follows, likes or blocks whom or what | |
| `community_reports` | Reporter, reported user, target, reason, optional details text, resolution, the moderator's note, and a copy of the reported text taken when the report was made | The copy is kept so a moderator can judge content the author has since deleted (section 3.6) |
| `community_reserved_handles` | A handle and the date it was reserved | Kept when a suspended account is deleted, so the handle cannot be taken again. No email address and no fingerprint of one is kept |

### 3.2 Held elsewhere

| Where | What |
|---|---|
| API request log | One line per request: time, method, path **without the query string**, status, duration, client IP address and request id. No request bodies. The access log of the API's web server (uvicorn) is switched off by the start command since the release of 2026-11-19 and by the application itself since `2b0c7c1`; the API container of earlier releases wrote that access log, query strings included. Database errors are logged without the values of the statement |
| Other log records | The assistant writes one record per support reply, `assistant_support_reply`, holding only the case (crisis, distress or under 21) and whether the person was signed in; no message text and no user id. The worker and the backup job log what they did |
| Log retention | The container logs on the server have no size limit or retention rule set (`infrastructure/hostinger/compose.yaml` sets none). The shared reverse proxy's own logs were not inspected (not verified) |
| Database backups | A compressed copy of the whole database every day on the same server, kept 14 days; a further copy before each release, the newest five kept (section 3.6) |
| Web browser | One session cookie (`ov_session`, HttpOnly). A cookie for odds format (`ov_odds`). Theme and live-refresh choices in browser storage |
| Mobile device | The session token, its expiry and the user profile in the operating system's secure storage. Odds format in app storage |
| Assistant | Questions are answered and not stored. Apart from the support-reply record above, the assistant writes nothing to the database or the logs |

### 3.3 Not collected

Date of birth, government identifiers, precise or coarse location, payment details, contacts, device advertising
identifiers, sportsbook credentials, analytics events (no analytics tool is installed).

### 3.4 Added since the first version of this packet

All merged and running on the preview, except where marked.

| Addition | Personal data involved |
|---|---|
| Account status and plan | Suspended or active; free or premium (no billing) |
| Last sign-in time, email-confirmed time | Timestamps on the user |
| Email verification and password-reset tokens | A table of token hashes per user. The flows are off in production |
| Email outbox | Recipient address, subject and full message body of each email that would have been sent. Nothing is sent |
| Staff user management, export and delete | See section 5.7 |
| Community | Seven tables (section 3.1). Switched off, so the tables are expected to be empty on the preview (not checked) |
| Idempotent bet saves | An id generated by the app per save |

### 3.5 Where the drafts and the software disagree

These are ours to fix. Counsel should know about them because the draft policy cannot be finalised until they are
resolved. Rows 1 to 3 of the earlier list are closed: the draft `/privacy` page now lists every category above and
what deletion keeps, and the internal documents no longer claim a stored terms version or a stored time zone.

| # | Document says | Software does |
|---|---|---|
| 1 | `PRIVACY_AND_DATA.md` section 4 (design intent): deletion re-authenticates the user, passes through a pending state, de-identifies audit events and keeps a deletion ledger for restores | Deletion is immediate on typing DELETE, with no password prompt, no pending state, no de-identification and no ledger. The design intent is not built |
| 2 | `SECURITY_BASELINE.md` AU-03 and the screen map: sign-up must not reveal whether an email is registered | Sign-up returns "An account with this email already exists" |
| 3 | Sign-up screen: "By creating an account you agree to the terms and privacy policy" | Those documents are unreviewed drafts and acceptance is not recorded |
| 4 | Draft `/privacy`: staff "can produce the same data file for you, or delete the account, on request" | The routes exist in the API. No administrator exists on the preview, no written procedure exists for checking the requester's identity or sending the file, and the web screens for these routes are not in `2b0c7c1` (they are being added) |

### 3.6 What is kept, and for how long, as built

| What | Kept | Notes |
|---|---|---|
| Account data | Until the account is deleted | Deleted from the live database at once when the owner or an administrator deletes the account |
| Audit log entries | No end date. Nothing removes them | After a deletion the account's earlier entries stay, each with the account's opaque id, the action, the id of the item acted on, the request id, the **IP address** and the details (for example a settled bet's result, a followed team's id, a reminder week). One more entry records the deletion. None holds the email address. An earlier README called this "no personal data"; an IP address may be personal data |
| Daily database dumps | 14 days (`ODDVEX_BACKUP_KEEP_DAYS`) | A dump holds every account as it was then: emails, password hashes, bets. Old dumps are deleted only after a new dump succeeds. All dumps are on the same server; no copy is kept anywhere else |
| Pre-release dumps | The newest five | One is taken at every deploy, before the release's database changes are applied |
| Restore leftovers | No end date | A restore keeps a dump of the database it replaced and the replaced database itself |
| Reserved community handles | No end date | Only the handle held at the moment of deletion, only when the account is suspended then. No administrator route releases one |
| Copies of reported text | Until the report is deleted, which happens when the reporter's or the reported author's account is deleted | Kept even when the author deleted the content. Not returned to the reporter or included in their export |
| Notifications | At most 500 per user | Older ones are removed |
| Logs | No rule set | Section 3.2 |

## 4. Draft legal pages and where they live

| Page | Route | Source file | State |
|---|---|---|---|
| Terms of service | `/terms` | `apps/web/src/app/(marketing)/terms/page.tsx` | Short draft. Carries a "Preview draft" banner saying it has not been reviewed by counsel |
| Privacy policy | `/privacy` | `apps/web/src/app/(marketing)/privacy/page.tsx` | Draft with the same banner. Lists what is stored, what the export holds and leaves out, what deletion removes and what it keeps (security log entries with IP addresses, backups for about 14 days plus pre-release copies, a reserved handle in one case), and that staff can export or delete for someone who cannot sign in. States that retention is to be confirmed before launch |
| Responsible gambling | `/responsible-gambling` | `apps/web/src/app/(marketing)/responsible-gambling/page.tsx` | Gives the national helpline, 988 and 911, says the facts were checked on November 19, 2026, and names 1-800-GAMBLER as the New Jersey council's line. A draft banner covers only the "What OddVex commits to" list |
| Methodology | `/methodology` | `apps/web/src/app/(marketing)/methodology/page.tsx` | Explains the formulas. Not a legal page; relevant to claims |
| Pricing | `/pricing` | `apps/web/src/app/(marketing)/pricing/page.tsx` | Says everything in the preview is free and paid plans are planned, with nothing decided |
| Contact | `/contact` | `apps/web/src/app/(marketing)/contact/page.tsx` | Shows the address the web build is given (`support@oddvex.com` on the preview; the live page was not checked) and invites data-rights requests from people who cannot sign in |

The mobile app does not contain the terms, privacy or methodology pages. The community guidelines are served by the
API (`services/api/src/oddvex_api/community/guidelines.py`) and need the same review before the community is switched on.

Internal policy drafts that inform them, all in `docs/compliance/`: `COMPLIANCE_OVERVIEW.md` (the full issue list
with identifiers such as GB-01 used below), `PRIVACY_AND_DATA.md`, `RESPONSIBLE_GAMBLING.md`,
`SECURITY_BASELINE.md`, `INCIDENT_RESPONSE.md`, `THREAT_MODEL.md`, and the audit report
`PRE_LAUNCH_AUDIT_2026-11-19.md`. Marketing drafts: `docs/marketing/BRAND_VOICE.md` (banned claims),
`docs/marketing/APP_STORE_LISTING_DRAFT.md`, `docs/marketing/STORE_SUBMISSION_PREP.md`.

We can supply all of these as PDF, plus screenshots or a screen recording of each flow, on request.

## 5. Features with heightened legal sensitivity

Each is built. For each: what it does, exactly as implemented, and what we need to know.

### 5.1 Age attestation

| | |
|---|---|
| What it does | Sign-up on web and mobile requires ticking "I am 21 or older, and I understand OddVex provides information only and does not take bets." The API refuses registration without it and stores the time. Nothing else is checked. An administrator account made with the operator's command (`scripts/bootstrap_admin.py`) records the time it was made; running the command stands in for the tick |
| Not done | No date of birth, no identity or age verification, no location check, no age screen on public pages, no stored terms version. In the mobile app the research screens work without an account |
| Policy intent | Accounts credibly identified as under 21 are closed and their data deleted. Staff can now delete an account (section 5.7), but there is no written procedure. When a user tells the assistant they are under 21 it gives no betting information; nothing is recorded and nothing is flagged |
| Questions | Is self-attestation adequate for an information-only service? Does the answer change with affiliate links, with a paid tier, or with store distribution? Should the attestation record more (terms version, wording shown)? Is a neutral date-of-birth screen expected? What must the under-21 procedure contain, and must a statement to the assistant trigger it? Do state age-assurance or app-store age laws apply? (AG-01 to AG-05, GB-09) |

### 5.2 Weekly staking reminder and the helpline

| | |
|---|---|
| What it does | The user may set a weekly amount. When the stakes of bets **recorded in OddVex** for the current week reach it, one in-app notification is created stating the amount staked and the user's own threshold, and that confidential help is available 24 hours a day, every day, by calling 1-800-MY-RESET (1-800-697-3738) or texting 800GAM |
| Limits, stated in the product | It is a reminder and not a limit: OddVex never blocks, rejects or delays recording a bet. It sees only bets the user logs or imports. The week is Monday to Sunday in UTC, not the user's time zone. It is checked when a bet is created or imported, not when one is edited. One reminder per week at most |
| Helpline facts | The product names the National Problem Gambling Helpline, 1-800-MY-RESET (1-800-697-3738), call or text 800GAM (800426), confidential, 24 hours a day every day, in service since 2026-01-29; not an emergency service, so in a crisis call or text 988 or call 911. Checked on 2026-11-19 against the National Council on Problem Gambling's pages. Before that the product gave 1-800-GAMBLER, which is the Council on Compulsive Gambling of New Jersey's line. The facts are in one module per app (`services/api/src/oddvex_api/helpline.py`, `apps/web/src/lib/site.ts`, `apps/mobile/src/helpline.ts`) |
| Questions | Does offering this create any duty of care, or expectations associated with operator-style limit tools? Is "reminder, not a limit" wording sufficient to avoid a user reasonably relying on it as a control? Is the stored amount, or the fact a user set one, sensitive data under any state privacy law? Should the helpline wording vary by state? Should we offer or avoid a self-exclusion style account lock? (RG-Q1, RG-Q2, PR-03, AI-C6) |

### 5.3 Alerts and notification wording

| | |
|---|---|
| What it does | Only the user creates alert rules. Notifications are in-app. All wording comes from one file of templates and an automated test scans every template for banned phrases |
| Copy rules we apply | Neutral and factual. No instruction to bet. No urgency. No probabilities. Prices with an explicit sign. No promotional notifications of any kind |
| Timing caveat | An alert is evaluated when the user opens the app, and on the preview a worker also evaluates every alert every two minutes. Elsewhere there is no schedule. Delivery is in-app only, so a notification is seen only when the user opens the app |
| Questions | Could a user-set price alert be treated as an inducement or as marketing under any rule that applies to us? What changes when alerts are delivered by push or email (consent, opt-out, content limits, quiet hours)? Is our description of timing adequate to avoid a deception claim if an alert arrives late or not at all? (AD-08, ST-12, CP-01) |

### 5.4 Value screen wording

| | |
|---|---|
| What it is | A screen listing upcoming games where one sportsbook's price differs from the no-vig consensus of the other books. Games in progress are never listed, and stale prices are left out. The roadmap calls the idea a "market discrepancy / +EV screen" (INTL-09) and had placed it in M4 pending claims review. It is built on synthetic data and its switch (`value_screen`) is **on by default**, so it is visible on the preview |
| Our concern | Words such as "value", "edge" or "+EV" may read as betting advice, a pick or an implied claim of profit. On synthetic data the statement that there is no real edge rests on the test described in section 2.4 |
| Questions | Which labels are acceptable for a price-comparison fact, and which cross into advice or a performance claim? What disclaimers and substantiation are required? Is there any regime for betting-advice or tout services that such a screen could fall under? Does this differ on real data? May it stay on before review? (GB-05, AD-05, AD-06, CP-01; gate G-14; DECISION_LOG O-15) |

### 5.5 Community and user-generated content (built, switched off)

| | |
|---|---|
| What it is | Opt-in public profiles (handle and bio), structured picks posted before a game and graded automatically from the final score, comments, follows, likes, blocks and reports. No stakes, units, paid picks, links or direct messages. Text that breaks fixed content rules is rejected automatically. A leaderboard sits behind a second switch |
| Switches | `community` and `community_leaderboard`, both off by default and off on the preview. An administrator can turn them on with one request; no administrator exists on the preview. The web and mobile screens are already in the shipped code and appear as soon as the switch is on, with no new app build |
| Moderation as built | Administrators (the only staff role) see a queue of reports oldest first, with a copy of the reported text taken when the report was made. They can hide or remove content, suspend the author, and restore hidden or removed content; a restore closes every open report on that content. An author's edit to a moderated profile goes back to the queue. Moderation is on the web only. Every decision is in the audit log |
| Deletion and suspension | A user who deletes their account deletes their community content. If the account is suspended at that moment, its handle is reserved for good (section 3.6). Nothing about the email is kept, so a suspended person can return with a new address and a new handle |
| Leaderboard rule | Ranked by the lower end of each member's win-rate interval, regardless of price. Today 24 wins in 30 picks at -500 ranks above 114 in 200 at -110, although the first record loses money at a flat stake. Each row carries the average price and the flat-stake return. A decision on price is needed before the leaderboard is switched on (`docs/backlog/owner-questions.md`) |
| Not done | No reviewed guidelines (the API serves a draft), no written moderation policy, no appeals process, no staffing, no DMCA agent, no administrator route to release a reserved handle |
| Questions | What must exist before the switch may be turned on for anyone, including a closed beta? Platform liability posture and how to moderate without assuming undue liability; terms and licence grant from users; prohibited content (pick-selling, guaranteed-win claims, solicitation, user-posted affiliate links); DMCA process; whether leaderboards could be treated as contests; store requirements for apps with user content, given the screens are in the binary while switched off; may any fingerprint of an email be kept after a suspended account is deleted; retention of reserved handles and report text copies (UG-01 to UG-09, ST-08, DL-09) |

### 5.6 Affiliate and outbound sportsbook links (not built)

| | |
|---|---|
| State | **Not built. No link to any sportsbook exists anywhere in the product.** The Founder has not decided whether affiliate revenue is part of the business |
| Why it is here | It is the decision that most changes everything else: licensing or registration, advertising rules, store review, age gating, state availability |
| Questions | If pursued: which states require what, by compensation model, with what timelines and costs? Would "available in your state" filtering be required before any link? What disclosures? If not pursued: does displaying sportsbook names and prices alone raise any of the same issues? (GB-02, GB-03, GB-04, AD-04, ST-04, RG-Q4) |

### 5.7 Staff access

| | |
|---|---|
| Roles | Two: `user` and `admin`. An account holds `admin` exactly when its address is in the server's administrator list and has been confirmed. In production no address can be confirmed through the product, so the first administrator is made by an operator command (`scripts/bootstrap_admin.py`), which creates the account or takes over an existing one with its data, sets a random password and prints it once. The printed password stays in that command's container output until the container is replaced. Administrators have no second sign-in factor (D-025) |
| What administrators can do | Counts and recent audit entries; search users by part of the email or name (each search is audited as `admin.read`); suspend and lift a suspension; set a plan; turn feature switches on and off; read the audit log and the email outbox; export an account's data or delete an account on the owner's behalf; moderate community content. They cannot export or delete another administrator's account or their own |
| Export and delete on behalf | For an owner who cannot sign in. Both need a written reason, which must not contain the account's email address and is kept in the audit log as free text. Delete also needs the account's email address typed. The export is the same file as the owner's own download. No second approver is required |
| Not done | No written procedure: who may run an export or delete, how the requester's identity is checked, how the file is sent and destroyed, whether a deletion needs a second person, how long the reason text is kept. These are Founder decisions still to be written (`docs/product/SUPPORT_READINESS.md`). No administrator exists on the preview |
| Questions | What identity checks are expected before staff export or delete an account for someone who cannot sign in? Is a second approver expected? What access controls and records are expected for staff reading user lists, the audit log and unsent email content? |

### 5.8 Assistant safeguards

| | |
|---|---|
| What it does | Every message is checked against fixed patterns before any other handling (`services/api/src/oddvex_api/assistant/safeguards.py`). In order: **crisis** (self-harm or crisis language, including threats against other people) gets a reply with 988 and 911 first, then the gambling helpline, and nothing else; **under 21** gets "OddVex is for adults 21 and over, so I can't give odds, prices or any other betting information here", the helpline and the crisis sentence; **distress** about gambling (cannot stop, chasing losses, borrowed or hidden money) gets an acknowledgement, the helpline, the staking reminder and tracker described as tools, and the crisis sentence, with no prices; a request to win money back is declined and named as a warning sign. A request for a certain winner gets a fixed refusal. Every other answer ends with a sentence giving the helpline and 988 |
| Limits | It is a rule list, not a classifier. It misses some wordings; the misses found so far are listed in `KNOWN_MISSES` in `services/api/tests/test_audit_assistant_detection.py`, and the help sentence on every other answer is the safety net for them. It also shows help for some ordinary messages (`HELP_SHOWN_ANYWAY`). Nothing is remembered between messages and no message text is stored. Nothing is recorded when a user says they are under 21 (the "flag per AG-03" step of the policy is not built) |
| Questions | Is the fixed wording of the crisis, distress and under-21 replies acceptable, including the crisis reply for threats against others? Does a rule-based safeguard with known misses create exposure that a disclaimer cannot cover? A sturdier list would need real missed messages to review, which means storing what users type: what would that require? Must a statement of being under 21 lead to any action on the account? (AI-C3, AI-C6, AG-03) |

### 5.9 Replay of real past games (internal only)

| | |
|---|---|
| What it is | A mode that serves the real 2024 NFL season shifted in time, with real team and player names and results, and fictional sportsbooks with simulated prices (D-015) |
| Limits as built | The API refuses to start in this mode when it runs in production mode, so it is not on the preview. The dataset is not committed. No logos. The screens label it "Replay" |
| Questions | What licences or permissions would showing real names, results and statistics to the public need? (DL-04, DL-05, G-12) |

### 5.10 Other items to be aware of

| Item | Note |
|---|---|
| Assistant named "OddVex AI" | It is a keyword and template system with no language model. The marketing page says so. Is the name itself a claim needing substantiation? (AI-C1, AI-C4) |
| Bet tracker and auto-settlement | A ledger of bets placed elsewhere. Auto-settlement marks a tracked bet from a final score; it moves no money. Does holding betting-transaction records bring any financial-privacy regime into play? (PR-12, GB-06) |
| Mock sync | Demonstration only. Real sync would use a third-party vendor (GB-07) |
| Prop research | Historical frequency with a range, labelled "a record, not a forecast" (GB-05) |
| Account deletion and export | Self-serve and immediate. At most 10 exports an hour per account. See what is kept in section 3.6 (PR-11, PD-Q2) |
| Entitlements without billing | Accounts carry a plan of free or premium. Both plans include the same things, there is no way to buy, and only staff can change a plan. Settings shows the plan name. No price is set |
| Tracker analytics | Includes winning and losing streaks as plain statistics with a neutral note. Our responsible-gambling policy rules out streak rewards and loss-recovery messaging (RG-P3). We would like a view on whether streaks should be shown at all |
| Per-account limits | At most 5,000 bets per account; 120 bet writes a minute and 2,000 a day per user; 10 exports an hour (D-026). They bound one account, not one person: creating accounts is limited only per IP address |

## 6. Prioritized questions

Questions 1 to 12 are the consolidated list from `COMPLIANCE_OVERVIEW.md` section 12, in its order. Questions 13 to
20 come from the Founder's open questions in `ROADMAP.md` and from what was built by 2026-11-16. Questions 21 to 26
were added on 2026-11-21.

| # | Question | Refs | Blocks |
|---|---|---|---|
| 1 | Does any current or planned OddVex feature require a gaming licence, vendor registration or affiliate registration in any state? | GB-01, GB-02 | Beta |
| 2 | If affiliate revenue is pursued, what is the state-by-state path and cost, by compensation model? | GB-02; Q-03 | Founder's affiliate decision |
| 3 | Is 21+ self-attestation adequate, or is date-of-birth entry or stronger verification expected? | AG-01; Q-05 | Beta |
| 4 | Should any states be excluded or geo-restricted at launch, and is geolocation needed? | GB-03; Q-06 | Beta |
| 5 | How do Apple and Google classify an odds-information app with no wagering, and what changes if it links out to sportsbooks? | ST-01, ST-04 | Store submission |
| 6 | What do we need in Terms, Privacy Policy and Responsible gambling pages before a closed beta with real users? | CP-04, PR-01 to PR-06 | Beta |
| 7 | What contractual terms are essential in a data licence, including AI and SEO use? | DL-02; Q-02 | Provider selection |
| 8 | Is third-party sportsbook sync legally sound, and under what consent and vendor terms? | GB-07 | Real sync |
| 9 | What substantiation and disclaimers are required for projections and EV labels, and for calling the assistant "AI"? | GB-05, AI-C4 | Value screen; marketing |
| 10 | What auto-renewal design satisfies federal and the strictest state requirements today? | SB-01, SB-02 | Paid tier |
| 11 | Do GDPR or UK GDPR obligations arise from incidental EU or UK traffic, and should we geo-block? | PR-04 | Public site |
| 12 | What is the breach-notification matrix we should pre-build into incident response? | PR-10 | Beta |
| 13 | Value screen: acceptable labels, required disclaimers, and whether it may stay on before real data | Section 5.4; G-14 | Showing the screen to real users |
| 14 | Staking reminder: duty-of-care exposure, wording, data sensitivity | Section 5.2 | Beta |
| 15 | May or must we keep the 21+ attestation record, the user id, the IP address and the action details in the audit log after account deletion, and for how long? What retention applies to logs and backups? | Section 3.6; PD-Q2, PD-Q6 | Beta |
| 16 | What must be in place before the community switch is turned on for anyone? | Section 5.5 | Switching community on |
| 17 | Transactional email (verification, password reset): sender identification, footer content and any consent or record-keeping requirements before the first real send | AD-08; G-06 | First real email |
| 18 | What legal-entity details must appear in the legal pages and store listings, and are any registrations needed first? | CP-08; Q-10 | Publishing legal pages |
| 19 | May the public website go live on synthetic, fictional data with clear labelling, before a data licence exists? What labelling is sufficient? | CP-02 | Any public launch |
| 20 | Trademark clearance for "OddVex" and the tagline "Every Line. A Smarter Perspective." | DL-07 | Marketing, store listing |
| 21 | The preview API accepts sign-ups from anyone under unreviewed draft pages. Is that acceptable for a private preview, or must registration be closed or the pages finalised first? | Section 2.4 | The preview running now |
| 22 | Staff export and delete for someone who cannot sign in: identity checks, second approver, how the file is sent, how long the free-text reason is kept | Section 5.7 | First data-rights request |
| 23 | Backups hold deleted accounts for about 14 days plus pre-release copies, all on the same server: acceptable, and what must the privacy page say? | Section 3.6 | The preview running now |
| 24 | Assistant safeguards: wording of the fixed replies; exposure from known misses; whether storing user messages to improve the rules is acceptable | Section 5.8 | Beta |
| 25 | Community: email fingerprint after a suspended account is deleted (none kept today); retention of reserved handles and of report text copies | Section 5.5, 3.6 | Switching community on |
| 26 | Store listings: the community screens are in the app binary while switched off. Must they be declared as user-generated content? | Section 5.5; `STORE_SUBMISSION_PREP.md` section 3 | Store submission |

The Founder's open questions that are business decisions rather than legal ones (milestone order, sports in scope,
free and premium split, budget, the leaderboard order, the per-account limits) are in
`docs/product/DECISION_LOG.md` and `docs/backlog/owner-questions.md`.

## 7. What we will do with the answers

- Record each answer against its identifier in `COMPLIANCE_OVERVIEW.md` and change its status from Open.
- Record each resulting Founder decision in `docs/product/DECISION_LOG.md`.
- Replace the draft pages only with text counsel has approved, and remove the draft banner only then (gate G-10).
- Change no product behaviour on legal grounds without a recorded answer.

## 8. Sign-off record

To be completed by counsel and the Founder. One row per document or feature reviewed.

| Item reviewed | Version or commit reviewed | Reviewed by (name, firm) | Date | Outcome (approved / approved with changes / not approved) | Conditions or required changes | Founder acknowledgement (name, date) |
|---|---|---|---|---|---|---|
| Terms of service | | | | | | |
| Privacy policy | | | | | | |
| Responsible gambling page | | | | | | |
| Age-gating approach | | | | | | |
| Staking reminder | | | | | | |
| Alert and notification wording | | | | | | |
| Value screen wording | | | | | | |
| Assistant safeguards and fixed replies | | | | | | |
| Staff export and delete procedure | | | | | | |
| Retention (audit log, backups, reserved handles, report copies) | | | | | | |
| Community (before switching on) | | | | | | |
| Affiliate and outbound links position | | | | | | |
| State availability | | | | | | |
| Store review notes and privacy declarations | | | | | | |
| Breach-notification matrix | | | | | | |
| Transactional email content | | | | | | |
| | | | | | | |

Engagement details:

| | |
|---|---|
| Counsel engaged (name, firm, practice areas) | ____________ |
| Engagement date | ____________ |
| Packet sent on / by | ____________ |
| Version of this packet sent (commit) | ____________ |
| Follow-up call | ____________ |
