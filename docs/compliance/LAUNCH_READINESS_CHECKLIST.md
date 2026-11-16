# OddVex — Launch Readiness Checklist

Last updated: 2026-11-16

**Status: NOT READY FOR LAUNCH.** Everything runs on synthetic data. There is no production environment, no legal review, no store account and no real user. The mobile app has never run on a device.

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
| [x] | No real customer data has been collected (no production environment exists) | `docs/product/BUILD_STATUS.md` (nothing deployed); `infrastructure/README.md` | — |
| [x] | No paid data provider, paid infrastructure or store submission has been initiated | `docs/product/BUILD_STATUS.md`; `docs/product/DECISION_LOG.md` | — |

## 1. Legal sign-offs [C] [F]

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Qualified counsel engaged (gaming, privacy, consumer protection/advertising, IP) [B] | None. Packet ready to send: `COUNSEL_REVIEW_PACKET.md` | G-10; ROADMAP Q-09 |
| [ ] | Written confirmation of licensing/registration position for the launch feature set, state by state (GB-01) [B] | None | G-10 |
| [ ] | Affiliate decision made; if yes, required state registrations/licences obtained before any affiliate link goes live (GB-02) | None. Affiliate links are not built | G-10, G-11; ROADMAP Q-03 |
| [ ] | State availability decision recorded (any excluded/geo-restricted states) (GB-03) [B] | None | G-10; ROADMAP Q-06 |
| [ ] | Terms of Service final and approved [B] | Draft with banner: `apps/web/src/app/(marketing)/terms/page.tsx` | G-10 |
| [ ] | Privacy Policy final and approved; matches actual data practices [B] | Draft with banner: `apps/web/src/app/(marketing)/privacy/page.tsx`. Draft does not yet match the data model (see `COUNSEL_REVIEW_PACKET.md` section 3) | G-10 |
| [ ] | Responsible Gambling page approved; helpline details verified [B] | Page exists: `apps/web/src/app/(marketing)/responsible-gambling/page.tsx`. Not reviewed. It carries no draft banner | G-10 |
| [ ] | Age-gating approach approved (AG-01) [B] | Self-attestation built: `services/api/src/oddvex_api/auth/schemas.py` | G-10; ROADMAP Q-05 |
| [ ] | Advertising/marketing rules memo received; banned-claims list confirmed (AD-01…AD-10) | None | G-10 |
| [ ] | Data licence reviewed and signed (DL-01, DL-02) [B] | None. No provider chosen | G-01, G-10 |
| [ ] | Sync vendor agreement and consent language reviewed (if sync ships) (GB-07) | None. Mock provider only | G-01, G-10 |
| [ ] | Auto-renewal/subscription flows reviewed (if Premium ships) (SB-01…SB-07) | None. No billing built | G-07, G-10 |
| [ ] | AI disclosure and disclaimers reviewed (AI-C1…AI-C4) | None. Assistant is rule-based | G-10 |
| [ ] | UGC terms, guidelines and DMCA process reviewed (if community ships) | None. Community not built (in progress behind a flag, off by default) | G-10 |
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
| [ ] | RG footer (21+, 1-800-GAMBLER) on every web, marketing and mobile surface [B] | Partial: web footer asserted in `apps/web/e2e/marketing.spec.ts`. Mobile has a responsible-gambling line in Settings and is unverified on a device | Mobile device testing; G-10 |
| [ ] | 21+ gate enforced at signup on web and mobile [B] | Partial: API rejects registration without `age_confirmed` (`auth/schemas.py`); web and mobile forms require it. Mobile unverified on a device. Method not approved | G-10 (AG-01) |
| [ ] | `/responsible-gambling` live and linked from app settings [B] | Page built; nothing is live | G-03, G-10 |
| [ ] | Assistant distress/guarantee/under-21 behaviours tested [B] | `services/api/tests/test_api_assistant.py` exists; coverage of each behaviour not audited in this pass | Engineering review; G-10 |
| [ ] | Notification copy reviewed for inducement (if notifications ship) | Automated banned-phrase scan only: `services/api/tests/test_notification_copy.py`. No human or counsel review | G-10 |
| [ ] | Tracker shows losses plainly; no celebratory or chasing prompts [B] | Built; no review recorded | Product and RG review |
| [ ] | Parlay screen shows probability with payout and correlation warning | Correlation warning asserted in `apps/web/e2e/app.spec.ts`; no RG review recorded | Product and RG review |
| [ ] | All copy passes BRAND_VOICE banned-claims check [B] | Notification templates only (see above). No full copy audit | Product review; G-10 |
| [ ] | No goals/KPIs tied to amount wagered or bet count | No analytics or KPIs exist | Founder |

## 4. Privacy and data

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Data inventory reconciled with actual implementation and vendors [B] | Not reconciled. Known mismatches listed in `COUNSEL_REVIEW_PACKET.md` section 3 | Engineering + G-10 |
| [x] | Self-serve account deletion works end to end on web and API [B] | `DELETE /v1/me` (`auth/router.py`); web test "delete account removes access" in `apps/web/e2e/app.spec.ts`; cascades in `db/models.py`. Audit rows keep the user id and IP (see `THREAT_MODEL.md` I-5) | — |
| [ ] | Self-serve account deletion verified in the mobile apps on a device [B] | Built with component tests; never run on a device | Mobile device testing (Founder decision) |
| [x] | Data export works [B] | `GET /v1/me/export`; `services/api/tests/test_api_account.py`; web test "export downloads my data without any password material" in `apps/web/e2e/app.spec.ts`. Web and API only: the mobile app has no export (`apps/mobile/README.md`) | — |
| [ ] | Retention schedule implemented (logs, backups, analytics) [B] | None. Notifications are capped at 500 per user; nothing else expires | G-10; G-02 |
| [ ] | Sub-processor list published; DPAs signed with each vendor [B] | None engaged | G-02, G-13, G-10 |
| [ ] | Analytics events audited: no emails, stakes, notes or assistant text [B] | No analytics instrumented | G-02, G-13 |
| [ ] | Cookie/consent approach implemented per counsel | None. Web sets a session cookie and stores theme and odds format in the browser | G-10 |
| [ ] | Privacy contact mailbox live and monitored [B] [F] | None. `/contact` shows a placeholder | G-06 |
| [ ] | No sportsbook credentials collected or stored anywhere (code + UI audit) | No credential field in `db/models.py` (`sync_connections.provider_state` is documented "never credentials"); mock sync only. No formal code and UI audit recorded | Engineering audit |
| [ ] | Sync tokens encrypted; disconnect revokes at vendor (if sync ships) | Not applicable until a vendor exists | G-01 |
| [ ] | LLM provider terms confirm no training on OddVex data and acceptable retention (if LLM ships) | Not applicable: no model connected | G-01 |
| [ ] | Process for suspected under-21 accounts documented [B] | Policy line in `PRIVACY_AND_DATA.md` section 9; no documented procedure or admin tool | G-10 (AG-03) |

## 5. Security

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | SECURITY_BASELINE M1 verification checklist complete [B] | Not completed. Gaps listed in `THREAT_MODEL.md` (AU-03, AU-04, AU-06, DS-01, DS-02) | Engineering |
| [ ] | All M2+ baseline controls implemented for production [B] | None | G-02, G-09 |
| [ ] | Admin accounts use MFA; admin actions audit-logged [B] | No MFA exists. Admin reads and role changes are not audited (`THREAT_MODEL.md` S-3, R-1) | Engineering |
| [ ] | Secrets in a managed store [B] | None | G-02, G-09 |
| [x] | Secret scan runs in CI over full git history [B] | `secrets` job (gitleaks, `fetch-depth: 0`) in `.github/workflows/ci.yml`. Job result on GitHub not re-checked in this pass | — |
| [ ] | Dependency, secret and static scans clean or exceptions risk-accepted [B] | Secret scan and lint run in CI. **No dependency vulnerability audit job.** Dependabot opens update PRs only | Founder decision (dependency-audit CI job) |
| [ ] | Rate limiting and abuse controls load-tested [B] | Unit and API tests only (`test_platform.py`, `test_api_auth.py`). Not load-tested. Web sign-ins share one bucket (`THREAT_MODEL.md` D-2) | G-02 |
| [ ] | Backups automated; restore test passed with recorded RTO/RPO [B] | None | G-02 |
| [ ] | Independent penetration test completed; findings resolved or risk-accepted by Founder [F] | None | G-02 |
| [ ] | Security contact and `security.txt` published | None | G-06 |
| [ ] | Access review complete; least privilege confirmed [B] | No production access exists. `CODEOWNERS` names a placeholder team | G-09; Founder decision (CODEOWNERS, branch protection) |

## 6. Reliability and operations

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Production environment provisioned and documented [B] [F] | None. Plan: `infrastructure/DEPLOYMENT_PLAN.md` | G-02, G-03 |
| [ ] | Staging mirrors production; deploy and rollback rehearsed [B] | None. Procedure unrehearsed: `infrastructure/ROLLBACK_PLAN.md` | G-02 |
| [ ] | Monitoring, alerting and on-call roster active [B] | None. Template with blanks: `infrastructure/RUNBOOK.md` section 12 | G-02 |
| [ ] | Data freshness monitors and feed kill switches in place [B] | None | G-01, G-02 |
| [ ] | Feature flags / kill switches for assistant, sync, alerts | In progress in the API; not in `services/api/README.md` yet | Engineering |
| [ ] | Incident response tabletop completed [B] | None | Founder |
| [ ] | Load test at expected launch traffic (targets to be set) | None; targets not set | G-02 |
| [ ] | Performance budgets met on reference devices (NFR-20…NFR-25) | Not measured | Mobile device testing |
| [ ] | Status page or in-app incident banner available | None | G-02 |
| [ ] | Database migration plan reviewed; no pending destructive migrations without approval [F] | Plan written, not reviewed: `infrastructure/DEPLOYMENT_PLAN.md` section 6. Revisions 0001 to 0003 are additive | G-08 |
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
| [ ] | Mobile a11y pass (VoiceOver, TalkBack, font scaling, contrast, targets) | None. The app has never run on a device or simulator | Mobile device testing (Founder decision) |
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
| [ ] | In-app account deletion present and discoverable | Built in mobile Settings with component tests (`apps/mobile/src/components/account-forms.test.tsx`). Never seen on a device | G-04; mobile device testing |
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
| [ ] | Organisation developer account verified | None | G-04, G-02 |
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
| [ ] | Entitlements enforced server-side; restore purchases works | Entitlements without billing are in progress in the API | G-07, G-11 |
| [ ] | Sales-tax handling confirmed | None | G-10 |

## 10. Community (only if it ships at launch) [C]

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Community guidelines published | None | G-10 |
| [ ] | Report, block, mute functional; moderation queue staffed with response-time targets | None | G-10; staffing: Founder |
| [ ] | Automated filtering for prohibited content in place | None | G-10 |
| [ ] | Appeals process documented | None | G-10 |
| [ ] | DMCA agent registered and takedown process live | None | G-10 |

## 11. Marketing and support [F]

| Done | Item | Evidence | Blocking gate or next step |
|---|---|---|---|
| [ ] | Launch plan approved; every external action individually approved (G-05) | Draft: `docs/marketing/LAUNCH_PLAN_DRAFT.md` | G-05 |
| [ ] | Ad-platform certifications obtained where required before any paid campaign | None | G-05, G-10 |
| [ ] | Affiliate/influencer disclosures in place (if used) | None | G-05, G-10 |
| [ ] | Email sending domain authenticated (SPF, DKIM, DMARC); unsubscribe works; physical address in footer per counsel (G-06) | None. No code sends email | G-02, G-06 |
| [ ] | Support channel staffed; help centre content complete; macros for deletion, RG, data questions | Playbook and macros drafted: `docs/product/SUPPORT_READINESS.md`. No mailbox, no staff | G-06; Founder |
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
