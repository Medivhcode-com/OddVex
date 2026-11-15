# OddVex — Privacy and Data Handling

Last updated: 2026-11-15 · Status: internal engineering/product policy draft. **Not the public Privacy Policy and not legal advice**; the public policy (`/privacy`) must be drafted/reviewed by counsel.

## 1. Principles

1. **Minimise.** Collect only what a shipped feature needs.
2. **No credentials for third parties.** OddVex never stores sportsbook usernames or passwords.
3. **User control.** Access, export and deletion are self-serve (M2) and never obstructed.
4. **No sale of personal data.** No sharing for cross-context behavioural advertising.
5. **Purpose-bound.** Betting records are used to provide the tracker and the user's own insights — not for profiling, advertising, or sharing with sportsbooks.
6. **Honest state.** In M1 there are no real users, no production environment and no third-party processors. This document describes design intent plus what M1 code handles.

## 2. Data inventory

Legend — **Built**: `M1` handled by the current build (local/CI only); `Later` planned. Sensitivity: L / M / H (internal classification, not a legal category).

| # | Data | Examples | Purpose | Source | Sens. | Stored where | Built | Shared with |
|---|---|---|---|---|---|---|---|---|
| D-01 | Account identity | Email, user ID, role | Authentication, account | User | M | PostgreSQL | M1 | Nobody (M1) |
| D-02 | Credential | Password **hash** only | Authentication | User | H | PostgreSQL | M1 | Nobody |
| D-03 | Age attestation & legal acceptance | 21+ flag, timestamp, Terms/Privacy version | Eligibility record | User | M | PostgreSQL | M1 — verify | Nobody |
| D-04 | Preferences | Odds format, time zone | Personalisation | User | L | PostgreSQL | M1 | Nobody |
| D-05 | Bet records | Sportsbook, market, selection, odds, stake, result, dates, notes | Tracker | User / sync | **H** | PostgreSQL | M1 | Nobody |
| D-06 | Sync connection metadata | Provider, status, last synced, vendor token reference | Sync | Vendor / mock | H | PostgreSQL (token encrypted or vendor-side) | M1 (mock only) | Sync vendor (M3) |
| D-07 | Sportsbook credentials | Username/password | — | — | — | **Never collected or stored** | n/a | n/a |
| D-08 | Session data | Session/refresh tokens, expiry | Auth | System | H | Server store / httpOnly cookie | M1 | Nobody |
| D-09 | Assistant messages | User questions, responses | Answering; (later) history | User | M–H | Not persisted in M1 (engineering to verify); persisted M4 | M1 (transient) | LLM provider (M4, under contract) |
| D-10 | Parlay drafts | Legs | Parlay research | User | L | Client state M1; persisted M2 | M1 (client) | Nobody |
| D-11 | Favorites / watchlists | Teams, players | Personalisation | User | L | PostgreSQL | Later (M2) | Nobody |
| D-12 | Alerts & notification tokens | Rules, push tokens | Notifications | User/device | M | PostgreSQL | Later (M3) | Push services (APNs/FCM/Expo) |
| D-13 | Server logs | IP address, user agent, request path, user ID, timestamps | Security, debugging | System | M | Log store | M1 (local) | Hosting/logging vendor (M2) |
| D-14 | Security audit events | Logins, failures, admin actions | Security | System | M | Append-only store | Partial M1 / M2 | Nobody |
| D-15 | Product analytics | Event names + properties per taxonomy (no stakes, no free text) | Product improvement | System | M | Analytics vendor/store | Later (M2) | Analytics vendor (TBD) |
| D-16 | Approximate location | State/region derived from IP or user-declared | State availability (if adopted) | System/user | M | PostgreSQL / derived | Later (decision pending) | Nobody |
| D-17 | Billing | Subscription status, processor customer ID (no card numbers held by OddVex) | Premium | Processor/stores | H | PostgreSQL + processor | Later (M4) | Payment processor, app stores |
| D-18 | Support messages | Email content | Support | User | M | Support tool | Later (M2) | Support/email vendor |
| D-19 | Community content | Posts, profile, reports | Community | User | M | PostgreSQL | Later (M5) | Public (by design) |
| D-20 | Waitlist | Email | Launch comms | User | M | TBD | Later (M2, G-06) | Email vendor |
| D-21 | Sports/odds data | Synthetic provider output | Product | Synthetic provider (M1) / licensed provider (M2) | L (non-personal) | Not persisted in M1 (served from provider, per ADR-0002); persisted from M2 | M1 | — |

**Not collected (current intent):** date of birth, government ID, SSN, precise geolocation, contacts, payment card data, sportsbook credentials, biometric data. Adding any requires Founder approval (G-13) and counsel review.

## 3. Retention (proposed defaults — to be confirmed by counsel)

| Data | Proposed retention | Notes |
|---|---|---|
| Account, preferences, bet records, sync metadata | Life of account; deleted on account deletion | — |
| Age attestation / legal acceptance record | Life of account; whether a minimal record may/should be kept after deletion — counsel | Open |
| Sessions | Until expiry/logout | Short-lived access tokens |
| Assistant messages | Not persisted (M1). When persisted: user-deletable; proposed default 12 months | Decide at M4 |
| Server logs | 30–90 days | Shorter is better; security needs to be balanced |
| Security audit events | 12 months | May contain user IDs; pseudonymise on account deletion |
| Analytics events | 14 months or less; de-identified on deletion | Vendor-dependent |
| Backups | Rolling window (proposal: 30–35 days) | Deleted data ages out with rotation |
| Billing records | As required for tax/accounting | Counsel/accountant |
| Deleted-account tombstone | Minimal non-identifying marker to prevent accidental restore | — |
| Inactive accounts | Proposal: notify then delete after 24 months of inactivity | Founder decision |

## 4. Deletion flow (AUTH-06; M2 — required before any real user)

| Step | Action | Notes |
|---|---|---|
| 1 | User requests deletion in Settings (web and in-app on mobile) | Also via support email as fallback |
| 2 | Show scope and irreversibility; offer export | See USER_JOURNEYS J10 |
| 3 | Re-authenticate | Password (and MFA when available) |
| 4 | Immediately: revoke sessions; disable login; mark account `pending_deletion` | — |
| 5 | Revoke sync connections with vendor; request vendor-side data deletion | Retry queue; logged |
| 6 | Hard-delete from primary DB: D-01–D-06, D-08–D-12, D-16–D-17 references; delete or anonymise D-19 content | Single idempotent job with verification query |
| 7 | De-identify analytics and audit events (replace user ID with irreversible tombstone) | — |
| 8 | Propagate to processors (analytics, email, LLM logs, support) | Per-vendor API or request |
| 9 | Backups: not restored selectively; data expires with rotation; if a backup is restored, re-apply deletion list | Deletion ledger kept (IDs only) |
| 10 | Confirm completion to user (on-screen; email when G-06 is approved) | — |

Targets (proposal): primary-store deletion within 7 days of request, typically immediate; full propagation incl. backups within the backup rotation window. Legal response deadlines to be confirmed by counsel.

Exceptions: data we are legally required to retain (e.g. billing records) is isolated and access-restricted; listed in the public policy.

**Export:** machine-readable (JSON/CSV) covering account, preferences, bets, sync metadata, saved items, and (when persisted) assistant history.

## 5. Sync-credential handling principles

| # | Principle |
|---|---|
| SC-1 | OddVex **never asks for, receives, transmits through its servers, logs, or stores** sportsbook usernames/passwords. |
| SC-2 | Real sync (M3) uses a vendor-hosted link flow; the user authenticates with the vendor, not with OddVex. |
| SC-3 | OddVex stores only vendor-issued, revocable, scoped tokens/references — encrypted at rest with keys held outside the database; never exposed to the client after exchange; never logged. |
| SC-4 | Read-only scope: bet history only. No ability to place bets, move funds, or change account settings. If a vendor cannot offer read-only scope, it is not used. |
| SC-5 | Explicit, specific consent before connecting, stating what is imported and from whom; consent record stored. |
| SC-6 | One-tap disconnect revokes the token at the vendor and offers deletion of imported data. |
| SC-7 | Vendor due diligence before selection: authorization basis with sportsbooks, security attestations, breach history, data-use limits (no resale), deletion support, sub-processors. Founder gate G-01; counsel review. |
| SC-8 | No scraping, credential stuffing, or automated login to sportsbooks by OddVex — ever. |
| SC-9 | Mock adapter (M1): no credential fields exist in the UI; labelled as demo; uses synthetic bets only. |
| SC-10 | Synced data is used only for the user's tracker and insights; never sold or shared; excluded from analytics payloads. |

## 6. Analytics and tracking rules

- No analytics SDK is active in M1 (verify). Taxonomy: `docs/marketing/ANALYTICS_EVENT_TAXONOMY.md`.
- Prohibited in events: email, exact stake/payout amounts, bet notes, assistant message text, tokens, IP beyond coarse region.
- No advertising pixels in the authenticated app. Marketing-site trackers require consent review (PR-06).
- Honour Global Privacy Control and do-not-sell/share requests if/when applicable (counsel).

## 7. Third parties / sub-processors

None engaged as of this date. Expected categories later, each requiring Founder approval and a data-processing agreement:

| Category | Milestone | Data involved |
|---|---|---|
| Cloud hosting / managed DB / logging | M2 | All |
| Transactional email | M2 | Email, message metadata |
| Product analytics / error monitoring | M2 | D-13, D-15 |
| Sports data provider | M2 | Non-personal (confirm no user data flows back) |
| Push delivery | M3 | Device tokens |
| Sync vendor | M3 | Bet history, connection tokens |
| LLM provider | M4 | Assistant prompts + tool results |
| Payment processor / app stores | M4 | Billing identifiers |

A public sub-processor list should be maintained from M2.

## 8. User rights handling (design intent; scope to be confirmed by counsel)

| Right | Mechanism | Milestone |
|---|---|---|
| Access / portability | Self-serve export | M2 |
| Deletion | Self-serve (see §4) | M2 |
| Correction | Edit profile and bets in-app | M1 |
| Opt-out of marketing | Unsubscribe link; preferences | M2/M3 |
| Opt-out of sale/share | Not applicable while no sale/share occurs; mechanism if that changes | — |
| Appeal / contact | privacy contact address (to be created; G-06) | M2 |

## 9. Children and minors

OddVex is for adults 21+. It is not directed to children. We do not knowingly collect data from anyone under 21; credible indications lead to account closure and deletion (process to be confirmed by counsel, AG-03).

## 10. Open questions

| # | Question | For |
|---|---|---|
| PD-Q1 | Is the assistant truly non-persistent in M1 (including logs)? | Engineering |
| PD-Q2 | May/should we keep an attestation record after account deletion? | Counsel |
| PD-Q3 | Do we need state/region data, and how is it obtained (IP vs. declared)? | Founder + counsel |
| PD-Q4 | Deletion grace period (e.g. 14 days undo) or immediate? | Founder |
| PD-Q5 | Analytics vendor choice and hosting region | Founder (G-02) |
| PD-Q6 | Legal response timelines for access/deletion requests | Counsel |
