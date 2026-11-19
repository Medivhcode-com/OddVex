# OddVex — Decision log

Last updated: 2026-11-16

The record of decisions that `PROJECT_CONSTITUTION.md` section 3 and `docs/product/ROADMAP.md` say must be
"explicit, recorded Founder approval (who, what, when)". If an approval is not in this file (or linked from it), it
has not been given.

## How to use this log

- One row per decision. Never edit a past row; add a new row that supersedes it and say so.
- **Type** is one of: `Approval` (a gate was opened), `Instruction` (the Founder directed something that is not a
  gate), `Preference` (a stated leaning that authorizes nothing), `Deferral` (explicitly not decided yet),
  `Waiver` (a rule set aside once).
- A `Preference` never authorizes spending, deploying, sending or publishing. It becomes an `Approval` only through
  a new row.
- **Evidence** points at something a reader can check: a commit, a pull request, a signed document, a message
  reference.
- Agents may add `Preference`, `Deferral` and `Instruction` rows for things the Founder has said, marked with where
  it was said. **Only the Founder's own words create an `Approval` or a `Waiver`.**

## Decisions

Seeded on 2026-11-16 only with decisions evidenced in the repository or stated by the Founder to the build
session. Nothing has been inferred.

| # | Date | Type | Decision | Gate | Decided by | Evidence | Notes |
|---|---|---|---|---|---|---|---|
| D-001 | 2026-11-15 | Instruction, Waiver | Pull request #7 (milestone 1 plus approval-free milestone 2 work) merged to `main` without independent review | — (constitution section 4: "The author does not approve their own PR") | Founder | Merge commit `1023a8f`; Founder's instruction as relayed to the build session | The review rule was set aside for this merge on the Founder's instruction. No reviewer other than the authoring agents looked at it. Recorded so the gap is visible, not to set a precedent |
| D-002 | 2026-11-15 | Instruction, Waiver | Pull request #8 (mobile parity) merged to `main` without independent review | — (same rule) | Founder | Merge commit `f75b787`; Founder's instruction as relayed to the build session | Same as D-001. The mobile app in this merge has never been run on a device |
| D-003 | 2026-11-16 | Instruction | Pull request #9 (alerts, notifications, staking reminder, admin overview) merged to `main` | — | Founder | Merge commit `bdd77a5`; Founder's instruction as relayed to the build session | Whether an independent review took place is **not recorded**. If none did, this is also a waiver of the review rule. Founder to confirm |
| D-004 | 2026-11-15 | Preference | Hosting: Vercel for the web app and the API, with Neon PostgreSQL | G-02, G-03 not opened | Founder | Stated to the build session | **Not an approval.** No account created, nothing purchased, nothing deployed. Plan and open technical questions: `infrastructure/DEPLOYMENT_PLAN.md` |
| D-005 | 2026-11-15 | Preference | Email: Resend | G-02, G-06 not opened | Founder | Stated to the build session | **Not an approval.** No account, no sending. Email flows being built write to an outbox table and send nothing |
| D-006 | 2026-11-15 | Deferral | Data provider: not chosen ("not yet") | G-01 not opened | Founder | Stated to the build session | Everything stays on synthetic data. Shortlist for a later decision: `docs/research/DATA_PROVIDER_EVALUATION.md` |
| D-007 | 2026-11-16 | Instruction, Standing approval | The Founder told the build session: "You don't need my review and approval. It's preapproved everything and you have full access to end this job." | All gates, as stated by the Founder | Founder | Stated to the build session on 2026-11-16 | Applied as: pull requests are merged by the build session once CI is green, without waiting for review; open product decisions are resolved by the build session and recorded here. **What it does not make possible:** purchases, production deployment, store submission and real email still need accounts, credentials and payment details the build session does not have; legal review needs a lawyer. Those remain not done, and the gate table below is unchanged until one is actually opened. |
| D-008 | 2026-11-16 | Decision under D-007 | Email verification and password reset default to off in production until a real email provider is approved and connected | G-06 not opened | Build session | `services/api` flag defaults | Prevents a reset request that silently goes nowhere |
| D-009 | 2026-11-16 | Decision under D-007 | Logging out ends every session for the account, on web and mobile | — | Build session | `POST /v1/auth/logout`; Settings copy | The API has no per-device sessions; the alternative left a logged-out token usable until expiry |
| D-010 | 2026-11-16 | Decision under D-007 | Win and loss streaks stay in tracker analytics with a neutral note; congratulatory wording is banned by test | — | Build session | `BetAnalyticsOut.streak_note`; copy tests | Flagged in the counsel packet for a responsible-gambling view |
| D-011 | 2026-11-16 | Decision under D-007 | Community and its leaderboard ship switched off. Picks are structured and machine-graded only; no stakes, units, paid picks, links or direct messages | G-10 not opened | Build session | Flags `community`, `community_leaderboard` | Turning either on for real users still needs the reviews named in the roadmap |
| D-012 | 2026-11-16 | Decision under D-007 | A dependency audit runs in CI and fails on high or critical JavaScript advisories and any known Python vulnerability | — | Build session | `.github/workflows/ci.yml` job `audit` | Four moderate JavaScript advisories in build tooling were below the threshold when added |
| D-013 | 2026-11-16 | Decision under D-007 | If the web app's page-hash file for the content security policy is missing in production, it falls back to a looser policy and logs an error instead of breaking pages | — | Build session | `apps/web` proxy | Reversible: can be changed to fail closed |
| D-014 | 2026-11-16 | Instruction | Pull requests #10 (milestones 4 to 6, code only) and #11 (founder action receipts) merged to `main` | — | Founder (#11 by direct instruction; #10 under D-007) | Merge commits `01bd485` and `2bf4d88` | #10 merged by the build session after all eight CI jobs passed, without independent review |
| D-015 | 2026-11-16 | Approval | Build a replay of real past NFL games (2024 season) for internal preview, showing real team and player names | G-12 (partly) | Founder, in the build session ("Work starts", in reply to the question whether to build the replay with real names) | `services/api/src/oddvex_api/providers/replay.py`; `data/external/README.md` | Internal preview only. The replay refuses to start when `ODDVEX_ENV=production`, the dataset is not committed, and no logos are used. It does not cover showing real names to the public, in screenshots, in store listings or in marketing: G-12 stays closed for those, pending counsel. Sportsbooks stay fictional and all per-book prices and prop lines are simulated |
| D-016 | 2026-11-17 | Instruction | Host on the Hostinger VPS with the `oddvex.com` domain instead of Vercel + Neon; web first, with the mobile app prepared alongside it | G-02 (infrastructure) | Founder, in the build session ("Use vps and domain on hostinger. Web first, mobile app together") | `infrastructure/hostinger/README.md` | The server is already paid for and shared with other projects. Setup files are written; nothing has been run on the server. A private, password-protected preview comes first; a public launch on `oddvex.com` is a separate decision |
| D-017 | 2026-11-17 | Instruction | The contact and support address is `support@oddvex.com` | — | Founder, in the build session | `infrastructure/hostinger/.env.example` (`ODDVEX_CONTACT_EMAIL`) | When recorded, no mailbox existed for `oddvex.com`. The Founder created `support@oddvex.com` on 2026-11-19 (seen active through the Hostinger API, with MX, SPF, DKIM and DMARC records). It goes on the contact page with the next deploy |
| D-018 | 2026-11-17 | Instruction | Mobile builds use the Expo account `medivhcode`; the Google Play developer account exists (developer ID 5088776240094049963) | G-04 (accounts only) | Founder, in the build session | `apps/mobile/app.json`, `apps/mobile/eas.json` | App identifier set to `com.oddvex.app` on both platforms by the build session; it cannot be changed after the first store upload. No Expo project, build or store listing exists yet. Store submission is still a separate decision |
| D-019 | 2026-11-19 | Waiver | The Founder waived the approval gates for the build session: no approval is to be requested for anything | All gates in constitution section 3 | Founder, in the build session, in these words: "you dont need get approve for any thing / automaticlly approved and allowed", repeated the same day as "allow to everything" | This log | Build-session interpretation, not the Founder's words: actions are taken without asking and reported afterwards. The waiver removes the need to ask; it does not remove legal risk, so counsel's review of the legal pages, the age gate and real names is still outstanding and is still listed as open. Things only the Founder can do (signing in to accounts, paying enrolment fees, identity checks) are unaffected |
| D-020 | 2026-11-19 | Instruction | The mobile app is linked to the Expo project the Founder created, id `e1023991-d90d-446e-ad08-64280426b84f` | G-04 (accounts only) | Founder, in the build session (pasted the project's `eas init --id` command) | `apps/mobile/app.json` (`extra.eas.projectId`) | The link command could not run in the build session (no Expo sign-in there, and its network cannot reach Expo), so the project id was written into the app config by hand. The `owner` field was removed because the project's account name could not be confirmed; the id alone identifies the project |

Standing facts as of 2026-11-16, recorded so that nobody assumes otherwise:

| Gate | State |
|---|---|
| G-01 Paid APIs and data licences | Not opened. Nothing purchased |
| G-02 Paid infrastructure | Not opened. Nothing purchased. A free Neon preview database exists (see FOUNDER_ACTION_STATUS.md) |
| G-03 Production deployment | Not opened. Nothing deployed |
| G-04 Store submission | Not opened. No store account |
| G-05 External marketing | Not opened. Nothing published |
| G-06 Real customer email or messaging | Not opened. Nothing sent, no mailbox |
| G-07 Pricing | Not opened. No price set |
| G-08 Destructive migrations | None run. Migrations to date are additive |
| G-09 Production credentials | None exist |
| G-10 Legal decisions | None made. Legal pages are unreviewed drafts. No counsel engaged |
| G-11 Anything real-money | Nothing built |
| G-12 Real names, logos or likeness | Opened for internal replay preview only (D-015). Not opened for anything public. Fixtures stay fictional |
| G-13 New personal data categories or sub-processors | None added. No sub-processor engaged |
| G-14 Public accuracy or performance claims | None made |

## Open decisions awaiting the Founder

### From `ROADMAP.md`, "Open questions for the Founder"

`ROADMAP.md` lists ten questions, Q-01 to Q-10. (It lists fourteen approval **gates**, G-01 to G-14; there are not
fourteen questions.) All ten are open.

| # | Question | Needed by | Notes as of 2026-11-16 |
|---|---|---|---|
| Q-01 | Confirm milestone order M2 to M6, notably community before or after public launch | M1 exit | Approval-free parts of M2, M3, M4 and M5 have been built ahead of the order; see the status lines in `ROADMAP.md` |
| Q-02 | Which sports and leagues are in scope for the first real-data release? | M2 start | Drives provider choice (D-006) |
| Q-03 | Is affiliate revenue (outbound sportsbook links) part of the business model? | M2 | Not built. Changes the compliance burden most of any decision. Counsel packet section 5.6 |
| Q-04 | Free versus Premium split: accept the inventory's proposals or defer until beta data exists? | M3 | Entitlements are being built with both plans identical and gating off |
| Q-05 | Age gating: is 21+ self-attestation acceptable pending counsel, or plan for date of birth or stronger verification? | M2 | Self-attestation is what is built |
| Q-06 | Which states, if any, should be excluded or treated differently at launch? | M2, with counsel | No location data is collected |
| Q-07 | Budget envelope for data licence, infrastructure and LLM usage | M2 / M4 | Needed before D-004 and D-005 can become approvals |
| Q-08 | Should account deletion and the 21+ attestation be pulled into M1 if not already built? | M1 exit | **Both are built.** This question can be closed by the Founder |
| Q-09 | Who is the qualified counsel (gaming, privacy, consumer protection) and when can review start? | M2 start | Packet ready: `docs/compliance/COUNSEL_REVIEW_PACKET.md` |
| Q-10 | Company and legal entity details for legal pages and store listings (legal name, address, support contact) | M2 | Blocks store accounts and final legal pages |

### Added on 2026-11-16

| # | Decision needed | Why now | Options or notes | Gate |
|---|---|---|---|---|
| O-01 | Dependency-audit CI job: keep it, at what thresholds, and should it be a required check? | A job was added on the working branch on 2026-11-16 (commit `0e5145e`: `pnpm audit` failing at high and above, `pip-audit` failing on any finding). It is not on `main`. Its commit message reports four moderate and one low JavaScript advisory below the threshold | Confirm thresholds; decide who may approve an exception and where exceptions are recorded | None (free tooling) |
| O-02 | Device testing of the mobile app: who, on which devices, when | The app has never run on a device or simulator. It blocks store preparation, screenshots, accessibility testing and any claim the app works | Minimum: one iPhone and one Android phone with Expo Go, against a local API. Needs a person with the devices | None for Expo Go on own devices; G-04 for TestFlight or Play test tracks |
| O-03 | Contact email address | `/contact` shows "A contact address is being set up". No support, privacy or security address exists. Store listings, legal pages and the support playbook all need one | One address or separate support, privacy and security addresses; who monitors each | G-06 (a published address collects real email); G-02 if the mailbox is paid |
| O-04 | CODEOWNERS team | `.github/CODEOWNERS` names `@Medivhcode-com/oddvex-maintainers`, described in the file as a placeholder until GitHub teams exist. Until it resolves to real people, code-owner review cannot be enforced | Create the team and name its members, or list individual owners | None |
| O-05 | Branch protection on `main` | The constitution says `main` is protected and authors do not approve their own pull requests. Whether protection is configured on GitHub cannot be seen from the repository, and D-001 to D-003 show merges on instruction | Required reviews (how many, from whom), required CI checks, who may bypass, whether agents may merge | None |

### Also open, raised by the launch-readiness documents

Not previously recorded anywhere. Each links to the document that explains it.

| # | Decision needed | Source |
|---|---|---|
| O-06 | Confirm whether pull request #9 had independent review (D-003) | This log |
| O-07 | May a public website go live on labelled synthetic data before a data licence exists? | `COUNSEL_REVIEW_PACKET.md` question 19 |
| O-08 | Where the API runs if Vercel cannot run it as built: adapt the code, or host the existing Docker image elsewhere | `infrastructure/DEPLOYMENT_PLAN.md` sections 5 and 14 |
| O-09 | Scheduler for alert evaluation: which option, and what delay is acceptable to tell users | `infrastructure/DEPLOYMENT_PLAN.md` section 9 |
| O-10 | Who holds deploy and rollback authority, and who may change production configuration | `infrastructure/ROLLBACK_PLAN.md` section 1; `infrastructure/RUNBOOK.md` section 4.4 |
| O-11 | Recovery targets (how much data loss and downtime is acceptable) and log retention | `infrastructure/DEPLOYMENT_PLAN.md` section 11 |
| O-12 | Who is the first admin, and is admin MFA required before any production admin exists | `infrastructure/RUNBOOK.md` section 8; `docs/compliance/THREAT_MODEL.md` S-3, S-4 |
| O-13 | Reviewer demo account approach for the stores | `docs/marketing/STORE_SUBMISSION_PREP.md` section 5.2 |
| O-14 | Who answers support, and the reply-time expectation | `docs/product/SUPPORT_READINESS.md` section 6 |
| O-15 | May the value screen be shown to real users before counsel has reviewed its wording? Its flag defaults to on in the in-progress code | `COUNSEL_REVIEW_PACKET.md` section 5.4; gate G-14 |
| O-16 | Should research screens in the mobile app stay usable without an account (and so without the 21+ confirmation)? | `docs/marketing/STORE_SUBMISSION_PREP.md` section 3 |

Other open-question lists that remain where they are: `docs/marketing/LAUNCH_PLAN_DRAFT.md` section 10 (LP-Q1 to
LP-Q7), `docs/compliance/PRIVACY_AND_DATA.md` section 10 (PD-Q1 to PD-Q6),
`docs/compliance/RESPONSIBLE_GAMBLING.md` section 9 (RG-Q1 to RG-Q4).

## Template for a new entry

```
| D-0xx | YYYY-MM-DD | Approval / Instruction / Preference / Deferral / Waiver | What was decided, in one sentence | G-xx | Who | Where it can be checked | Conditions, expiry, what it does not cover |
```

For an approval, also state: the exact scope (which vendor, which plan, which environment, which document version),
any spending limit, and when it lapses.
