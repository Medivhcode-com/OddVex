# OddVex — App Store and Google Play submission preparation

Last updated: 2026-11-21 (facts checked against the code at commit `2b0c7c1` and `docs/product/DECISION_LOG.md`) ·
Status: **preparation only. Nothing has been submitted and no store build has been made.** A Google Play developer
account exists (D-018) and the app is linked to an Expo project (D-020); no Apple developer account is recorded. One
Android test build exists, made with the `preview` profile and signed with the public debug key: it is for the
Founder's own phone and must never be uploaded to a store (`apps/mobile/README.md`, "Builds"). Uploading a build,
starting any test track or changing a listing are G-04 decisions in `docs/product/ROADMAP.md`; the Founder waived the
need to ask on 2026-11-19 (D-019), which does not replace counsel's answers below.

Companion to `docs/marketing/APP_STORE_LISTING_DRAFT.md` (listing copy). This document covers everything around the
copy: accounts, questionnaires, privacy declarations, review notes, policy checks and screenshots.

> Store policies change. **Nothing in this document quotes or summarises current policy text as fact.** Section 6
> lists what to read on the stores' own current pages at submission time. Answers marked "draft for counsel" are
> our reading of our own product, to be confirmed before anything is entered in a store console.

## 1. Blockers

Nothing here can be submitted until every row is cleared.

| # | Blocker | Why it blocks | Clears when | Gate or owner |
|---|---|---|---|---|
| B-1 | **The app has not been reported as run on a device or simulator** | An Android test APK exists (`docs/product/BUILD_STATUS.md`), but nobody has recorded running it. Layout, the tab bar, modals, keyboard handling, safe areas, text scaling, screen readers and secure storage on real hardware are all unobserved (`apps/mobile/README.md`). Screenshots cannot be taken. Review will exercise all of it. An iPhone cannot use the App Store's Expo Go for this SDK 58 project (`docs/product/PHONE_TEST_GUIDE.md`) | Someone runs it on an iPhone and an Android phone and records what they find | Founder decision on device testing (O-02 in `docs/product/DECISION_LOG.md`) |
| B-2 | No production API | A store build needs an `https://` API address (`EXPO_PUBLIC_API_URL`); release builds refuse cleartext. The `production` profile in `apps/mobile/eas.json` points at `https://api.oddvex.com`, which is not deployed; only the private preview API (`https://api-preview.oddvex.com`) runs | Production environment exists | G-02, G-03 |
| B-3 | All data is synthetic | A store listing must describe the shipped app accurately. Shipping fictional data to the public, or describing data we do not have, are both decisions for the Founder and counsel | Data licence signed, or an explicit decision to submit on labelled synthetic data | G-01, G-12, G-10 |
| B-4 | Legal pages are unreviewed drafts and are not hosted | Both stores ask for a privacy policy address. The mobile app itself contains no terms or privacy page | Counsel-approved pages live at a public address | G-10, G-03 |
| B-5 | Support address not proven | `support@oddvex.com` exists (D-022) and the preview's web build is set to show it on `/contact`. That it receives mail is not verified and nobody is named to read it (O-03) | A test message received; a reader named | G-06 |
| B-6 | Apple developer account missing; legal entity details not confirmed | A Google Play developer account exists (D-018); whether it is an organisation account under the right entity is not recorded. No Apple Developer Program membership is recorded. Accounts must be under the right entity (ROADMAP Q-10) | Founder confirms entity; Apple account created; Play account checked against the entity | G-04, G-02, G-10 |
| B-7 | No production signing credentials, final icon or splash art | The EAS project (D-020), the `preview` and `production` build profiles (`apps/mobile/eas.json`) and the app identifier `com.oddvex.app` on both platforms (`apps/mobile/app.json`; it cannot change after the first store upload) exist. No signing credentials for the `production` profile are recorded as created. The `preview` profile signs with the public debug key; a phone with that build must uninstall it before installing a properly signed one (`apps/mobile/README.md`, "Builds") | Credentials created in EAS; icon and splash art made and reviewed | G-04 (signing credentials: G-09) |
| B-8 | No working password recovery | The reset and verification screens and API routes are built (`apps/mobile/src/screens/email-flows.tsx`), but the `email_flows` switch is off in production and the product sends no email, so recovery does not work end to end. A reviewer or user who forgets a password is locked out | Recovery works end to end with real email | G-06 |
| B-9 | Counsel has not confirmed how each store classifies the app | Drives the age rating, declarations and review notes | Answer to question 5 in `docs/compliance/COUNSEL_REVIEW_PACKET.md` | G-10 |
| B-10 | Mobile accessibility never tested with VoiceOver or TalkBack | Launch checklist item; also a quality bar | Tested on devices | Device testing |

## 2. Accounts and access needed

State on 2026-11-21: the Google Play developer account and the Expo project exist; nothing else in this table does.

| Item | For | Needs first | Notes |
|---|---|---|---|
| Apple Developer Program membership, organisation type | App Store; also needed to install any build on an iPhone outside a simulator | Legal entity name and details (Q-10); whatever organisation verification Apple currently requires (check the enrolment page) | Paid (G-02). None recorded |
| App Store Connect roles | Uploading, listing, review replies | Decide who holds which role. To be decided: Founder | Access to signing is production credential access (G-09) |
| Google Play Console developer account, organisation type | Google Play | Legal entity details; whatever verification Google currently requires (check the sign-up page) | **Exists** (D-018, developer ID recorded there). Account type and verification state not recorded |
| Expo account and EAS project | Building and signing | Decide free or paid plan | **Exist.** D-018 names the Expo account; D-020 links project `e1023991-d90d-446e-ad08-64280426b84f` (`extra.eas.projectId` in `apps/mobile/app.json`). `owner` is not set in `app.json` because the account name could not be confirmed, so builds must run under the account that owns the project. Build profiles in `apps/mobile/eas.json`. Plan not recorded |
| Signing certificates and keys | Both stores | Accounts above | G-09. Never in the repository. None recorded for the `production` profile; the `preview` profile uses the public debug key |
| Support email address | Both listings, review contact | Mailbox | `support@oddvex.com` exists; receiving not verified (B-5) |
| Public privacy policy and terms addresses | Both listings | Counsel-approved pages, deployed site | G-10, G-03 |
| Public account-deletion address | Google Play (see section 6) | A page reachable without the app | Not built. Web deletion today is inside the signed-in app at `/app/settings` |
| Reviewer demo account | Both | Section 5 | G-09 if created in production |

## 3. Age rating questionnaire inputs

Prepare truthful inputs. Do not try for a lower rating. The exact questions and rating tiers must be read in each
console at submission; the listing draft notes that Apple revised its tiers and that this needs re-checking.

Facts about the app as built, for whoever fills in the questionnaires. All are **draft for counsel**.

| Topic the questionnaires are expected to ask about | Fact about the build | Source |
|---|---|---|
| Real-money gambling | None. No wagers, deposits, withdrawals or payments | `PROJECT_CONSTITUTION.md` section 1 |
| Simulated gambling | None. No games of chance, no virtual currency, no play-money betting. The parlay and calculator screens compute payouts for bets the user describes; they do not simulate placing one | `apps/mobile/README.md` |
| Gambling-related information or themes | **Yes, throughout.** Sportsbook odds, betting calculators, a ledger of bets placed elsewhere | Same |
| Contests, sweepstakes, prizes | None | — |
| User-generated content, messaging between users | **Yes, in the binary, switched off.** The community screens (feed, picks with optional reasoning text, comments, profiles with a handle and bio, follows, likes, blocks, reports, leaderboard) are compiled into the app. They appear when the server's `community` switch is turned on, with no new build; the switch is off by default, and off on the preview. Report and block are in the app; moderation is done by staff on the web only. No messaging between users | `apps/mobile/src/app/(tabs)/(games)/community/`; `apps/mobile/src/components/community-gate.tsx`; `services/api/src/oddvex_api/flags/catalog.py` |
| Unrestricted web access | None. The app opens no in-app browser. Links to web-only pages from the assistant are dropped | `apps/mobile/README.md` |
| Advertising | None | — |
| In-app purchases | None | — |
| Violence, sexual content, profanity, drugs, alcohol, tobacco | None | — |
| Medical or treatment information | None. The app shows a problem-gambling helpline number | — |
| Location sharing | None. No location permission | `apps/mobile/app.json` |
| Minimum age enforced in app | 21, by self-attestation at account creation. Research screens work signed out | `apps/mobile/README.md` |
| Audience | Adults only. Not directed to children | `docs/compliance/PRIVACY_AND_DATA.md` section 9 |

Open, for counsel (COMPLIANCE_OVERVIEW ST-01, ST-02): whether each store treats the app as gambling, simulated
gambling, gambling information, or none; any country-specific rating consequence.

Note for the Founder: research screens being usable **without** an account means the 21+ confirmation does not
gate odds content in the app. Whether that is acceptable is a counsel question (AG-01, AG-02).

Open, for counsel: the stores judge the binary. Whether the community screens must be declared as user-generated
content while the server switch is off, and what filtering, reporting and blocking the stores expect if it is on at
submission (ST-08), is question 26 in `docs/compliance/COUNSEL_REVIEW_PACKET.md`.

## 4. Privacy declarations

Derived from the data model on `main` (`services/api/src/oddvex_api/db/models.py`) and the mobile client
(`apps/mobile/README.md`, `apps/mobile/app.json`). Every answer is **draft for counsel** and must be re-derived
from the shipped build at submission. Category names below are descriptive; map them to the categories each console
actually offers at the time.

Facts that apply to every row:

- No third-party SDK for analytics, advertising, crash reporting or attribution is installed in the mobile app.
- No data is used for tracking across apps or sites and none is shared with advertisers or data brokers.
- The API runs on a third-party server (Hostinger) for the preview. Whether a hosting or database vendor counts as
  "sharing" under each store's definitions is for counsel.
- Data is sent over HTTPS. Whether to declare encryption in transit depends on the deployed setup.
- Users can delete their account and data in the app (Settings, Delete account).

| Data | Collected by the app | Linked to the user | Purpose | Optional | Notes |
|---|---|---|---|---|---|
| Email address | Yes | Yes | Account, sign-in | Required for an account | |
| Name (display name) | Yes | Yes | Account | Required for an account | Free text; need not be a real name |
| User id | Yes | Yes | Account | Required | Internal id |
| Password | Yes, sent to the API; stored only as a hash | Yes | Sign-in | Required | |
| Age confirmation (21+) | Yes, as a timestamp | Yes | Eligibility | Required | Not a date of birth |
| Bet records the user enters: sportsbook, selection, odds, stake, result, notes | Yes | Yes | App functionality (tracker) | Optional feature | Which store category this falls under (user content, financial information, other) is a **counsel question**. It is a record of activity elsewhere, not payment data |
| Weekly staking reminder amount | Yes | Yes | App functionality | Optional | See counsel packet section 5.2 |
| Watchlist, alert rules, notification preferences | Yes | Yes | App functionality | Optional | |
| In-app notifications | Generated by the service | Yes | App functionality | — | Not push |
| Assistant questions | Sent to the API, not stored | No | App functionality | Optional | No language model, no third party |
| IP address | Yes, in the audit log (the user's address as forwarded by the shared reverse proxy or the web server). The API request log holds the proxy's or the web server's address on the preview, not the user's; the shared reverse proxy's own logs were not inspected | Yes, in the audit log | Security, fraud prevention | Not optional | Retained after account deletion today, with the action details, with no end date (`docs/compliance/PRIVACY_AND_DATA.md` section 3.1). This must be resolved or declared accurately |
| Account status, plan, last sign-in time, email-confirmed time | Generated by the service | Yes | App functionality, security | — | |
| Community: handle, bio, picks with optional reasoning text, comments, likes, follows, blocks, reports | Yes, when the community is switched on | Yes | App functionality (user content) | Optional (opt-in public profile) | A public profile shows the handle, bio, picks and record to other users, never the email or name. A report keeps a copy of the reported text. A suspended account's handle stays reserved after deletion |
| Product interaction, analytics | No | — | — | — | No analytics installed |
| Crash and performance diagnostics | No | — | — | — | No monitoring installed. Changes if one is added (G-13) |
| Device or advertising identifiers | No | — | — | — | |
| Push token | No | — | — | — | `expo-notifications` is not installed |
| Location, precise or coarse | No | — | — | — | No permission requested |
| Contacts, photos, camera, microphone, health, calendar | No | — | — | — | No such permission in `app.json` |
| Payment or purchase data | No | — | — | — | No purchases |
| Sportsbook credentials | No | — | — | — | Never collected |

On-device storage, for completeness: the session token, its expiry and the user profile in the operating system's
secure storage; the odds-format choice in app storage.

Built since the first version of this list: email verification state, last sign-in time, account status and plan
(rows above), and an outbox holding unsent email content (empty in production while the email flows are off). If
real email, push, analytics or crash reporting is added, each adds rows and a sub-processor (G-13).

Tracking position: none. If any SDK changes that, the Founder must approve it (G-13) and the declarations and any
required prompt must be updated before the next submission.

## 5. Review notes and demo account

### 5.1 Review notes template

Complete truthfully at submission. Delete every line that is not true of the submitted build. The older template in
`APP_STORE_LISTING_DRAFT.md` section 5 predates the mobile build and should be replaced by this one.

```
OddVex is a sports-betting information and analytics app for adults 21 and over.

What it does not do
- It does not accept, place or facilitate wagers. There is no real-money
  gambling, no deposits, no withdrawals and no payments of any kind.
- It contains no links to sportsbooks and no affiliate links.
- It shows no advertising and has no in-app purchases.

What it does
- Compares odds across sportsbooks, shows player-prop history, and provides
  betting-math calculators.
- Lets a user keep a personal record of bets they placed elsewhere.
- Lets a user set alerts. Alerts appear inside the app only. The app sends
  no push notifications.
- "OddVex AI" answers a fixed set of question types from the app's own data
  using rules and templates. [It does not use a language model.]
- [If the community is switched on: users can post structured picks,
  comments and a profile; other users can report or block them, and
  staff review reports.]

Data shown in the app
- [Odds, scores and statistics are provided by ______ under licence.]
- [OR: All teams, players, sportsbooks and prices in this build are
  fictional sample data, and every screen is labelled "Synthetic data".]

Sportsbook sync
- [The "connect a sportsbook" feature in this build is a demonstration that
  imports sample bets from a fictional account. It asks for no credentials
  and contacts no sportsbook.]

Accounts
- Creating an account requires confirming the user is 21 or older.
- Odds, props and calculators can be viewed without an account. The bet
  tracker, watchlist and alerts need one.
- Account deletion: Settings tab > Delete account > type DELETE.

Demo account
  Email:    ______
  Password: ______
  The demo account contains sample bets, alert rules and notifications.

Contact for review questions
  Name:  ______
  Phone: ______
  Email: ______
```

### 5.2 Demo account approach

What exists: `services/api/scripts/seed_demo.py` creates `demo@oddvex.test` with sample bets, alert rules and
notifications. It is a development convenience. Its default password is published in the repository.

Options for a reviewer account. To be decided: Founder (G-04; G-09 because it creates a known credential in
production).

| Option | How | For | Against |
|---|---|---|---|
| A. Seeded demo account in production | Run the seed script with `--allow-production` and a strong, private `ODDVEX_DEMO_PASSWORD` | Reviewer sees a full tracker immediately | A standing shared account in production. The script refuses production by default for that reason. The password must be rotated after review. The `.test` address cannot receive email |
| B. Ordinary account made by hand | Register a normal account on a mailbox we control and log a few sample bets | No special path; behaves like a real user | Manual; data must be re-entered if it is deleted |
| C. Reviewer signs up themselves | Notes tell the reviewer to create an account | Nothing to maintain | Reviewer sees an empty tracker. If email verification is enforced by then, they need a working mailbox |

Whichever is chosen:

- [ ] The password is unique, strong, stored only in the store console and the team's secret store
- [ ] The account is not an admin
- [ ] The reviewer can reach every screen in section 7 with it
- [ ] If the reviewer deletes the account (it is a visible button), there is a way to restore it quickly
- [ ] The password is changed after each review cycle
- [ ] Sample data in it is fictional or licensed

## 6. Policy points to confirm against the stores' current published policies

A reading list, not a summary. For each: open the store's current official page, read the section, record the date
read and what it requires of this app. Our understanding in `docs/compliance/COMPLIANCE_OVERVIEW.md` section 4 is
unverified. Owner: to be decided (Founder to assign); counsel for classification questions.

### Apple (App Review Guidelines and App Store Connect help)

| # | What to check | Why it matters here | Read on (date) | Finding |
|---|---|---|---|---|
| AP-1 | The gambling and gaming sections: how an app that shows odds and betting tools but takes no wagers is treated; any licensing, geo-restriction or free-app conditions | Classification (ST-01) | | |
| AP-2 | Whether odds comparison, bet tracking or betting calculators count as simulated gambling or gambling-related content for the age rating | Rating (ST-02) | | |
| AP-3 | Current age rating tiers and questionnaire | Section 3 | | |
| AP-4 | Account deletion requirement for apps that allow account creation: what "in-app" must include | Deletion is in Settings; confirm it satisfies the wording (ST-05) | | |
| AP-5 | Whether account creation may be required, and treatment of features available without sign-in | Research works signed out | | |
| AP-6 | Privacy policy link requirements, in the listing and in the app | The app has no in-app privacy page | | |
| AP-7 | App privacy details definitions: "collected", "linked", "tracking", and how server-side IP logging is treated | Section 4 | | |
| AP-8 | App Tracking Transparency: when a prompt is required | We believe none; confirm | | |
| AP-9 | Demo account and review information requirements | Section 5 | | |
| AP-10 | Metadata accuracy, screenshots, use of placeholder or sample data in a shipped app | Synthetic data (B-3) | | |
| AP-11 | Minimum functionality and "beta, demo or test" app rules | A build on fictional data may be treated as a demo | | |
| AP-12 | Export compliance questions about encryption | The app uses the operating system's HTTPS and secure storage only; answer per the current questionnaire | | |
| AP-13 | Rules on apps that describe themselves as AI or include an assistant | "OddVex AI" is rule-based (ST-09) | | |
| AP-14 | User-generated content rules | The community screens are in the binary behind a server switch; read the rules for that case, not only for an app with the community on (ST-08) | | |
| AP-15 | In-app purchase rules for digital subscriptions | Only if a paid tier ships (ST-07) | | |
| AP-16 | Rules on links out of the app to gambling operators | No links today; needed for the affiliate decision (ST-04) | | |
| AP-17 | TestFlight external testing: review and tester rules | Any beta (G-04) | | |

### Google Play (Developer Program Policies and Play Console help)

| # | What to check | Why it matters here | Read on (date) | Finding |
|---|---|---|---|---|
| GP-1 | Real-money gambling, games and contests policy: scope, and whether an odds-information app with no wagering falls inside it; any application or declaration form | Classification (ST-01, ST-14) | | |
| GP-2 | Rules on gambling-related ads or links to operators inside apps | No ads or links today (ST-04) | | |
| GP-3 | Content rating questionnaire (IARC): gambling-related questions | Section 3 | | |
| GP-4 | Target audience and content settings for adult-only apps | Adults only | | |
| GP-5 | Data safety form definitions: "collected", "shared", "processed ephemerally", service-provider exceptions, encryption in transit, deletion request | Section 4 | | |
| GP-6 | Account deletion requirement: in-app path **and** a web address that works without the app | **No such web page exists.** It would need building | | |
| GP-7 | Privacy policy requirements | B-4 | | |
| GP-8 | Testing requirements for new developer accounts before production access, by account type | Affects the timeline. Do not assume numbers; read the current rule | | |
| GP-9 | Target API level and other technical requirements for new apps | Expo SDK 58; check what it targets against the current requirement | | |
| GP-10 | Deceptive behaviour and metadata rules; sample or placeholder data | Synthetic data (B-3) | | |
| GP-11 | AI-generated content policy | Assistant naming (ST-09) | | |
| GP-12 | User-generated content policy | The community screens are in the binary behind a server switch (ST-08) | | |
| GP-13 | Payments policy for subscriptions | Only if a paid tier ships | | |
| GP-14 | Organisation account verification requirements | B-6 | | |

### Both

- [ ] Country availability set per Founder decision (United States only unless decided otherwise; ST-03)
- [ ] Any state-level availability question answered by counsel first (ROADMAP Q-06)
- [ ] Listing copy re-checked against `BRAND_VOICE.md` banned claims and against what the build actually contains

## 7. Screenshot list mapped to real screens

Screens below exist in `apps/mobile/src/screens` and are described in `apps/mobile/README.md`. **None can be
captured until the app has run on a device or simulator (B-1).** Captions are from the listing draft and need
counsel and Founder approval with the rest of the listing (G-04, G-05).

Rules: real app UI only; fictional or licensed data only; the "Synthetic data" badge stays visible if the data is
synthetic; show at least one loss in the tracker; no screenshot of a feature absent from the submitted build.

| # | Screen (route) | What to show | Draft caption | Built in mobile | Check before capture |
|---|---|---|---|---|---|
| 1 | Game detail (`/event/[id]`) | One row per sportsbook, the word "Best" on the best price, freshness, no-vig consensus | "Every line, side by side" | Yes | Fictional names fit the row without truncation |
| 2 | Games tab (`/`) | Live, upcoming and final groups, league chips, best moneyline per side | "Scores and prices together" | Yes | Header layout with the bell and the data badge |
| 3 | Prop analyzer (`/player/[id]`) | "x of n games", the range, the game-log bars labelled Over, Under, Push, "A record, not a forecast" | "Props, backed by history" | Yes | Chart renders; labels readable |
| 4 | Tools tab (`/tools`) | A calculator with "Show the working" open | "Run the numbers" | Yes | Keyboard does not cover the result |
| 5 | Parlay research (`/parlay`) | Combined odds, payout, break-even, the correlation warning | "Understand the whole parlay" | Yes | Warning visible in frame |
| 6 | Tracker tab (`/tracker`) | Profit, ROI, record, open and settled bets including a loss | "Your record, honestly" | Yes | A negative number is shown |
| 7 | OddVex AI (`/assistant`) | An answer with its sources line and disclaimer | "Answers with sources" | Yes | Do not imply a language model |
| 8 | Notifications, Alerts segment (`/notifications?tab=alerts`) | Rules grouped Active, Triggered, Paused, Expired | To be written | Yes | Wording must not suggest real-time or push delivery |
| 9 | Settings tab (`/settings`) | Responsible-gambling line, staking reminder ("a reminder, not a limit"), delete account | "Information, never pressure" | Yes | Helpline number correct |

Not available as mobile screens: the web odds board, line-movement charts, the profit chart and breakdowns, data
export, community moderation, and the terms, privacy and methodology pages. Do not show web screens in a mobile
listing. Community screens exist but are switched off; do not show them unless the community is on in the submitted
configuration.

Sizes and counts required per device class: read in each console at submission. `app.json` sets
`supportsTablet: false`, so no iPad set is expected; confirm.

Still to produce: final app icon, splash art, Play feature graphic. None exists in final form.

## 8. Technical readiness for a store build

| Item | State | Source |
|---|---|---|
| JavaScript bundles for iOS and Android | Bundled in CI | `mobile` job, `export:check`. Proves the code compiles, not that a native app launches |
| Native build | One Android APK from the `preview` profile (EAS build `e0686e6b-192e-460a-a60b-647ad97f7591`, commit `9bb7677`), signed with the public debug key; not for a store. No iOS build, no store build | `docs/product/BUILD_STATUS.md`; `apps/mobile/README.md` |
| EAS project and build profiles | Project linked (`extra.eas.projectId`); profiles `base`, `preview` (Android APK, internal distribution, preview API) and `production` (store builds, version raised automatically, API `https://api.oddvex.com`) | `apps/mobile/app.json`; `apps/mobile/eas.json` |
| Bundle identifier and Android package name | `com.oddvex.app` on both platforms. Cannot change after the first store upload | `apps/mobile/app.json` |
| Version | `0.1.0`. Build numbers are kept by EAS (`appVersionSource: remote`) and raised automatically for `production` builds (`autoIncrement`) | `apps/mobile/app.json`; `apps/mobile/eas.json` |
| Permissions requested | None beyond defaults | `apps/mobile/app.json` |
| Push | Not installed | `apps/mobile/README.md` |
| Over-the-air updates | Not configured | Same |
| Crash reporting | None | G-02, G-13 to add |
| API address | Build-time `EXPO_PUBLIC_API_URL`; must be `https://` | Same |
| Password recovery | Built, switched off in production (`email_flows`), sends nothing: does not work end to end (B-8) | `services/api/README.md`; `services/api/src/oddvex_api/flags/catalog.py` |

## 9. Sequence once approvals exist

1. Device testing on at least one iPhone and one Android phone; fix what it finds (B-1, B-10). Steps: `docs/product/PHONE_TEST_GUIDE.md`.
2. Counsel answers on classification, age gating and the legal pages (B-4, B-9).
3. Production API and site live (B-2); support mailbox live (B-5).
4. Founder approves developer accounts (G-04, G-02); entity details confirmed (B-6).
5. Read every item in section 6 and record findings.
6. Build configuration, signing, icons (B-7).
7. Internal testing track on each store (G-04).
8. Complete questionnaires and privacy declarations from the shipped build; counsel reviews.
9. Capture screenshots from the shipped build.
10. Founder approves submission, recorded in `docs/product/DECISION_LOG.md` (G-04).

## 10. Known disagreements with the listing draft

`APP_STORE_LISTING_DRAFT.md` was written before the mobile app reached parity and should be updated before use:

| Listing draft says | Now |
|---|---|
| "The mobile app in M1 covers games + odds only" | Props, calculators, parlay research, tracker, mock sync, watchlist, alerts, assistant and account settings are built (`apps/mobile/README.md`), none verified on a device |
| Screenshot storyboard marks props, calculators, parlay and tracker as M3 and the assistant as M4 | Built |
| Description mentions "Optional sync through authorized partners" | Mock only. Remove unless a real vendor ships |
| Description mentions breakdowns "by sport, sportsbook and market" | Web only; not in the mobile build |
| Description mentions "American, decimal or implied-probability view" | The mobile setting is an odds format choice; confirm on a device what is offered before claiming it |
| Play "Account deletion URL: web deletion page (to be built)" | Still not built |
| Privacy label inputs list analytics, diagnostics and push token as intended | None is installed |
