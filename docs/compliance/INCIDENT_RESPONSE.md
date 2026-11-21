# OddVex — Incident Response Plan

Last updated: 2026-11-21 (status line only) · Status: draft plan. **A private preview has run in production mode since 2026-11-18** (`docs/product/DECISION_LOG.md`, D-021); its API is open to the internet and accepts sign-ups, so it may hold real people's email addresses, password hashes and IP addresses. Whether anyone outside the team has signed up cannot be seen from the repository. This plan has not been exercised; it must be (tabletop) before any real-user beta, and it already applies to the preview. Legal notification duties are **to be confirmed by counsel** — nothing here states a legal deadline as fact.

## 1. Scope

An incident is any event that threatens the confidentiality, integrity or availability of OddVex systems or data, or that could materially mislead or harm users.

| Category | Examples |
|---|---|
| Security | Unauthorised access, account takeover wave, leaked secret, vulnerable dependency exploited, lost device with access |
| Privacy | Personal data exposed to the wrong party, cross-user data leak (e.g. another user's bets visible), data sent to an unapproved vendor |
| Data integrity | Wrong or stale odds presented as current, mis-attributed sportsbook prices, calculator defect, wrong P/L |
| AI | Assistant presents an invented number, leaks another user's data, bypasses refusals, gives harmful response to a distressed user |
| Availability | Outage, severe degradation, data-provider outage, failed migration |
| Third party | Incident at data provider, sync vendor, LLM provider, hosting, payment processor |
| Compliance / trust | Banned claim published, under-21 user identified, regulator/legal notice, app-store rejection or takedown, harmful UGC |

## 2. Severity

| Sev | Definition | Examples | Response start | Update cadence |
|---|---|---|---|---|
| **SEV1** | Confirmed/likely exposure of personal data or credentials; widespread materially wrong data; full outage; active attack | DB exposed; cross-user bet leak; production secret leaked; odds wrong across site | Immediately | Every 30–60 min |
| **SEV2** | Significant degradation or contained security issue; no confirmed data exposure | Sync failing for all; assistant ungrounded answer reproducible; single-feed stale without labelling | Within 1 h | Every 2–4 h |
| **SEV3** | Minor/limited impact; workaround exists | One calculator edge-case bug; isolated stale market correctly labelled | Next business day | Daily |
| **SEV4** | Near miss / hygiene | Secret committed to a branch but never deployed (still rotate) | Planned | On closure |

When unsure, classify higher and downgrade later.

## 3. Roles

| Role | Responsibility | Holder |
|---|---|---|
| Incident Commander (IC) | Runs the response, makes containment calls, owns timeline | On-call engineer (to be assigned at M2) |
| Founder | Decisions on user/regulator/press communication, legal engagement, spend, taking the service offline for extended periods | Founder |
| Technical lead | Investigation, fix, recovery | Assigned per incident |
| Communications | Status page, user notices, support replies | Founder-approved; drafted by product/compliance docs |
| Legal counsel | Notification obligations, privilege, regulator contact | To be engaged (Q-09) |
| Scribe | Timestamped log of actions and decisions | Assigned per incident |

Contact roster (names, phones, vendor support lines) lives in a private location, not in this repo. To be created at M2.

## 4. Process

| Phase | Actions |
|---|---|
| **1. Detect & report** | Sources: monitoring alerts, user reports, vendor notices, staff, security researchers. Anyone can declare an incident. Open an incident record immediately. |
| **2. Triage** | Assign IC and severity; start timeline; establish a private channel; preserve evidence (logs, snapshots) before changing systems where feasible. |
| **3. Contain** | Stop the harm first: disable feature via flag/kill switch, revoke sessions/tokens, rotate secrets, block traffic, put feed in "stale/unavailable" state, take service to maintenance mode if needed. |
| **4. Eradicate** | Remove root cause: patch, config fix, remove malicious access, purge wrongly stored data. |
| **5. Recover** | Restore from known-good state; verify data integrity (reconcile bets/P&L, odds sanity checks); monitor closely; re-enable features gradually. |
| **6. Notify** | Founder + counsel determine obligations to users, regulators, partners, app stores, vendors. See §6. |
| **7. Review** | Blameless post-incident review within 5 business days (SEV1/2): timeline, root cause, what worked, action items with owners and dates. |

Guardrails during incidents:
- Production credential use and production changes still follow Founder gates (G-03, G-09); the Founder may pre-authorise an emergency procedure at M2.
- **No destructive data operation** (G-08) without Founder approval and a verified backup, even under time pressure.
- Do not delete evidence. Do not communicate externally without Founder approval.

## 5. Playbooks (summaries)

### 5.1 Suspected personal-data exposure
1. Contain access path; snapshot logs.
2. Determine: what data (see PRIVACY_AND_DATA inventory), whose, how many, how long, accessed by whom.
3. Rotate any related credentials; revoke sessions if accounts affected.
4. Founder + counsel assess notification duties (state breach laws vary; contractual duties to vendors/partners).
5. Prepare user notice: what happened, what data, what we did, what users should do.

### 5.2 Leaked secret / credential
1. Rotate immediately (do not wait to confirm exploitation).
2. Search for use of the secret in access logs.
3. Purge from history where practical; assume compromised regardless.
4. Add detection so the class of leak is caught in CI.

### 5.3 Account takeover / credential stuffing
1. Raise rate limits/blocks; force logout and password reset for affected accounts.
2. Notify affected users (G-06 applies).
3. Review for data viewed (bet history) and treat as privacy incident if accessed.

### 5.4 Wrong or stale data shown as current
1. Flip affected feed to "unavailable/stale" state; show banner.
2. Identify window and affected markets; determine if best-line or calculators consumed bad data.
3. Correct data; add validation (range checks, cross-book sanity, timestamp monotonicity).
4. If users may have relied on it: in-app notice; note in status history. Never silently fix a material error.

### 5.5 Assistant failure (invented number, unsafe output, data leak)
1. Disable the assistant or the failing tool via kill switch.
2. Capture the minimal reproduction (respect privacy: redact user content).
3. Add the case to the grounding/refusal test suite before re-enabling.
4. Cross-user data exposure ⇒ treat as SEV1 privacy incident.

### 5.6 Sync vendor incident (M3+)
1. Suspend sync; revoke/rotate vendor tokens as advised.
2. Obtain vendor's written incident details; assess impact on OddVex users.
3. Notify affected users per Founder/counsel decision; offer disconnect + data deletion.

### 5.7 Data-provider outage or licence problem
1. Stale-state UI; pause alerts (M3+) to avoid acting on stale prices.
2. If licence dispute/termination: follow contract's cease-use and deletion clauses; counsel involved.

### 5.8 Failed deploy / migration
1. Roll back application; do **not** improvise destructive DB fixes.
2. Restore from backup only with Founder approval; re-apply deletion ledger after restore.

### 5.9 Under-21 user identified
1. Disable account; delete data per policy; record minimal incident note.
2. Counsel to confirm any further duty (AG-03).

### 5.10 Legal, regulator, or app-store notice
1. Do not respond substantively; forward to Founder immediately (G-10).
2. Preserve relevant records; counsel leads response.

### 5.11 Harmful UGC / moderation failure (M5+)
1. Remove/limit content; action account; preserve evidence.
2. Escalate anything involving threats, minors, or illegality to Founder + counsel.

### 5.12 Published banned claim or misleading marketing
1. Remove or correct immediately; record where it appeared and for how long.
2. Review approval path; add to BRAND_VOICE checks.

## 6. Notification decision record (to be completed with counsel per incident)

| Question | Answer |
|---|---|
| Was personal data involved? Which categories? | |
| Residents of which states/countries affected? | |
| Is notification to individuals required/advisable? By when? | Counsel |
| Regulators / attorneys general? | Counsel |
| Partners/vendors with contractual notice rights (data provider, sync vendor, processor, stores)? | |
| Insurer notification? | |
| Public statement / status page? | Founder |

Pre-work for M2: counsel to supply a breach-notification matrix (PR-10) so timelines are known before an incident.

## 7. Communication templates (drafts; Founder approval required before any send)

**Status banner (data issue):** "Some odds data is currently delayed. Prices shown may be out of date and are marked as stale. We're working on it."

**User notice (security/privacy) — outline:** what happened · when · what information was involved · what we have done · what you can do · how to contact us · no speculation, no minimising language.

## 8. Readiness checklist

- [ ] On-call roster and private contact list created (M2)
- [ ] Monitoring/alerting covers auth anomalies, error rates, data freshness (M2)
- [ ] Kill switches exist for assistant, sync, alerts, each data feed (M2/M3)
- [ ] Backup restore tested (M2)
- [ ] Counsel-provided notification matrix on file (M2)
- [ ] Tabletop exercise run for: data exposure, wrong odds, leaked secret (M2)
- [ ] Status page / in-app banner mechanism available (M2)
- [ ] Incident record template and post-incident review template in place (M2)
- [ ] Security contact published (before public launch)

## 9. M1 applicability

During M1 (no production, no users): treat any committed secret, any real personal data appearing in fixtures, and any use of real brand/player/sportsbook names as SEV4 incidents — fix, record, and add a preventive check.

Note of 2026-11-21: the paragraph above was written before the private preview existed. The preview runs in production mode with an open sign-up API (see the status line at the top), so the full plan, including the data-breach paths, applies to it now; the SEV4 rule above still applies to the repository.
