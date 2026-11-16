# OddVex — Counsel review packet

Prepared: 2026-11-16 · Prepared by: product and engineering documentation, not lawyers · Status: **ready to send
once the Founder has chosen counsel (ROADMAP Q-09). Not sent.**

> **Not legal advice.** This packet describes a product and asks questions. It reaches no legal conclusion and none
> should be read into it. Statements about law or store policy elsewhere in this repository are the team's
> unverified understanding. Everything here is for qualified counsel (US gaming, privacy, consumer protection and
> advertising, intellectual property) to review, correct and answer.

Sending this packet and acting on the answers are Founder decisions (gate G-10 in `docs/product/ROADMAP.md`).

## 1. What we are asking for

| # | Request | Needed before |
|---|---|---|
| 1 | Answers to the prioritized questions in section 6 | A closed beta with real users |
| 2 | Review and redraft of the three public legal pages in section 4 | Any real user |
| 3 | A view on the sensitive features in section 5, each of which is built or in progress | Any real user |
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
| Odds comparison | Prices for the same game from several sportsbooks side by side, the best price marked, each price with its age |
| Line movement | How a line has moved over time |
| Player prop research | Past results against a line, shown as "x of n games" with a statistical range, labelled as a record and not a forecast |
| Calculators | Odds conversion, no-vig, expected value, closing line value, parlay payout and break-even |
| Parlay research | Combined odds and payout, with a warning when legs are correlated |
| Bet tracker | A personal ledger of bets the user placed elsewhere: stake, odds, sportsbook, result, profit and loss |
| Auto-settlement | A tracked bet tied to a game can be marked won or lost from the final score |
| Mock sportsbook sync | A demonstration import from a fictional account. No real sportsbook is connected |
| Watchlist | Follow teams, players and games |
| Alerts and notifications | User-set rules (a price reaches a level, a line moves, a game is about to start, a game ends) that produce in-app notifications |
| Weekly staking reminder | A user-set amount; reaching it produces one in-app reminder a week with a helpline number |
| Assistant ("OddVex AI") | Answers a small set of question types from the product's own data. It is rule-based. No language model is connected |
| Account | Email and password, 21+ confirmation, change password, download your data, delete your account |
| Admin | A read-only overview for staff |

### 2.3 What it does not do

| Fact | Source in the repository |
|---|---|
| It does not accept, place, route or settle wagers and holds no user funds | `PROJECT_CONSTITUTION.md` section 1 |
| It has no payment, deposit, withdrawal or subscription function | `services/api/README.md` route table |
| It has no links to sportsbooks and no affiliate or referral links | Not built. See section 5.6 |
| It shows no advertising | Not built |
| It collects no sportsbook usernames or passwords | `services/api/src/oddvex_api/db/models.py`; `PRIVACY_AND_DATA.md` section 5 |
| It sends no email, push notification or text message | `services/api/README.md`, "Notifications" |
| It makes no predictions, picks or projections | `services/api/README.md` |
| It has no user-generated or community content | Not on `main`. See section 5.5 |

### 2.4 State of the build

- **All sports data is synthetic.** Teams, players, sportsbooks, prices and statistics are fictional and generated
  by the software. The interface and the API label it as synthetic.
- **Nothing is deployed.** There is no public website, no production system and no real user. No personal data has
  been collected from anyone.
- **Nothing has been bought.** No data licence, hosting, email service or store developer account exists.
- **The mobile app has never been run on a phone or simulator.** It has passed automated checks only.
- **The legal pages are drafts written by non-lawyers.**

### 2.5 What is planned and would change the analysis

| Planned | Milestone | Decided? |
|---|---|---|
| Licensed real odds, scores and statistics | M2 | No provider chosen. The Founder has deferred the choice |
| Real team, league, player and sportsbook names | M2 | No (gate G-12) |
| Real email: verification, password reset | M2 | Flows are being built to write to an internal table without sending. Sending is not approved (gate G-06). The Founder's stated preference for a provider is Resend |
| Hosting | M2 | Not approved. The Founder's stated preference is Vercel with Neon PostgreSQL |
| Push notifications | M3 | No |
| Real sportsbook account sync through a third-party vendor | M3 | No |
| Outbound or affiliate links to sportsbooks | M3 at the earliest | **No. The Founder has not decided whether affiliate revenue is part of the business** (ROADMAP Q-03) |
| Paid subscription | M4 | No prices set (gate G-07) |
| Assistant backed by a language model | M4 | No |
| Projections and backtesting | M4 | No |
| Community | M5 | Module being built behind a switch that is off by default |
| App Store and Google Play submission | M6 | No (gate G-04) |

## 3. Personal data the software handles

Taken from the database models on `main` (`services/api/src/oddvex_api/db/models.py`, commit `bdd77a5`) and the
clients. No real person's data is held today.

### 3.1 Stored in the database

| Table | Fields that are or may be personal | Notes |
|---|---|---|
| `users` | Email, display name, password hash (argon2id), role, active flag, time of 21+ confirmation, created time, time of last password change | The 21+ confirmation is a timestamp only. **No date of birth. No record of which version of the terms was accepted** |
| `bets` | Sportsbook name, bet type, sport, stake, odds, payout, profit, result, free-text notes, placed and settled times, how it was settled, source (manual or sync) | Free-text notes can contain anything the user types |
| `bet_legs` | Selection text, market, league, event, line, odds, closing odds, result | |
| `sync_connections`, `sync_import_runs` | Provider name, status, label, opaque provider state, timestamps, counts, error text | Mock provider only. No credentials |
| `watchlist_items` | Teams, players and games followed | |
| `alert_rules` | The rule: game or team, market, side, threshold, state, timestamps | |
| `notifications` | Title, body, link, kind, read time | At most 500 kept per user |
| `notification_preferences` | Which notification kinds are switched off | |
| `stake_reminders` | The weekly amount the user set; the last week a reminder was created | See section 5.2 |
| `audit_log` | User id, action, target, **IP address**, request id, small details object, time | Not linked by foreign key, so rows remain after account deletion |

### 3.2 Held elsewhere

| Where | What |
|---|---|
| Server logs | One line per request: time, method, path, status, duration, IP address. No request bodies. Retention undecided |
| Web browser | One session cookie (`ov_session`, HttpOnly). A cookie for odds format (`ov_odds`). Theme choice in browser storage |
| Mobile device | The session token, its expiry and the user profile in the operating system's secure storage. Odds format in app storage |
| Assistant | Questions are answered and not stored. The assistant route writes nothing to the database or the logs |

### 3.3 Not collected

Date of birth, government identifiers, precise or coarse location, payment details, contacts, device advertising
identifiers, sportsbook credentials, analytics events (no analytics tool is installed).

### 3.4 Being added now (in progress, unmerged, subject to change)

Seen in the working branch on 2026-11-16. Listed so the review is not out of date the day it starts.

| Addition | Personal data involved |
|---|---|
| Account status and plan | Suspended or active; free or premium (no billing) |
| Last login time, email-verified time | Timestamps on the user |
| Email verification and password-reset tokens | A table of tokens per user |
| Email outbox | Recipient address, subject and full message body of each email that would have been sent. Nothing is sent |
| Admin user management | Staff can list users, suspend them, set plan, read the audit log and read the outbox |

### 3.5 Where the drafts and the software disagree

These are ours to fix. Counsel should know about them because the draft policy cannot be finalised until they are
resolved.

| # | Document says | Software does |
|---|---|---|
| 1 | Draft `/privacy` lists account details, bets, sync connections and security logs | Also stores watchlist, alert rules, notifications, notification preferences and the staking reminder amount. Also stores IP addresses in the audit log and server logs. None is mentioned |
| 2 | Draft `/privacy`: deleting the account "removes your account, bets and sync connections immediately" | True for those, and for watchlist, alerts, notifications and the reminder. But audit rows keep the user's id and the IP address of each past action, and server logs keep IP addresses until they expire |
| 3 | `PRIVACY_AND_DATA.md` D-03 and `COMPLIANCE_OVERVIEW.md` AG-01: the 21+ confirmation is recorded "with timestamp and terms version" | Timestamp only |
| 4 | `PRIVACY_AND_DATA.md` section 4: deletion re-authenticates the user, passes through a pending state, de-identifies audit events and keeps a deletion ledger for restores | Deletion is immediate on typing DELETE, with no password prompt, no pending state, no de-identification and no ledger |
| 5 | `PRIVACY_AND_DATA.md` D-04: preferences such as odds format and time zone stored in the database | Odds format is stored in the browser or on the device. No time zone is stored |
| 6 | `PRIVACY_AND_DATA.md` D-11 and D-12: watchlists and alerts are "later" | Both are built |
| 7 | `SECURITY_BASELINE.md` AU-03 and the screen map: sign-up must not reveal whether an email is registered | Sign-up returns "an account with this email already exists" |
| 8 | Sign-up screen: "By creating an account you agree to the terms and privacy policy" | Those documents are unreviewed drafts and acceptance is not recorded |

## 4. Draft legal pages and where they live

| Page | Route | Source file | State |
|---|---|---|---|
| Terms of service | `/terms` | `apps/web/src/app/(marketing)/terms/page.tsx` | Short draft. Carries a "Preview draft" banner saying it has not been reviewed by counsel. Sections: what OddVex is; who can use it; no advice, no guarantees; preview data; your account; your content; changes |
| Privacy policy | `/privacy` | `apps/web/src/app/(marketing)/privacy/page.tsx` | Short draft with the same banner. Does not match the data model (section 3.5) |
| Responsible gambling | `/responsible-gambling` | `apps/web/src/app/(marketing)/responsible-gambling/page.tsx` | Draft. **Carries no draft banner.** Sections: get help now; signs it may be a problem; practical limits; what OddVex commits to |
| Methodology | `/methodology` | `apps/web/src/app/(marketing)/methodology/page.tsx` | Explains the formulas. Not a legal page; relevant to claims |
| Contact | `/contact` | `apps/web/src/app/(marketing)/contact/page.tsx` | Shows "A contact address is being set up" because no mailbox exists |

The mobile app does not contain the terms, privacy or methodology pages.

Internal policy drafts that inform them, all in `docs/compliance/`: `COMPLIANCE_OVERVIEW.md` (the full issue list
with identifiers such as GB-01 used below), `PRIVACY_AND_DATA.md`, `RESPONSIBLE_GAMBLING.md`,
`SECURITY_BASELINE.md`, `INCIDENT_RESPONSE.md`, `THREAT_MODEL.md`. Marketing drafts: `docs/marketing/BRAND_VOICE.md`
(banned claims), `docs/marketing/APP_STORE_LISTING_DRAFT.md`, `docs/marketing/STORE_SUBMISSION_PREP.md`.

We can supply all of these as PDF, plus screenshots or a screen recording of each flow, on request.

## 5. Features with heightened legal sensitivity

Each is built or in progress. For each: what it does, exactly as implemented, and what we need to know.

### 5.1 Age attestation

| | |
|---|---|
| What it does | Sign-up on web and mobile requires ticking "I am 21 or older, and I understand OddVex provides information only and does not take bets." The API refuses registration without it and stores the time. Nothing else is checked |
| Not done | No date of birth, no identity or age verification, no location check, no age screen on public pages, no stored terms version |
| Policy intent | Accounts credibly identified as under 21 are closed and their data deleted. There is no written procedure and no staff tool for it yet |
| Questions | Is self-attestation adequate for an information-only service? Does the answer change with affiliate links, with a paid tier, or with store distribution? Should the attestation record more (terms version, wording shown)? Is a neutral date-of-birth screen expected? What must the under-21 procedure contain? Do state age-assurance or app-store age laws apply? (AG-01 to AG-05, GB-09) |

### 5.2 Weekly staking reminder, presented as a responsible-gambling tool

| | |
|---|---|
| What it does | The user may set a weekly amount. When the stakes of bets **recorded in OddVex** for the current week reach it, one in-app notification is created stating the amount staked, the user's own threshold and that free, confidential help is available at 1-800-GAMBLER |
| Limits, stated in the product | It is a reminder and not a limit: OddVex never blocks, rejects or delays recording a bet. It sees only bets the user logs or imports. The week is Monday to Sunday in UTC, not the user's time zone. It is checked when a bet is created or imported, not when one is edited. One reminder per week at most |
| Questions | Does offering this create any duty of care, or expectations associated with operator-style limit tools? Is "reminder, not a limit" wording sufficient to avoid a user reasonably relying on it as a control? Is the stored amount, or the fact a user set one, sensitive data under any state privacy law? Should the helpline wording vary by state? Should we offer or avoid a self-exclusion style account lock? (RG-Q1, RG-Q2, PR-03, AI-C6) |

### 5.3 Alerts and notification wording

| | |
|---|---|
| What it does | Only the user creates alert rules. Notifications are in-app. All wording comes from one file of templates and an automated test scans every template for banned phrases |
| Copy rules we apply | Neutral and factual. No instruction to bet. No urgency. No probabilities. Prices with an explicit sign. No promotional notifications of any kind |
| Timing caveat | There is no background process. An alert is evaluated when the user opens the app. A start-time alert nobody opened the app for expires silently. The screens say so |
| Questions | Could a user-set price alert be treated as an inducement or as marketing under any rule that applies to us? What changes when alerts are delivered by push or email (consent, opt-out, content limits, quiet hours)? Is our description of timing adequate to avoid a deception claim if an alert arrives late or not at all? (AD-08, ST-12, CP-01) |

### 5.4 Value screen wording (in progress)

| | |
|---|---|
| What it is | A screen listing markets where one sportsbook's best price differs from the no-vig consensus of the other books. The roadmap calls the idea a "market discrepancy / +EV screen" (INTL-09) and had placed it in M4 pending claims review. It is being built now, on synthetic data |
| Our concern | Words such as "value", "edge" or "+EV" may read as betting advice, a pick or an implied claim of profit. The synthetic data has no real edge by construction |
| Questions | Which labels are acceptable for a price-comparison fact, and which cross into advice or a performance claim? What disclaimers and substantiation are required? Is there any regime for betting-advice or tout services that such a screen could fall under? Does this differ on real data? (GB-05, AD-05, AD-06, CP-01; gate G-14) |

### 5.5 Community and user-generated content (in progress, switched off)

| | |
|---|---|
| What it is | A community module is being built behind a switch that is off by default. No community feature is available to any user. Turning it on is not approved |
| Not done | No community guidelines, moderation policy, reporting or blocking flow, appeals process, staffing or DMCA agent |
| Questions | What must exist before the switch may be turned on for anyone, including a closed beta? Platform liability posture and how to moderate without assuming undue liability; terms and licence grant from users; prohibited content (pick-selling, guaranteed-win claims, solicitation, user-posted affiliate links); DMCA process; shared bet slips and privacy defaults; whether leaderboards could be treated as contests; store requirements for apps with user content (UG-01 to UG-09, ST-08, DL-09) |

### 5.6 Affiliate and outbound sportsbook links (not built)

| | |
|---|---|
| State | **Not built. No link to any sportsbook exists anywhere in the product.** The Founder has not decided whether affiliate revenue is part of the business |
| Why it is here | It is the decision that most changes everything else: licensing or registration, advertising rules, store review, age gating, state availability |
| Questions | If pursued: which states require what, by compensation model, with what timelines and costs? Would "available in your state" filtering be required before any link? What disclosures? If not pursued: does displaying sportsbook names and prices alone raise any of the same issues? (GB-02, GB-03, GB-04, AD-04, ST-04, RG-Q4) |

### 5.7 Other items to be aware of

| Item | Note |
|---|---|
| Assistant named "OddVex AI" | It is a keyword and template system with no language model. The marketing page says so. Is the name itself a claim needing substantiation? (AI-C1, AI-C4) |
| Bet tracker and auto-settlement | A ledger of bets placed elsewhere. Auto-settlement marks a tracked bet from a final score; it moves no money. Does holding betting-transaction records bring any financial-privacy regime into play? (PR-12, GB-06) |
| Mock sync | Demonstration only. Real sync would use a third-party vendor (GB-07) |
| Prop research | Historical frequency with a range, labelled "a record, not a forecast" (GB-05) |
| Account deletion and export | Self-serve and immediate. See the retained audit data in section 3.5 (PR-11, PD-Q2) |
| Entitlements without billing (in progress) | Accounts carry a plan of free or premium. Both plans currently include the same things, there is no way to buy, and only staff can change a plan. No price is set |
| Tracker analytics (in progress) | Deeper breakdowns of the user's own record, including winning and losing streaks. Our responsible-gambling policy rules out streak rewards and loss-recovery messaging (RG-P3). Showing a streak as a plain statistic is not a reward, but we would like a view on whether it should be shown at all, and how |
| Admin user management (in progress) | Staff will be able to suspend accounts and read user lists, the audit log and unsent email content. What internal access controls and records are expected? |

## 6. Prioritized questions

Questions 1 to 12 are the consolidated list from `COMPLIANCE_OVERVIEW.md` section 12, in its order. Questions 13 to
20 come from the Founder's open questions in `ROADMAP.md` and from what has been built since.

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
| 13 | Value screen: acceptable labels, required disclaimers, and whether it may ship before real data | Section 5.4; G-14 | Enabling the screen for real users |
| 14 | Staking reminder: duty-of-care exposure, wording, data sensitivity | Section 5.2 | Beta |
| 15 | May or must we keep the 21+ attestation record, the user id and the IP address in the audit log after account deletion, and for how long? What retention applies to server logs and backups? | Section 3.5; PD-Q2, PD-Q6 | Beta |
| 16 | What must be in place before the community switch is turned on for anyone? | Section 5.5 | Enabling community |
| 17 | Transactional email (verification, password reset): sender identification, footer content and any consent or record-keeping requirements before the first real send | AD-08; G-06 | First real email |
| 18 | What legal-entity details must appear in the legal pages and store listings, and are any registrations needed first? | CP-08; Q-10 | Publishing legal pages |
| 19 | May the public website go live on synthetic, fictional data with clear labelling, before a data licence exists? What labelling is sufficient? | CP-02 | Any public deployment |
| 20 | Trademark clearance for "OddVex" and the tagline "Every Line. A Smarter Perspective." | DL-07 | Marketing, store listing |

The Founder's open questions that are business decisions rather than legal ones (milestone order, sports in scope,
free and premium split, budget) are in `docs/product/DECISION_LOG.md`.

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
| Community (before enabling) | | | | | | |
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
