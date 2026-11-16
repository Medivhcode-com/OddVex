# OddVex — Go / no-go decision template

Last updated: 2026-11-16 · Status: **template. No launch decision has been made or scheduled.**

Use one copy of this template per decision: closed beta, public web launch, store submission. Copy it, fill it in,
and link the completed copy from `docs/product/DECISION_LOG.md`. A "go" is a Founder approval under gates G-03
(production), G-04 (stores) and G-05 (marketing) in `docs/product/ROADMAP.md`. Nobody else can give it.

Rules:

- Every criterion needs a link to evidence a reader can open: a CI run, a test output, a signed document, a
  decision-log entry. "Believed done" is a no.
- A criterion is **Met**, **Not met** or **Waived**. Only the Founder waives, in writing, with a reason.
- Any criterion marked **Must** that is not met and not waived makes the decision no-go.
- Do not fill in a threshold on the day. Thresholds are agreed beforehand.

## 1. Decision header

| | |
|---|---|
| Decision | Closed beta / Public web launch / App Store submission / Google Play submission |
| Scope | What exactly goes live, for whom, where: ____________ |
| Not in scope | ____________ |
| Release (commit, API version, mobile build) | ____________ |
| Data | Synthetic and labelled / Licensed from ____________ |
| Proposed date and time (with time zone) | ____________ |
| Meeting date | ____________ |
| Attendees | ____________ |
| Decision owner | Founder: ____________ |

## 2. Criteria

Evidence starting points are listed where the repository already has something. They are not evidence that the
criterion is met.

### 2.1 Legal and compliance

| # | Criterion | Must | Evidence link | Owner | State | Notes |
|---|---|---|---|---|---|---|
| L-1 | Counsel engaged; sign-off table complete for everything in scope | Must | `docs/compliance/COUNSEL_REVIEW_PACKET.md` section 8 | Founder | | |
| L-2 | Terms, Privacy policy and Responsible gambling pages are final, approved and deployed; draft banners removed | Must | | Founder, counsel | | |
| L-3 | Privacy policy matches what the software stores | Must | Counsel packet section 3.5 resolved | Engineering, counsel | | |
| L-4 | Age-gating approach approved | Must | | Counsel | | |
| L-5 | State availability decision recorded | Must | Decision log | Founder | | |
| L-6 | Affiliate position recorded; no outbound sportsbook link in the build unless approved | Must | Decision log | Founder | | |
| L-7 | Data licence signed and its display, storage and attribution terms implemented, **or** written decision to launch on labelled synthetic data | Must | | Founder | | |
| L-8 | Real names, logos and likeness policy approved if any appear (G-12) | Must if applicable | | Founder, counsel | | |
| L-9 | Breach-notification matrix on file | Must | | Counsel | | |
| L-10 | `LAUNCH_READINESS_CHECKLIST.md` section 1 complete or waived | Must | `docs/compliance/LAUNCH_READINESS_CHECKLIST.md` | Founder | | |

### 2.2 Product honesty and responsible gambling

| # | Criterion | Must | Evidence link | Owner | State | Notes |
|---|---|---|---|---|---|---|
| H-1 | No wagering, no funds, no bet-slip hand-off in any surface, re-verified on this release | Must | | Product | | |
| H-2 | No synthetic data presented as real; every data surface labelled while data is synthetic | Must | | Product | | |
| H-3 | Every price shows its age; stale prices are labelled and excluded from best price | Must | | Engineering | | |
| H-4 | Marketing and listing copy describe only what is in this release | Must | | Product | | |
| H-5 | Copy passes the banned-claims list; no accuracy or profit claims (G-14) | Must | `docs/marketing/BRAND_VOICE.md` | Product | | |
| H-6 | Responsible-gambling footer and helpline on every surface; helpline details re-verified this release | Must | | Compliance | | |
| H-7 | Notification, alert, value-screen and reminder wording reviewed | Must | `services/api/tests/test_notification_copy.py` is an automated scan only | Counsel | | |
| H-8 | Features not approved for users are off (community; premium gating) | Must | Flag states recorded | Engineering | | |

### 2.3 Quality

| # | Criterion | Must | Evidence link | Owner | State | Notes |
|---|---|---|---|---|---|---|
| Q-1 | CI green on the release commit: API, API on PostgreSQL, web, mobile, end to end, Docker, dependency audit, secret scan | Must | CI run link | Engineering | | |
| Q-2 | No test skipped, disabled or deleted to get there | Must | Diff since last release | Engineering | | |
| Q-3 | Critical journeys J1 to J10 pass end to end on staging | Must | `docs/product/USER_JOURNEYS.md` | Engineering | | |
| Q-4 | Web accessibility: automated checks pass and a manual keyboard and screen-reader pass is recorded | Must | `apps/web/e2e/a11y.spec.ts` covers the automated half only | Engineering | | |
| Q-5 | Mobile: run on at least one iPhone and one Android phone; findings fixed or accepted | Must for any mobile release | | Mobile | | |
| Q-6 | Mobile accessibility with VoiceOver and TalkBack | Must for store submission | | Mobile | | |
| Q-7 | Known defects listed, each with a severity and an accept or fix decision | Must | | Engineering | | |
| Q-8 | Browser and device matrix tested | Should | | Engineering | | |

### 2.4 Security and privacy

| # | Criterion | Must | Evidence link | Owner | State | Notes |
|---|---|---|---|---|---|---|
| S-1 | Top risks in `THREAT_MODEL.md` section 6 each fixed or risk-accepted by the Founder in writing | Must | `docs/compliance/THREAT_MODEL.md` | Founder | | |
| S-2 | Admin accounts: named, approved, MFA in place | Must | Decision log | Founder | | |
| S-3 | Production secrets in a managed store; access list reviewed (G-09) | Must | | Operations | | |
| S-4 | Dependency and secret scans clean or exceptions accepted | Must | CI run | Engineering | | |
| S-5 | Rate limiting works on the production host, including for web sign-in | Must | Test on staging | Engineering | | |
| S-6 | Account deletion and export verified on production configuration; retained data matches the privacy policy | Must | | Engineering | | |
| S-7 | Independent penetration test done; findings resolved or accepted | Must for public launch | | Founder (G-02) | | |
| S-8 | Sub-processor list published; agreements signed (G-13) | Must | | Founder, counsel | | |
| S-9 | Security contact published | Should for beta, Must for public | | Founder (G-06) | | |

### 2.5 Operations

| # | Criterion | Must | Evidence link | Owner | State | Notes |
|---|---|---|---|---|---|---|
| O-1 | Production and staging exist, approved and documented (G-02, G-03) | Must | `infrastructure/DEPLOYMENT_PLAN.md` | Operations | | |
| O-2 | Deploy and rollback rehearsed on staging, including across a migration | Must | `infrastructure/ROLLBACK_PLAN.md` section 9 | Operations | | |
| O-3 | Backups running; restore test passed; recovery figures recorded | Must | | Operations | | |
| O-4 | No destructive migration in the release, or G-08 on record | Must | | Engineering | | |
| O-5 | Monitoring and alerting live; on-call roster filled in | Must | `infrastructure/RUNBOOK.md` section 12 | Operations | | |
| O-6 | Alert evaluation has a scheduler, or the product says plainly how alerts are checked | Must | | Engineering | | |
| O-7 | Incident response tabletop held | Must | `docs/compliance/INCIDENT_RESPONSE.md` section 8 | Founder | | |
| O-8 | Rollback thresholds R-7 and R-8 filled in | Must | `infrastructure/ROLLBACK_PLAN.md` section 2 | Engineering, Founder | | |
| O-9 | Cost monitoring and budget alerts set | Should | | Founder | | |
| O-10 | Smoke test passed on production | Must (on the day) | `infrastructure/DEPLOYMENT_PLAN.md` section 10 | Release owner | | |

### 2.6 Support and communication

| # | Criterion | Must | Evidence link | Owner | State | Notes |
|---|---|---|---|---|---|---|
| C-1 | Support mailbox live and monitored; `/contact` shows it | Must | | Founder (G-06) | | |
| C-2 | Support playbook current for this release; someone is assigned | Must | `docs/product/SUPPORT_READINESS.md` | Founder | | |
| C-3 | Password recovery works, or the limitation is stated to users | Must | | Engineering | | |
| C-4 | Every external launch action individually approved (G-05); no email unless G-06 | Must | Decision log | Founder | | |
| C-5 | A way to tell users about an incident | Should | | Operations | | |

### 2.7 Store submission (only for a store decision)

| # | Criterion | Must | Evidence link | Owner | State | Notes |
|---|---|---|---|---|---|---|
| A-1 | Every blocker in `STORE_SUBMISSION_PREP.md` section 1 cleared | Must | `docs/marketing/STORE_SUBMISSION_PREP.md` | Mobile | | |
| A-2 | Current store policies read; findings recorded in section 6 of that document | Must | | Assigned reader, counsel | | |
| A-3 | Age rating answers and privacy declarations derived from the shipped build and reviewed by counsel | Must | | Counsel | | |
| A-4 | Review notes true of the build; demo account works | Must | | Mobile | | |
| A-5 | Screenshots taken from the shipped build | Must | | Mobile | | |

## 3. Summary

| Area | Must criteria | Met | Not met | Waived |
|---|---|---|---|---|
| Legal and compliance | | | | |
| Product honesty and responsible gambling | | | | |
| Quality | | | | |
| Security and privacy | | | | |
| Operations | | | | |
| Support and communication | | | | |
| Store submission | | | | |

## 4. Waivers

Only the Founder waives. Counsel-required items cannot be waived without counsel's written view attached.

| # | Criterion | Reason | Risk accepted | Mitigation | Expires or revisit on | Founder (name, date) |
|---|---|---|---|---|---|---|
| | | | | | | |

## 5. Rollback trigger and plan for this release

| | |
|---|---|
| Rollback plan | `infrastructure/ROLLBACK_PLAN.md`, rehearsed on ____________ |
| Previous known-good build (web / API) | ____________ / ____________ |
| Migration in this release | None / additive / destructive (G-08 entry: ______) |
| Rollback triggers in force | R-1 to R-11 in `ROLLBACK_PLAN.md` section 2 |
| Error-rate trigger (R-7) | Above ______ % for ______ minutes |
| Latency trigger (R-8) | Above ______ for ______ minutes |
| Additional trigger for this release | ____________ |
| Who may call a rollback | ____________ and ____________ |
| Watch period after release | ______ hours, staffed by ____________ |
| What a rollback cannot undo for this release | ____________ |
| How users are told | ____________ (any email: G-06) |

## 6. Decision

| | |
|---|---|
| Decision | **Go** / **No-go** / **Go with conditions** |
| Conditions | ____________ |
| If no-go: what must change, and re-review date | ____________ |
| Gates opened by this decision | G-____ for ____________ (exact scope) |

Sign-off:

| Role | Name | Position on the decision | Signature or message reference | Date |
|---|---|---|---|---|
| Founder (decides) | | Go / No-go | | |
| Engineering lead | | Recommend go / no-go | | |
| Product | | Recommend go / no-go | | |
| Compliance documentation | | Recommend go / no-go | | |
| Counsel (advises on legal criteria) | | Reviewed / Not reviewed | | |
| Release owner | | Ready / Not ready | | |

Record the outcome as a new row in `docs/product/DECISION_LOG.md`.

## 7. After the decision

- [ ] Decision-log entry added with the commit and scope
- [ ] `LAUNCH_READINESS_CHECKLIST.md` section 12 updated
- [ ] If go: release record opened; watch period staffed
- [ ] If no-go: each unmet criterion has an owner and a Linear issue
- [ ] Review held ______ days after release: what the criteria missed
