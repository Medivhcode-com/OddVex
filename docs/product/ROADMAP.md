# OddVex — Roadmap (M1–M6)

Last updated: 2026-11-21 (status lines for M2 to M6 added from the code at commit `2b0c7c1` and the server records in `BUILD_STATUS.md`) · Feature IDs reference [MASTER_FEATURE_INVENTORY.md](./MASTER_FEATURE_INVENTORY.md)

- Milestones are **scope-and-exit-criteria based, not date based.** No dates are committed in this document.
- **Only M1 is in build.** M2–M6 are planned; their order is a proposal for Founder confirmation.
- Nothing in M1 touches real money, real customers, real sportsbook accounts, paid services, or production.

## Milestone overview

| MS | Name | Theme | State |
|---|---|---|---|
| M1 | Foundation & Core Research | Full research loop on synthetic data | **In build** |
| M2 | Real Data & Production Foundations | Licensed data, production infra, account lifecycle, closed beta | Planned |
| M3 | Engagement & Mobile Parity | Alerts/push, mobile feature parity, real sync vendor | Planned |
| M4 | Premium & Advanced Intelligence | Billing/entitlements, LLM assistant, projections/backtesting | Planned |
| M5 | Community & Admin Console | UGC with moderation, full admin console | Planned |
| M6 | Store Submission & Public Launch | App Store / Play, launch marketing, hardening | Planned |

---

## M1 — Foundation & Core Research (in build)

**Scope**

| Area | In scope |
|---|---|
| Governance & platform | Repo governance, monorepo, CI, design system (PLAT-01/02) |
| Marketing website | All marketing routes incl. draft legal pages and methodology (MKT-01/02/03/06) |
| Web app | Dashboard, Games/Live scores, Odds comparison, Prop analyzer, Calculators, Parlay research, Bet tracker, Assistant, Settings |
| Sync | Adapter interface + **mock** adapter (SYNC-01/02/03) |
| OddVex AI | **Rule-based v0** (AI-01…AI-06) |
| Auth | Email/password, sessions, RBAC (AUTH-01/03/07); 21+ attestation (AUTH-02, verify) |
| Admin | Basic overview endpoint (ADMN-01) |
| Mobile | First slice: games + odds (MOB-01, GAME-09, ODDS-11) |
| Data | Synthetic fixtures, provider abstraction, freshness metadata (DATA-01/02/04) |

**Explicitly not in M1:** real data provider, alerts/notifications/push, watchlists/favorites persistence, community, premium billing/entitlements, full admin console, LLM-backed assistant, model projections/backtesting, store submission, production infrastructure, any real email.

**Exit criteria**

- [ ] Every "Built in M1" item in the inventory demonstrated end-to-end locally/CI; every "M1 — verify" item resolved to Built or moved to a later milestone.
- [ ] CI green: lint, type-check, unit tests, a11y checks, dependency scan.
- [ ] Calculator reference vectors pass; one shared maths implementation (AC-INTL-1/2).
- [ ] Assistant grounding test passes: no number without a tool source (AC-AI-1).
- [ ] "Demo data" labelling present on all data surfaces (NFR-04); no real team/player/sportsbook names or logos anywhere.
- [ ] Mock sync never requests real credentials (AC-SYNC-2).
- [ ] Per-user authorization tests pass for tracker, sync, assistant.
- [ ] All four states (loading/empty/stale/error) implemented for each screen in SCREEN_MAP marked M1.
- [ ] Marketing and in-app copy passes BRAND_VOICE banned-claims check; RG footer with the National Problem Gambling Helpline, 1-800-MY-RESET (1-800-697-3738), present.
- [ ] No secrets in repo; no production deployment performed.
- [ ] Founder demo and written M1 review completed.

## M2 — Real Data & Production Foundations (planned)

**Status as of 2026-11-16:** built without crossing a gate, on synthetic data: watchlist persistence, auto-settlement, line movement, account deletion and export, audit log, mobile sign-in and account settings (mobile unverified on a device). In progress: email verification and password reset that write to an outbox table and send nothing. Not built: hedge and arbitrage calculators, waitlist, analytics. Gated and not started: licensed data provider and historical odds from a real feed (G-01; provider choice deferred), production infrastructure (G-02, G-03; Vercel, Neon and Resend are stated preferences, not approvals; plan in `infrastructure/DEPLOYMENT_PLAN.md`), real email (G-06), counsel review (G-10; packet in `docs/compliance/COUNSEL_REVIEW_PACKET.md`), closed beta. No exit criterion below is met. See `BUILD_STATUS.md`.

**Status as of 2026-11-21:** email verification and password reset are built and switched off in production, where nothing is sent. A private preview runs in production mode on the Hostinger server (D-016, D-021 in `DECISION_LOG.md`): `preview.oddvex.com` behind a password and `api-preview.oddvex.com` open to the internet and accepting sign-ups, with daily database dumps kept 14 days on the same server. It replaced the Vercel and Neon preference. Public production on `oddvex.com`, real email, a data licence, counsel review (packet reissued 2026-11-21, not sent) and a closed beta are not started. No exit criterion below is met.

**Scope:** licensed provider integration (DATA-03), historical odds store (DATA-05), line movement (ODDS-07), auto-settlement (TRKR-06), favorites/watchlists persistence (GAME-05, PROP-07, HOME-04), email verification/reset (AUTH-04), account deletion/export (AUTH-06), admin audit log + basic data health (ADMN-07/04), production infrastructure (PLAT-03), analytics (PLAT-04), waitlist (MKT-04), mobile auth (MOB-02), hedge/arb calculators (INTL-07), closed web beta.

**Exit criteria**

- [ ] Data licence signed (Founder gate) and its display, caching, storage, attribution and naming terms implemented and documented.
- [ ] Freshness SLOs defined from real provider behaviour; stale handling verified against live feed outages.
- [ ] Counsel review of Terms, Privacy Policy, RG page, age-gating approach complete for beta.
- [ ] Account deletion and export work end-to-end and are tested, including backups policy.
- [ ] Production environment provisioned with backups, monitoring, alerting, secrets management (SECURITY_BASELINE) — Founder gate.
- [ ] Incident-response runbook exercised once (tabletop).
- [ ] Closed beta cohort approved by Founder; beta feedback loop in place.

## M3 — Engagement & Mobile Parity (planned)

**Status as of 2026-11-16:** built without crossing a gate: alerts engine and in-app notifications with per-type preferences (evaluated when the app is opened or by script; no background worker), weekly staking reminder (a reminder, not a limit), mobile screens for props, calculators, parlay research and tracker (never run on a device). In progress: feature flags. Not built: MFA, alt lines, injuries and lineups, quiet hours. Gated and not started: push and email delivery (G-02, G-06), real sync vendor (G-01), outbound sportsbook links (G-10, G-11; no decision), VoiceOver and TalkBack pass (needs device testing).

**Status as of 2026-11-21:** feature flags are built (`services/api/src/oddvex_api/flags/catalog.py`). On the preview a worker evaluates alerts and grades community picks every two minutes; delivery is still in-app only. The mobile app has one Android test build and has not been reported as run on a device.

**Scope:** alerts engine and push/email notifications (INTL-11, NOTF-01/02, ODDS-12, PROP-08, GAME-08), mobile parity for props/tools/parlay/tracker (PROP-09, INTL-12, PRLY-07, TRKR-11), real sync vendor (SYNC-05/07), alt lines/markets (ODDS-10), injuries/lineups (GAME-07), feature flags (ADMN-06), MFA (AUTH-05), RG tools (SET-03, TRKR-10), outbound sportsbook links if approved (ODDS-09).

**Exit criteria**

- [ ] Notification consent, preferences and quiet-hours behaviour implemented; notification copy passes RG review (no inducement to bet).
- [ ] Sync vendor due diligence complete; no sportsbook credentials stored by OddVex; consent copy reviewed by counsel.
- [ ] Mobile app reaches agreed parity list; a11y pass with VoiceOver and TalkBack.
- [ ] Decision recorded on affiliate/outbound links after counsel's state-by-state review.

## M4 — Premium & Advanced Intelligence (planned)

**Status as of 2026-11-16:** in progress without crossing a gate, on synthetic data: entitlements without billing (both plans identical, gating off), a market discrepancy (value) screen, advanced tracker analytics. Their wording has not had the claims review this milestone calls for (G-14). Gated and not started: pricing and billing (G-07, G-11), LLM-backed assistant (G-01), projections and backtesting, quantified correlation.

**Status as of 2026-11-21:** entitlements without billing, the value screen (switched on by default) and tracker analytics are built. Their wording has still not had the claims review (G-14).

**Scope:** entitlements and billing (PREM-01…07), LLM-backed assistant with eval suite (AI-07/08/09/11/12, ADMN-09), projections and backtesting (PROP-06, INTL-10), market discrepancy screen (INTL-09), quantified correlation (PRLY-06), advanced tracker analytics (TRKR-13).

**Exit criteria**

- [ ] Pricing and packaging approved by Founder; auto-renewal, cancellation and trial flows reviewed by counsel.
- [ ] Payment processor and store billing approved for this business category.
- [ ] LLM assistant passes eval thresholds (to be defined) for numeric fidelity, refusals and injection resistance before any user exposure; AI disclosure reviewed.
- [ ] Any projection shown to users has published methodology, backtest results, and uncertainty; no accuracy claim in marketing without substantiation reviewed by counsel.

## M5 — Community & Admin Console (planned)

**Status as of 2026-11-16:** built: a read-only admin overview page. In progress: admin user management, and a community module behind a flag that is off by default. Gated: turning community on for anyone (G-10; no guidelines, moderation policy, reporting flow or staffing exist).

**Status as of 2026-11-21:** built: the web admin console (users, suspension, plans, flags, audit log, outbox), staff export and delete routes in the API (no web screen at `2b0c7c1`), and the community module with draft guidelines, reports, blocks, a moderation queue on the web and a restore route in the API, all behind the `community` switch, which is off. Still missing before it can be switched on: counsel review, a written moderation policy, appeals, staffing, and a decision on the leaderboard order. No administrator exists on the preview.

**Scope:** COMM-01…08, ADMN-02/03/05/08.

**Exit criteria**

- [ ] Community guidelines, moderation policy, reporting/blocking, and appeal process live; moderation coverage staffed.
- [ ] UGC legal review complete (see COMPLIANCE_OVERVIEW §UGC).
- [ ] Admin actions fully audit-logged; least-privilege admin roles.
- [ ] Leaderboards decision made after RG review.

## M6 — Store Submission & Public Launch (planned)

**Status as of 2026-11-16:** documentation prepared, nothing executed: `docs/marketing/STORE_SUBMISSION_PREP.md`, `docs/product/GO_NO_GO_TEMPLATE.md`, `docs/product/SUPPORT_READINESS.md`, `infrastructure/ROLLBACK_PLAN.md`, `infrastructure/RUNBOOK.md`, `docs/compliance/THREAT_MODEL.md`. Gated and not started: store accounts and submission (G-04), launch marketing (G-05), production (G-03), penetration test (G-02). The mobile app has never run on a device and no rollback has been rehearsed.

**Status as of 2026-11-21:** a private production-mode preview is deployed (not a public launch) and deploys have run on it; a rollback has not been exercised on the server. A Google Play developer account and an Expo project exist; no Apple account is recorded and nothing is submitted. One Android test APK exists (debug-signed, not for a store).

**Scope:** App Store and Google Play submission (MOB-03), launch marketing (LAUNCH_PLAN_DRAFT), production hardening, support readiness.

**Exit criteria**

- [ ] Every item in `docs/compliance/LAUNCH_READINESS_CHECKLIST.md` checked or explicitly waived by the Founder in writing.
- [ ] Legal sign-offs recorded.
- [ ] Store review notes, demo account, age rating and privacy declarations prepared and accurate.
- [ ] Security review / penetration test findings resolved or risk-accepted by Founder.
- [ ] Launch go/no-go meeting held; rollback plan documented.

> Sequencing note: M5 and M6 can be swapped (launch before community) if the Founder prefers a smaller launch surface. Store review of UGC features adds requirements; launching without community may reduce review risk — to be decided.

---

## Founder-approval gates

No agent or team member may do any of the following without **explicit, recorded Founder approval** (who, what, when, in the repo or decision log).

| # | Gate | Examples | First likely milestone |
|---|---|---|---|
| G-01 | **Paid APIs and data licences** | Odds/scores/stats provider; LLM API; sync vendor; any metered API | M2 |
| G-02 | **Paid infrastructure** | Cloud hosting, managed DB, CDN, monitoring, email service, paid CI minutes, paid analytics | M2 |
| G-03 | **Production deployment** | First and every production deploy process change; public DNS cut-over for oddvex.com | M2 |
| G-04 | **Store submission** | App Store / Google Play accounts, TestFlight external testing, any submission or listing change | M6 |
| G-05 | **External marketing** | Ads, social posts, press, influencer/affiliate outreach, public waitlist promotion | M2+ |
| G-06 | **Real customer email / messaging** | Any email, SMS or push to real people; collecting real email addresses | M2 |
| G-07 | **Pricing changes** | Setting or changing prices, tiers, trials, discounts, refunds policy | M4 |
| G-08 | **Destructive migrations** | Dropping/rewriting tables or columns with data, irreversible data transforms, bulk deletes | any |
| G-09 | **Production credentials** | Creating, rotating, sharing or using production secrets/keys; granting production access | M2 |
| G-10 | **Legal decisions** | Publishing Terms/Privacy/RG policy as final; entity/licensing/registration choices; accepting vendor contracts; state availability decisions; responding to regulators or legal notices | M2 |
| G-11 | **Anything real-money** | Payments, subscriptions, affiliate revenue, payouts, anything touching user or company funds | M3/M4 |
| G-12 | Real brand/league/sportsbook/player names, logos or likeness | Replacing fictional fixtures with real identities | M2 |
| G-13 | New categories of personal data or new sub-processors | e.g. precise location, date of birth, ID verification, new analytics vendor | any |
| G-14 | Public claims about accuracy, performance, or results | Any "X% accurate"/"beats the market" style statement | M4 |

Default rule: **if unsure whether something is gated, treat it as gated and ask.**

---

## Open questions for the Founder

| # | Question | Needed by |
|---|---|---|
| Q-01 | Confirm milestone order M2→M6 (notably community before or after public launch). | M1 exit |
| Q-02 | Which sports/leagues are in scope for the first real-data release? Drives provider selection and cost. | M2 start |
| Q-03 | Is affiliate revenue (outbound sportsbook links) part of the business model? It materially changes the compliance burden (state affiliate registration, ad rules, store review). | M2 |
| Q-04 | Free vs. Premium split: accept the proposals in the inventory as a starting point, or defer packaging until beta data exists? | M3 |
| Q-05 | Age gating: is self-attestation (21+) acceptable to you pending counsel, or should we plan for date-of-birth collection or stronger verification? | M2 |
| Q-06 | Which states (if any) should be excluded or treated differently at launch? | M2 (with counsel) |
| Q-07 | Budget envelope for data licence, infra and LLM usage. | M2 / M4 |
| Q-08 | Should account deletion and the 21+ attestation be pulled into M1 if not already built ("M1 — verify" items)? | M1 exit |
| Q-09 | Who is the qualified counsel (gaming + privacy + consumer protection) for review, and when can review start? | M2 start |
| Q-10 | Company/legal entity details to appear in legal pages and store listings (Medivh Code legal name, address, support contact). | M2 |
