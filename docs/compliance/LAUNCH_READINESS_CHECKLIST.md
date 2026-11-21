# OddVex — Launch Readiness Checklist

Last updated: 2026-11-21

**Status: NOT READY FOR LAUNCH.** Everything runs on synthetic data. A private preview runs in production mode on a Hostinger server (`docs/product/DECISION_LOG.md`, D-021): the web preview is behind a password, and the API at `api-preview.oddvex.com` is open and accepts sign-ups from anyone, so real email addresses may already be stored. Whether anyone outside the team has signed up cannot be seen from the repository. There is no legal review, no public launch and no store submission. A Google Play developer account exists (D-018). One Android test build exists; the mobile app has not been reported as run on a device.

Rows changed on 2026-11-21 were checked against the code at commit `2b0c7c1` and the server records in `docs/product/BUILD_STATUS.md`; the audit of 2026-11-19 is in `PRE_LAUNCH_AUDIT_2026-11-19.md`.

"Launch" = public availability to real users (M6). Sub-gates: **[B]** = also required before a closed beta with real users (M2). **[F]** = Founder approval gate. **[C]** = counsel sign-off required. Gates G-01 to G-14 are defined in `docs/product/ROADMAP.md`.

How boxes are ticked:

- A box is ticked only when a file or CI job in this repository shows it is true. The Evidence column names it.
- Ticks made on 2026-11-16 were made by a documentation pass reading the repository. They show that a check **exists and is configured**; test results are those recorded in `docs/product/BUILD_STATUS.md`. Nothing was re-run for this update and the status of CI runs on GitHub was not re-checked. The Founder or an engineer should countersign in section 13.
- Where an original item bundled something provable with something not yet done, it is split into two rows so the unproven half stays open. Rows marked "(added 2026-11-16)" are new.
- "None" in the Evidence column means nothing exists yet. The last column names the approval gate, or the next step where no gate applies.

## 0. Trivially true today

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [x] | Product does not accept, place or route wagers and holds no user funds (by design; must be re-confirmed at each release) | `PROJECT_CONSTITUTION.md` section 1; no payment, wallet or bet-placement route in `services/api/README.md` route table | Re-confirm each release |
| [ ] | No real customer data has been collected | Unticked 2026-11-21. Unknown: the preview API accepts sign-ups from anyone and stores email addresses, password hashes and IP addresses (`docs/product/BUILD_STATUS.md`, "Private preview on the Hostinger VPS"). The repository cannot show whether anyone outside the team has registered | Check the preview's `users` table, or close registration on the preview (a code change) |
| [x] | No paid data provider, no new paid infrastructure and no store submission has been initiated | `docs/product/DECISION_LOG.md` standing-facts table (G-01, G-02, G-04). The preview uses a server the Founder already paid for (D-016) | — |

## 1. Legal sign-offs [C] [F]

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Qualified counsel engaged (gaming, privacy, consumer protection/advertising, IP) [B] | None. Packet reissued on 2026-11-21 from the code at `2b0c7c1` and not sent: `COUNSEL_REVIEW_PACKET.md` (its section 0 lists what changed since the version marked ready on 2026-11-16) | G-10; ROADMAP Q-09 |
| [ ] | Written confirmation of licensing/registration position for the launch feature set, state by state (GB-01) [B] | None | G-10 |
| [ ] | Affiliate decision made; if yes, required state registrations/licences obtained before any affiliate link goes live (GB-02) | None. Affiliate links are not built | G-10, G-11; ROADMAP Q-03 |
| [ ] | State availability decision recorded (any excluded/geo-restricted states) (GB-03) [B] | None | G-10; ROADMAP Q-06 |
| [ ] | Terms of Service final and approved [B] | Draft with banner: `apps/web/src/app/(marketing)/terms/page.tsx` | G-10 |
| [ ] | Privacy Policy final and approved; matches actual data practices [B] | Draft with banner: `apps/web/src/app/(marketing)/privacy/page.tsx`. Since `2b0c7c1` it lists what is stored, what the export leaves out and what deletion keeps (security log with IP addresses, backups, a reserved handle). It promises staff export and delete for people who cannot sign in, for which no procedure is written. Not reviewed | G-10 |
| [ ] | Responsible Gambling page approved; helpline details verified [B] | Page exists: `apps/web/src/app/(marketing)/responsible-gambling/page.tsx`. Helpline facts checked by the build session on 2026-11-19 against the National Council on Problem Gambling's pages (1-800-MY-RESET, text 800GAM, 988, 911); not reviewed by counsel. A draft banner covers only the commitments list | G-10 |
| [ ] | Age-gating approach approved (AG-01) [B] | Self-attestation built: `services/api/src/oddvex_api/auth/schemas.py` | G-10; ROADMAP Q-05 |
| [ ] | Advertising/marketing rules memo received; banned-claims list confirmed (AD-01…AD-10) | None | G-10 |
| [ ] | Data licence reviewed and signed (DL-01, DL-02) [B] | None. No provider chosen | G-01, G-10 |
| [ ] | Sync vendor agreement and consent language reviewed (if sync ships) (GB-07) | None. Mock provider only | G-01, G-10 |
| [ ] | Auto-renewal/subscription flows reviewed (if Premium ships) (SB-01…SB-07) | None. No billing built | G-07, G-10 |
| [ ] | AI disclosure and disclaimers reviewed (AI-C1…AI-C4) | None. Assistant is rule-based | G-10 |
| [ ] | UGC terms, guidelines and DMCA process reviewed (if community ships) | None. Community is built behind the `community` switch, off by default and on the preview; the screens are in the web and mobile code. Draft guidelines in `services/api/src/oddvex_api/community/guidelines.py` | G-10 |
| [ ] | Trademark clearance for "OddVex" and tagline (DL-07) | None | G-10 |
| [ ] | Policy on real team/league/player/sportsbook names and logos approved (G-12) [B] | None. Fixtures are fictional | G-12, G-10 |
| [ ] | Breach-notification matrix on file (PR-10) [B] | None | G-10 |
| [ ] | Legal entity, business registrations, tax and insurance confirmed (CP-08) | None | G-10; ROADMAP Q-10 |
| [ ] | Legal sign-off record stored (who, date, scope, version of documents reviewed) | Blank table: `COUNSEL_REVIEW_PACKET.md` section 8 | G-10 |

## 2. Product boundary and honesty

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Re-verified: no wagering, no funds, no bet-slip execution hand-off in any surface | Design intent holds in code today; no formal re-verification recorded | Product review each release |
| [ ] | No synthetic/demo data presented as real anywhere in the launch build; or demo surfaces clearly labelled [B] | Partial: `data_mode: "synthetic"` on API responses; "Synthetic data" badge on mobile (`apps/mobile/README.md`). No launch build exists | G-01, G-03, G-12 |
| [ ] | Every odds/score/stat block shows "as of"; stale handling verified against real feed interruptions [B] | Partial: freshness and stale flags come from the API (ADR-0002). No real feed to verify against | G-01 |
| [ ] | "Best line" logic verified against real multi-book data; commercial relationships do not influence it (or are disclosed) | Logic tested on synthetic data only (`services/api/tests/test_board.py`) | G-01 |
| [ ] | Features described as "planned" are not marketed as available | Not audited in this pass. `docs/marketing/APP_STORE_LISTING_DRAFT.md` describes the intended set, not the built set | Product review; G-05 |
| [ ] | `/methodology` matches implemented formulas and data sources | Not audited in this pass | Engineering review |
| [ ] | No accuracy, performance or results claims without substantiation and counsel review (G-14) | No such claims found in docs reviewed; no formal copy audit recorded | G-14, G-10 |

## 3. Responsible gambling

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | RG short line (21+, National Problem Gambling Helpline 1-800-MY-RESET) on every web, marketing and mobile surface [B] | Partial: web marketing footer and app shell at every width (`apps/web/src/lib/site.ts`, `RESPONSIBLE_GAMBLING_LINE`; `apps/web/e2e/marketing.spec.ts`). Mobile: Settings, the tracker in every state and the sync panel (`apps/mobile/src/helpline.ts`); not reported as seen on a device | Mobile device testing; G-10 |
| [ ] | 21+ gate enforced at signup on web and mobile [B] | Partial: API rejects registration without `age_confirmed` (`auth/schemas.py`); web and mobile forms require it. Mobile unverified on a device. Method not approved | G-10 (AG-01) |
| [ ] | `/responsible-gambling` live and linked from app settings [B] | Page built and linked from web Settings; on the private preview behind its password. Not public. Mobile links to the Council's site instead | G-03, G-10 |
| [ ] | Assistant distress/guarantee/under-21 behaviours tested [B] | Rules in `services/api/src/oddvex_api/assistant/safeguards.py`, tested in `services/api/tests/test_audit_assistant_detection.py` and `services/api/tests/test_audit_assistant_support.py`. Known misses listed in `KNOWN_MISSES`; the help sentence on every other answer covers them. The AG-03 flag for under-21 users is not built. No counsel or RG review | G-10; RG review |
| [ ] | Notification copy reviewed for inducement (if notifications ship) | Automated banned-phrase scan only: `services/api/tests/test_notification_copy.py`. No human or counsel review | G-10 |
| [ ] | Tracker shows losses plainly; no celebratory or chasing prompts [B] | Built; no review recorded | Product and RG review |
| [ ] | Parlay screen shows the break-even rate with the payout, and the correlation warning | Break-even rate and same-game warning shown on web and mobile. No combined probability that every leg wins is shown (at `2b0c7c1` the screen reads "Combined probability: Not shown"; pull request 20 replaces it). Warning asserted in `apps/web/e2e/app.spec.ts`. No RG review recorded | Product and RG review |
| [ ] | All copy passes BRAND_VOICE banned-claims check [B] | Banned-phrase tests on notification templates, community copy, marketing copy and assistant replies. No full copy audit | Product review; G-10 |
| [ ] | No goals/KPIs tied to amount wagered or bet count | No analytics or KPIs exist | Founder |

## 4. Privacy and data

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Data inventory reconciled with actual implementation and vendors [B] | Reconciled with the code at `2b0c7c1` on 2026-11-21 (`PRIVACY_AND_DATA.md` section 2 and 3.1). Remaining mismatches with the design intent: `COUNSEL_REVIEW_PACKET.md` section 3.5. Hostinger's role as host is a counsel question | Engineering + G-10 |
| [x] | Self-serve account deletion works end to end on web and API [B] | `DELETE /v1/me` (`auth/router.py`, `services/api/src/oddvex_api/account/service.py`); web test "delete account removes access" in `apps/web/e2e/app.spec.ts`; cascades in `db/models.py`. Audit rows keep the user id, IP address and action details with no end date, and backups keep the account for about 14 days plus pre-deploy copies (`PRIVACY_AND_DATA.md` section 3.1) | Retention decision (counsel) |
| [ ] | Self-serve account deletion verified in the mobile apps on a device [B] | Built with component tests; not reported as run on a device | Mobile device testing (Founder decision) |
| [x] | Data export works [B] | `GET /v1/me/export`; `services/api/tests/test_api_account.py`; web test "export downloads my data without any password material" in `apps/web/e2e/app.spec.ts`. Web and API only: the mobile app has no export (`apps/mobile/README.md`) | — |
| [ ] | Retention schedule implemented (logs, backups, analytics) [B] | Partial: daily dumps kept 14 days and the newest five pre-deploy dumps (`infrastructure/hostinger/compose.yaml`, `infrastructure/hostinger/ops.sh`); notifications capped at 500 per user. Audit log, reserved handles, report text copies and logs have no end date | G-10; G-02 |
| [ ] | Sub-processor list published; DPAs signed with each vendor [B] | None engaged | G-02, G-13, G-10 |
| [ ] | Analytics events audited: no emails, stakes, notes or assistant text [B] | No analytics instrumented | G-02, G-13 |
| [ ] | Cookie/consent approach implemented per counsel | None. Web sets a session cookie and stores theme and odds format in the browser | G-10 |
| [ ] | Privacy contact mailbox live and monitored [B] [F] | `support@oddvex.com` exists and the preview's web build is set to show it on `/contact` (D-022; live page not checked). That it receives mail is not verified; who reads it is not decided (O-03). No separate privacy address | G-06 |
| [ ] | No sportsbook credentials collected or stored anywhere (code + UI audit) | No credential field in `db/models.py` (`sync_connections.provider_state` is documented "never credentials"); mock sync only. No formal code and UI audit recorded | Engineering audit |
| [ ] | Sync tokens encrypted; disconnect revokes at vendor (if sync ships) | Not applicable until a vendor exists | G-01 |
| [ ] | LLM provider terms confirm no training on OddVex data and acceptable retention (if LLM ships) | Not applicable: no model connected | G-01 |
| [ ] | Process for suspected under-21 accounts documented [B] | Policy line in `PRIVACY_AND_DATA.md` section 9. An administrator delete route exists (`POST /v1/admin/users/{user_id}/delete`); no documented procedure, and no administrator exists on the preview | G-10 (AG-03) |

## 5. Security

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | SECURITY_BASELINE M1 verification checklist complete [B] | Not completed. Gaps listed in `THREAT_MODEL.md` (AU-03, AU-04, AU-06, DS-01, DS-02) | Engineering |
| [ ] | All M2+ baseline controls implemented for production [B] | None | G-02, G-09 |
| [ ] | Admin accounts use MFA; admin actions audit-logged [B] | No MFA exists. Admin actions, user searches (`admin.read`) and role changes (`role.granted`, `role.removed`) are audited since `2b0c7c1` (`services/api/src/oddvex_api/api/admin.py`, `services/api/src/oddvex_api/deps.py`) | Engineering; O-12 |
| [ ] | Secrets in a managed store [B] | None | G-02, G-09 |
| [x] | Secret scan runs in CI over full git history [B] | `secrets` job (gitleaks, `fetch-depth: 0`) in `.github/workflows/ci.yml`. Job result on GitHub not re-checked in this pass | — |
| [ ] | Dependency, secret and static scans clean or exceptions risk-accepted [B] | Secret scan, lint and the dependency audit job (`audit` in `.github/workflows/ci.yml`: `pnpm audit` at high and above, `pip-audit`) run in CI on `main` (D-012). No static security analysis | Founder to confirm thresholds and exceptions (O-01) |
| [ ] | Rate limiting and abuse controls load-tested [B] | Unit and API tests only. Per-IP, per-network, per-email and per-user limits exist (`services/api/src/oddvex_api/ratelimit.py`); residual risks in `THREAT_MODEL.md` S-1 and S-6. Not load-tested | G-02 |
| [ ] | Backups automated; restore test passed with recorded RTO/RPO [B] | Partial: a daily dump on the preview server since 2026-11-19, kept 14 days, plus a dump before each deploy. All on the same server. A restore is rehearsed only in tests, not on the server. No RTO or RPO set (O-11) | G-02 |
| [ ] | Independent penetration test completed; findings resolved or risk-accepted by Founder [F] | None | G-02 |
| [ ] | Security contact and `security.txt` published | None | G-06 |
| [ ] | Access review complete; least privilege confirmed [B] | The preview server holds a generated database password, JWT secret and preview password (D-021). No product administrator exists there. `CODEOWNERS` names a placeholder team | G-09; Founder decision (CODEOWNERS, branch protection) |

## 6. Reliability and operations

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Production environment provisioned and documented [B] [F] | A private preview in production mode on the Hostinger server, documented in `infrastructure/hostinger/README.md`. No public production on `oddvex.com` | G-02, G-03 |
| [ ] | Staging mirrors production; deploy and rollback rehearsed [B] | No staging. Deploys have run on the preview (`docs/product/BUILD_STATUS.md`); a rollback and the automatic put-back have not been exercised on the server (`infrastructure/ROLLBACK_PLAN.md`) | G-02 |
| [ ] | Monitoring, alerting and on-call roster active [B] | None. Template with blanks: `infrastructure/RUNBOOK.md` section 12 | G-02 |
| [ ] | Data freshness monitors and feed kill switches in place [B] | None | G-01, G-02 |
| [ ] | Feature flags / kill switches for assistant, sync, alerts | Flags exist for community, the leaderboard, the value screen, tracker analytics, email flows and premium gating (`services/api/src/oddvex_api/flags/catalog.py`). None switches off the assistant, sync or alerts | Engineering |
| [ ] | Incident response tabletop completed [B] | None | Founder |
| [ ] | Load test at expected launch traffic (targets to be set) | None; targets not set | G-02 |
| [ ] | Performance budgets met on reference devices (NFR-20…NFR-25) | Not measured | Mobile device testing |
| [ ] | Status page or in-app incident banner available | None | G-02 |
| [ ] | Database migration plan reviewed; no pending destructive migrations without approval [F] | Plan written, not reviewed: `infrastructure/DEPLOYMENT_PLAN.md` section 6. Revisions 0001 to 0007 are additive and applied on the preview | G-08 |
| [ ] | Cost monitoring and budget alerts configured [F] | None | G-02; ROADMAP Q-07 |
| [x] | Docker images for API and web build and answer requests in CI (added 2026-11-16) | `docker` job in `.github/workflows/ci.yml`. `docker-compose.yml` itself has not been started | — |

## 7. Quality and accessibility

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | All M1…launch-scope acceptance criteria in the PRD verified | Not audited | Engineering + product |
| [x] | Automated test suites run in CI for API, web, mobile and end to end [B] | `api`, `api-postgres`, `web`, `mobile`, `e2e` jobs in `.github/workflows/ci.yml`; results recorded in `docs/product/BUILD_STATUS.md`. Not re-run in this pass | — |
| [ ] | Critical user journeys (J1–J10) covered end to end [B] | Not mapped journey by journey | Engineering review |
| [ ] | Calculator reference vectors pass on web, API, assistant and mobile [B] | API: `services/api/tests/quant/`. Web and mobile compute nothing and call the API. Not verified per surface | Engineering review |
| [ ] | Assistant grounding test: 100 % of numbers traceable to tool output [B] | `services/api/tests/test_api_assistant.py` exists; the 100 % claim is not audited in this pass | Engineering review |
| [x] | WCAG A and AA automated checks on web, dark and light themes | `apps/web/e2e/a11y.spec.ts` (axe), run by the `e2e` job | — |
| [ ] | WCAG 2.2 AA manual audit with a screen reader and keyboard; issues resolved or documented | None (`BUILD_STATUS.md`, "Not verified") | Engineering; G-02 if an external audit is bought |
| [ ] | Mobile a11y pass (VoiceOver, TalkBack, font scaling, contrast, targets) | None. The app has not been reported as run on a device or simulator | Mobile device testing (Founder decision) |
| [ ] | Cross-browser/device matrix tested | Chromium only, desktop and phone viewports (`ci.yml` installs `chromium`) | Engineering |
| [ ] | All screens implement loading / empty / stale / error states | Not audited per screen | Engineering review |
| [ ] | Copy review complete (US English, tone, no placeholder text) | None | Product; G-10 |
| [ ] | 404/500 pages and offline states verified | `apps/web/src/app/not-found.tsx`, `apps/web/src/app/app/error.tsx` exist. Mobile offline unobserved | Mobile device testing |
| [x] | API test suite runs on PostgreSQL in CI (added 2026-11-16) | `api-postgres` job (PostgreSQL 16) in `.github/workflows/ci.yml` | — |
| [x] | Generated API types and committed OpenAPI schema are checked for drift in CI (added 2026-11-16) | `api` and `web` jobs in `.github/workflows/ci.yml` | — |

## 8. Store-submission preparation [F]

**Apple App Store**

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Organisation developer account under the correct legal entity | None | G-04, G-02 |
| [ ] | Current App Review Guidelines re-read (gambling, account deletion, subscriptions, UGC, privacy sections) and gaps closed | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | App Review notes drafted: app does not accept wagers; data sources and licences; how sync works | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | Demo account for reviewers with representative data | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | Age rating questionnaire completed accurately | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | App privacy details ("nutrition labels") match data inventory and SDKs | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | In-app account deletion present and discoverable | Built in mobile Settings with component tests (`apps/mobile/src/components/account-forms.test.tsx`). Not reported as seen on a device | G-04; mobile device testing |
| [ ] | Privacy Policy and Terms URLs live; support URL live | Nothing is live; pages are drafts | G-03, G-10 |
| [ ] | In-app purchase products configured and tested; subscription disclosures on paywall (if Premium ships) | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | Screenshots/preview show real app UI with licensed or fictional data; no misleading claims | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | Push notification permission requested in context, not at first launch | Not applicable: no push (`expo-notifications` is not installed) | G-06 |
| [ ] | App Tracking Transparency position confirmed (no tracking, or prompt implemented) | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | Export-compliance (encryption) questions answered | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | TestFlight beta completed with approved testers | None | G-04 |

**Google Play**

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Organisation developer account verified | A Google Play developer account exists (D-018). Whether it is an organisation account and verified is not recorded | G-04, G-02 |
| [ ] | Current Play policies re-read (real-money gambling, UGC, subscriptions, account deletion, AI content) and gaps closed | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | Any gambling-related declaration/application the policy requires for this app type identified and completed | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | Content rating (IARC) questionnaire completed accurately | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | Data safety form matches data inventory and SDKs | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | Account deletion: in-app path and web deletion URL provided | In-app path built, unverified on a device. No public web deletion URL: web deletion is inside the signed-in app | G-04 |
| [ ] | Target audience set to adults; no child-directed declarations | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | Play Billing configured and tested (if Premium ships) | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | Target API level and other technical requirements met | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | Closed/internal testing track completed per Play requirements for the account type | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | Store listing assets and copy approved (APP_STORE_LISTING_DRAFT) | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |

**Both**

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Listing copy passes banned-claims check; includes "does not accept wagers" and 21+ | Preparation notes: `docs/marketing/STORE_SUBMISSION_PREP.md` | G-04 |
| [ ] | Country availability set per Founder decision (US only at launch unless decided otherwise) | None | G-04; Founder |
| [ ] | Outbound sportsbook link behaviour consistent with each store's policy (or disabled in app) | No outbound sportsbook links exist | G-04, G-10 |
| [ ] | Founder approval recorded for submission (G-04) | None | G-04 |

## 9. Monetisation (only if Premium ships at launch) [F] [C]

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Pricing approved (G-07) | None. `/pricing` shows no prices | G-07 |
| [ ] | Payment processor approved the business category | None | G-01, G-11 |
| [ ] | Pre-purchase disclosures, consent capture, confirmation email, renewal reminders implemented per counsel | None | G-07, G-10 |
| [ ] | Online cancellation at least as easy as signup; tested | None | G-07, G-10 |
| [ ] | Refund policy published | None | G-07, G-10 |
| [ ] | Entitlements enforced server-side; restore purchases works | Plans exist without billing; enforcement is behind `premium_gating`, off. No purchases | G-07, G-11 |
| [ ] | Sales-tax handling confirmed | None | G-10 |

## 10. Community (only if it ships at launch) [C]

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Community guidelines published | Draft served by the API (`GET /v1/community/guidelines`), shown only while the community is switched on. Not reviewed | G-10 |
| [ ] | Report, block, mute functional; moderation queue staffed with response-time targets | Report and block built on web and mobile; a moderation queue for administrators on web, with restore. No mute. Not staffed; no targets | G-10; staffing: Founder |
| [ ] | Automated filtering for prohibited content in place | Fixed content rules reject links and some prohibited text (`services/api/tests/test_community_content_rules.py`). Not reviewed | G-10 |
| [ ] | Appeals process documented | None | G-10 |
| [ ] | DMCA agent registered and takedown process live | None | G-10 |

## 11. Marketing and support [F]

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Launch plan approved; every external action individually approved (G-05) | Draft: `docs/marketing/LAUNCH_PLAN_DRAFT.md` | G-05 |
| [ ] | Ad-platform certifications obtained where required before any paid campaign | None | G-05, G-10 |
| [ ] | Affiliate/influencer disclosures in place (if used) | None | G-05, G-10 |
| [ ] | Email sending domain authenticated (SPF, DKIM, DMARC); unsubscribe works; physical address in footer per counsel (G-06) | The domain has MX, SPF, DKIM and DMARC records for the mailbox (`docs/product/BUILD_STATUS.md`). No code sends email | G-02, G-06 |
| [ ] | Support channel staffed; help centre content complete; macros for deletion, RG, data questions | Playbook and macros drafted: `docs/product/SUPPORT_READINESS.md`. Mailbox exists, receiving not verified; no staff; staff export and delete procedure not written | G-06; Founder |
| [ ] | Press/boilerplate reviewed for claims | None | G-05, G-10 |
| [ ] | Analytics dashboards for launch funnel ready; north-star definition agreed | None | G-02, G-13 |

## 12. Go / no-go

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | All sections above complete or explicitly waived in writing by the Founder (waivers listed below) | — | Founder |
| [ ] | Rollback plan documented and rehearsed | Documented: `infrastructure/ROLLBACK_PLAN.md`. **Not rehearsed** | G-02 (needs staging) |
| [ ] | Go/no-go meeting held; decision recorded | Template: `docs/product/GO_NO_GO_TEMPLATE.md` | Founder |

| Waiver # | Item | Reason | Approved by | Date |
|---|---|---|---|---|
| | | | | |

## 13. Countersignature of ticked items

| Section and item | Evidence re-checked (CI run link or test output) | Confirmed by | Date |
|---|---|---|---|
| | | | |
