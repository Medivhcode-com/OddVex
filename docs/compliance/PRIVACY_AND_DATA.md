# OddVex — Privacy and Data Handling

Last updated: 2026-11-21 · Status: internal engineering/product policy draft. "As built" statements describe the code at commit `2b0c7c1`. **Not the public Privacy Policy and not legal advice**; the public policy (`/privacy`) must be drafted/reviewed by counsel.

## 1. Principles

1. **Minimise.** Collect only what a shipped feature needs.
2. **No credentials for third parties.** OddVex never stores sportsbook usernames or passwords.
3. **User control.** Access, export and deletion are self-serve (M2) and never obstructed.
4. **No sale of personal data.** No sharing for cross-context behavioural advertising.
5. **Purpose-bound.** Betting records are used to provide the tracker and the user's own insights — not for profiling, advertising, or sharing with sportsbooks.
6. **Honest state.** A private preview has run on a rented server in production mode since 2026-11-18 (`docs/product/DECISION_LOG.md`, D-021). Its API is open to the internet and accepts sign-ups from anyone, so it can hold real email addresses, password hashes and IP addresses; whether anyone outside the team has signed up cannot be seen from the repository. No processor is engaged by contract. This document describes design intent plus what the code handles; where the two differ, it says so.

## 2. Data inventory

Legend — **Built**: `Yes` handled by the code at `2b0c7c1` (and so by the private preview); `Later` planned. Sensitivity: L / M / H (internal classification, not a legal category).

| # | Data | Examples | Purpose | Source | Sens. | Stored where | Built | Shared with |
|---|---|---|---|---|---|---|---|---|
| D-01 | Account identity | Email, display name, user ID, role, plan, status (active or suspended), last sign-in time, email-confirmed time, time of last password change, a token version, and a folded copy of the email and display name used by the staff search (`users.search_key`) | Authentication, account | User | M | PostgreSQL | Yes | Nobody |
| D-02 | Credential | Password **hash** only (argon2id) | Authentication | User | H | PostgreSQL | Yes | Nobody |
| D-03 | Age attestation & legal acceptance | 21+ confirmation time only. **No terms or privacy version is stored** | Eligibility record | User | M | PostgreSQL | Yes (time only) | Nobody |
| D-04 | Preferences | Odds format, theme. No time zone is stored | Personalisation | User | L | Browser cookie and storage (web); app storage (mobile). Not in the database | Yes | Nobody |
| D-05 | Bet records | Sportsbook, market, selection, odds, stake, result, dates, notes | Tracker | User / sync | **H** | PostgreSQL | Yes (at most 5,000 per account) | Nobody |
| D-06 | Sync connection metadata | Provider, status, last synced, vendor token reference | Sync | Vendor / mock | H | PostgreSQL (token encrypted or vendor-side) | Yes (mock only, no token) | Sync vendor (M3) |
| D-07 | Sportsbook credentials | Username/password | — | — | — | **Never collected or stored** | n/a | n/a |
| D-08 | Session data | Access token and expiry. No refresh token | Auth | System | H | httpOnly cookie (web); operating-system secure storage (mobile). The server keeps only a token version per account | Yes | Nobody |
| D-09 | Assistant messages | User questions, responses | Answering; (later) history | User | M–H | Not stored. A support reply writes one log record holding only the case and whether the person was signed in | Yes (transient) | LLM provider (M4, under contract) |
| D-10 | Parlay drafts | Legs | Parlay research | User | L | Client state M1; persisted M2 | M1 (client) | Nobody |
| D-11 | Favorites / watchlists | Teams, players, games | Personalisation | User | L | PostgreSQL | Yes | Nobody |
| D-12 | Alerts & notification tokens | Alert rules, in-app notifications, notification preferences, staking-reminder amount. No push tokens | Notifications | User/device | M | PostgreSQL | Yes (in-app only); push later | Push services (APNs/FCM/Expo), later |
| D-13 | Server logs | API request line: time, method, path without query string, status, duration, request id and `client_ip`, the address of the direct peer. On the preview that is the shared reverse proxy or the web server, not the visitor (`infrastructure/RUNBOOK.md` section 3); with no proxy in front of the API it would be the visitor's IP address. The visitor's address is stored in the audit log (D-14). No user agent, no user ID, no request body. Other lines in the same log: `assistant_support_reply` (D-09), which can be matched by time to its request line; `alert_evaluation_failed` with the user ID when an alert evaluation fails; and `user <id>: failed` from the worker's alert script | Security, debugging | System | M | Container logs on the preview server; no size limit or retention rule set. The shared reverse proxy (Caddy) keeps its own logs, which this project does not control and which were not inspected (not verified) | Yes | Nobody by contract (the server is Hostinger's) |
| D-14 | Security audit events | Sign-ins, failures, account and data actions, admin actions and reads: user id, action, item id, IP address, request id, details | Security | System | M | `audit_log` table (rows only added by application code; no separate store) | Yes | Nobody |
| D-15 | Product analytics | Event names + properties per taxonomy (no stakes, no free text) | Product improvement | System | M | Analytics vendor/store | Later (M2) | Analytics vendor (TBD) |
| D-16 | Approximate location | State/region derived from IP or user-declared | State availability (if adopted) | System/user | M | PostgreSQL / derived | Later (decision pending) | Nobody |
| D-17 | Billing | Subscription status, processor customer ID (no card numbers held by OddVex) | Premium | Processor/stores | H | PostgreSQL + processor | Later (M4) | Payment processor, app stores |
| D-18 | Support messages | Email content | Support | User | M | The mailbox `support@oddvex.com` (exists; that it receives mail is not verified). No support tool | Mailbox only | Mail host (Hostinger) |
| D-19 | Community content | Profile (handle, bio), picks with optional reasoning, comments, follows, likes, blocks, reports with a copy of the reported text | Community | User | M | PostgreSQL | Yes, behind the `community` switch (off) | Public (by design), when switched on |
| D-20 | Waitlist | Email | Launch comms | User | M | TBD | Later (M2, G-06) | Email vendor |
| D-21 | Sports/odds data | Synthetic provider output | Product | Synthetic provider (M1) / licensed provider (M2) | L (non-personal) | Not persisted (served from provider, per ADR-0002); persisted from M2 | Yes | — |
| D-22 | Email tokens and outbox | Hash of each verification or reset token; the full text of each email the product would have sent, with the recipient address | Account recovery and verification | System | M | PostgreSQL | Yes. The email flows are off in production, so the preview writes none | Nobody (nothing is sent) |
| D-23 | Staff action records | The reason an administrator gives for exporting or deleting an account (free text) | Accountability | Staff | M | `audit_log` details | Yes | Nobody |
| D-24 | Reserved community handles | The handle of a suspended account that was deleted, and the date | Stop a suspended person taking the same handle again | System | L–M | PostgreSQL | Yes | Nobody |

**Not collected (current intent):** date of birth, government ID, SSN, precise geolocation, contacts, payment card data, sportsbook credentials, biometric data. Adding any requires Founder approval (G-13) and counsel review.

## 3. Retention

### 3.1 As built (code at `2b0c7c1`)

| Data | Kept | Notes |
|---|---|---|
| Account data (D-01 to D-06, D-11, D-12, D-19, D-22) | Until the account is deleted, by its owner or by an administrator | Removed from the live database at once |
| Audit log (D-14, D-23) | No end date; nothing removes entries | After a deletion the account's earlier entries stay with its opaque id, action, item id, request id, **IP address** and details, plus an entry for the deletion. No email address. An earlier README called this "no personal data"; an IP address may be personal data |
| Daily database dumps | 14 days (`ODDVEX_BACKUP_KEEP_DAYS`), pruned only after a new dump succeeds | Each holds every account as it was then, emails and password hashes included. All on the same server; no copy elsewhere |
| Pre-deploy dumps | The newest five | Taken at every deploy |
| Restore leftovers | No end date | A restore keeps a dump of the replaced database and the replaced database itself |
| Reserved handles (D-24) | No end date | No administrator route releases one |
| Copies of reported text | Until the report is deleted, with the reporter's or the reported author's account | Kept even if the author deleted the content |
| Notifications | At most 500 per user | — |
| Server logs (D-13) | No rule set | Logs from releases before 2026-11-19 included query strings |

The public draft (`/privacy`, `apps/web/src/app/(marketing)/privacy/page.tsx` at `2b0c7c1`) states the account data, the audit log entries with their IP addresses and details, the daily and pre-release dumps and the reserved handle. It does not mention restore leftovers, copies of reported text, the 500-notification cap, the server logs (D-13) and their lack of a retention rule, the assistant's support log record (D-09), or the shared reverse proxy's own logs, which may hold visitors' addresses (not inspected) (owner question OQ-22). On the preview the API request line holds the proxy's or the web server's address, not the visitor's, so the visitor addresses the API stores are the ones in the audit log, which the page does mention. None of this has been reviewed by counsel.

### 3.2 Proposed defaults — to be confirmed by counsel

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

**As built:** deletion is immediate, from Settings on web and mobile after typing DELETE, with no password prompt, no
pending state, no de-identification of audit entries and no deletion ledger. An administrator can delete an account on
its owner's behalf (`POST /v1/admin/users/{user_id}/delete`, with a reason and the account's email address typed), using
the same code. What remains afterwards is listed in section 3.1. The table below is the design intent and is **not
built**.

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

**Export as built:** one JSON file from web Settings (`GET /v1/me/export`), at most 10 an hour per account; the mobile app has no export. It holds the account details, bets, watchlist, alert rules, notifications and their preferences, the staking reminder, sync connections and import runs, the account's own audit entries (with IP addresses) and its community data. It leaves out the password hash, the last sign-in time, the time of the last password change, the account status and stored outbox messages. An administrator can produce the same file for an owner who cannot sign in (`POST /v1/admin/users/{user_id}/export`, with a reason). No procedure exists for checking that such a request comes from the owner, or for sending the file (`docs/backlog/owner-questions.md`).

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

- No analytics SDK is installed in the web or mobile app (code at `2b0c7c1`). Taxonomy: `docs/marketing/ANALYTICS_EVENT_TAXONOMY.md`.
- Prohibited in events: email, exact stake/payout amounts, bet notes, assistant message text, tokens, IP beyond coarse region.
- No advertising pixels in the authenticated app. Marketing-site trackers require consent review (PR-06).
- Honour Global Privacy Control and do-not-sell/share requests if/when applicable (counsel).

## 7. Third parties / sub-processors

None engaged by contract as of this date. Hostinger hosts the server that runs the private preview and stores what its API collects (email addresses, password hashes, IP addresses, bets), and hosts the `support@oddvex.com` mailbox; whether that makes Hostinger a sub-processor needing gate G-13 and an agreement is a question for counsel. Expected categories later, each requiring Founder approval and a data-processing agreement:

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
| Access / portability | Self-serve export | Built (web); staff export for an owner who cannot sign in, procedure not written |
| Deletion | Self-serve (see §4) | Built (web and mobile); staff deletion for an owner who cannot sign in, procedure not written |
| Correction | Edit profile and bets in-app | M1 |
| Opt-out of marketing | Unsubscribe link; preferences | M2/M3 |
| Opt-out of sale/share | Not applicable while no sale/share occurs; mechanism if that changes | — |
| Appeal / contact | `support@oddvex.com` exists and the contact page invites data-rights requests; no separate privacy address | Partly |

## 9. Children and minors

OddVex is for adults 21+. It is not directed to children. We do not knowingly collect data from anyone under 21; credible indications lead to account closure and deletion (process to be confirmed by counsel, AG-03). As built, an administrator can delete an account, but no written procedure exists, and a statement to the assistant that the user is under 21 is not stored against the account and sets no flag. The only trace is one `assistant_support_reply` log line (case `underage`, signed in or not; no message text, no user id), written in the same container log as the request line (D-13), so the two can be matched by time. On the preview the request line holds the shared reverse proxy's or the web server's address, not the user's, and the assistant writes no audit row; whether the shared reverse proxy's own logs hold the user's address was not inspected (not verified). The container logs have no retention rule.

## 10. Open questions

| # | Question | For |
|---|---|---|
| PD-Q1 | Is the assistant truly non-persistent in M1 (including logs)? | Engineering. Answered 2026-11-21 from the code at `2b0c7c1`: no message text is stored or logged; each support reply writes one log record with the case and whether the person was signed in. The request log holds the path only |
| PD-Q2 | May/should we keep an attestation record after account deletion? | Counsel |
| PD-Q3 | Do we need state/region data, and how is it obtained (IP vs. declared)? | Founder + counsel |
| PD-Q4 | Deletion grace period (e.g. 14 days undo) or immediate? | Founder |
| PD-Q5 | Analytics vendor choice and hosting region | Founder (G-02) |
| PD-Q6 | Legal response timelines for access/deletion requests | Counsel |
