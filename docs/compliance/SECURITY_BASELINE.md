# OddVex — Security Baseline

Last updated: 2026-11-15 · Applies to: FastAPI backend (modular monolith), PostgreSQL, Next.js web, Expo mobile, CI.

Status legend: **M1 req** = required of the M1 build (implementation to be verified by engineering at M1 exit — this document sets the bar, it does not certify it is met). **M2+** = required before production / real users. No production environment exists today.

## 1. Authentication

| # | Control | Level |
|---|---|---|
| AU-01 | Passwords hashed with a memory-hard algorithm (Argon2id preferred; bcrypt acceptable) with per-password salt; never logged, never reversible | M1 req |
| AU-02 | Password policy: minimum length (proposal ≥ 10), no arbitrary composition rules, block known-breached/common passwords (offline list in M1; breach-check service later) | M1 req (length) / M2 |
| AU-03 | Login/signup responses do not reveal whether an email is registered | M1 req |
| AU-04 | Sessions: short-lived access token + rotating refresh token, or server-side sessions; web tokens in `HttpOnly`, `Secure`, `SameSite` cookies — not `localStorage` | M1 req |
| AU-05 | Mobile tokens stored in OS secure storage (Keychain / Keystore via Expo SecureStore) | M2 (when mobile auth ships) |
| AU-06 | Logout invalidates the session server-side; password change revokes other sessions | M1 req / M2 |
| AU-07 | CSRF protection for cookie-authenticated state-changing requests | M1 req |
| AU-08 | Brute-force defence: rate limits + progressive delay on login (see §4) | M1 req |
| AU-09 | Email verification and secure reset (single-use, expiring, hashed tokens) | M2 |
| AU-10 | MFA (TOTP/passkeys) offered to users; **mandatory for admins** | M3 / M2 for admins |
| AU-11 | Re-authentication for sensitive actions (delete account, change email, disconnect sync) | M2 |

## 2. Authorization

| # | Control | Level |
|---|---|---|
| AZ-01 | Deny by default: every endpoint declares its auth requirement; unauthenticated routes are an explicit allow-list | M1 req |
| AZ-02 | Object-level checks on every tracker/sync/assistant/settings resource — queries scoped by `user_id` from the session, never from client input | M1 req |
| AZ-03 | RBAC roles `user`, `admin`; admin endpoints enforce role server-side; 401 vs. 403 correct | M1 req |
| AZ-04 | Automated tests for cross-user access (user A cannot read/modify user B's bets, connections, conversations) | M1 req |
| AZ-05 | Assistant tools execute with the requesting user's identity only; no tool accepts an arbitrary user ID | M1 req |
| AZ-06 | Admin least privilege (split roles: support, moderator, operator) | M5 |
| AZ-07 | Entitlement checks server-side (never client-only) | M4 |

## 3. Secrets and configuration

| # | Control | Level |
|---|---|---|
| SE-01 | No secrets in the repository, fixtures, client bundles, or logs; `.env` files git-ignored; `.env.example` contains placeholders only | M1 req |
| SE-02 | Secret scanning in CI and pre-commit | M1 req |
| SE-03 | Only public configuration in `NEXT_PUBLIC_*` / Expo public env | M1 req |
| SE-04 | Production secrets in a managed secret store; per-environment separation; rotation schedule; access logged | M2 (G-09) |
| SE-05 | Any leaked secret is rotated immediately and treated as an incident | Always |
| SE-06 | Sync vendor tokens encrypted at application level; keys outside the DB | M3 |
| SE-07 | Production credentials created/used only with Founder approval (G-09) | Always |

## 4. Rate limiting and abuse prevention

Proposed starting limits (tune with real traffic):

| Surface | Limit (proposal) | Level |
|---|---|---|
| Login | 5 attempts / 15 min per account + per-IP ceiling | M1 req (basic) |
| Signup | 5 / hour per IP | M1 req (basic) |
| Password reset / verification emails | 3 / hour per account | M2 |
| Assistant | 30 messages / 5 min per user (cost control matters more at M4) | M1 req (basic) |
| General API (authenticated) | Per-user token bucket | M1 req (basic) |
| Public/unauthenticated API | Per-IP token bucket | M1 req (basic) |
| Sync trigger | 1 manual sync / few minutes per connection | M3 |

Also: request body size limits; pagination caps; 429 with `Retry-After`; distributed store for counters in production (M2); edge/WAF protection and bot mitigation (M2); CAPTCHA only if abuse observed (accessibility impact considered).

## 5. Input, output and transport

| # | Control | Level |
|---|---|---|
| IO-01 | Schema validation on all inputs (Pydantic); strict types for odds/stakes; decimal money | M1 req |
| IO-02 | Parameterised queries / ORM only; no string-built SQL | M1 req |
| IO-03 | Output encoding by framework defaults; no `dangerouslySetInnerHTML` with untrusted content; markdown from assistant/UGC sanitised | M1 req |
| IO-04 | Security headers: CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy`, frame-ancestors | M1 req (CSP baseline) / M2 hardened |
| IO-05 | CORS: explicit allow-list of origins; no wildcard with credentials | M1 req |
| IO-06 | TLS for all deployed environments; DB connections encrypted | M2 |
| IO-07 | Error responses carry no stack traces or internals | M1 req |
| IO-08 | Assistant: treat all user text and retrieved text as untrusted; tools have fixed schemas; no free-form SQL/tool invocation from model output; prompt-injection tests | M1 req (rule-based) / M4 (LLM) |
| IO-09 | File uploads: none in M1; if added — type/size validation, malware scan, separate origin | Later |

## 6. Audit logging

| # | Control | Level |
|---|---|---|
| AL-01 | Log security events: signup, login success/failure, logout, password change, role change, admin endpoint access, sync connect/disconnect, deletion/export requests | M1 req (core auth + admin access) / M2 full |
| AL-02 | Each record: timestamp (UTC), actor ID, action, target, result, request ID, source IP (coarse where possible) | M1 req |
| AL-03 | Never log: passwords, tokens, full cookies, sync tokens, bet notes, assistant message bodies | M1 req |
| AL-04 | Audit log is append-only and access-restricted; retention 12 months (proposal) | M2 |
| AL-05 | **All admin write actions are audit-logged with a reason field before any admin write capability ships** (ADMN-07) | M2 |
| AL-06 | Alerts on anomalies: login-failure spikes, admin access from new location, mass export/deletion | M2 |
| AL-07 | Structured logs with request correlation IDs | M1 req |

## 7. Dependency and code scanning

| # | Control | Level |
|---|---|---|
| DS-01 | Lockfiles committed for all packages (JS and Python); reproducible installs in CI | M1 req |
| DS-02 | Dependency vulnerability scanning in CI for JS and Python (e.g. `npm/pnpm audit`, `pip-audit` or equivalent); fail on high/critical with documented exceptions | M1 req |
| DS-03 | Automated dependency update PRs | M1 req (if free tooling) |
| DS-04 | Static analysis (linting, type-checking; security linters such as Bandit/Semgrep-equivalent) | M1 req (lint/types) / M2 (SAST) |
| DS-05 | Secret scanning (see SE-02) | M1 req |
| DS-06 | Licence scanning for dependencies | M2 |
| DS-07 | CI hardening: least-privilege tokens, pinned actions, no secrets exposed to fork PRs, protected main branch with required reviews | M1 req |
| DS-08 | Container/image scanning and SBOM | M2 |
| DS-09 | Independent penetration test before public launch | M6 (G-02 cost) |

## 8. Data protection and backups

| # | Control | Level |
|---|---|---|
| BK-01 | Encryption at rest for database and backups | M2 |
| BK-02 | Automated daily backups + point-in-time recovery for PostgreSQL | M2 |
| BK-03 | Backup retention: rolling 30–35 days (aligns with deletion policy) | M2 |
| BK-04 | Backups stored in a separate account/region from primary; access restricted and logged | M2 |
| BK-05 | **Restore test** at least quarterly and before launch; record RTO/RPO achieved | M2 |
| BK-06 | Proposed targets: RPO ≤ 24 h (≤ 15 min with PITR), RTO ≤ 4 h — to be confirmed by Founder against cost | M2 |
| BK-07 | Deletion ledger re-applied after any restore (see PRIVACY_AND_DATA §4) | M2 |
| BK-08 | Migrations: reviewed, reversible where possible, tested on a copy; **destructive migrations need Founder approval (G-08)** and a verified backup | Always |
| BK-09 | No production data in dev/test; fixtures are synthetic only | M1 req |
| BK-10 | Environment separation: dev / staging / production with separate databases and credentials | M2 |

## 9. Infrastructure and operations (M2+)

- Least-privilege cloud IAM; MFA for all operator accounts; no shared accounts.
- Private networking for the database; no public DB endpoint.
- Centralised logs, metrics, uptime checks, error monitoring with PII scrubbing.
- Patch cadence for base images and runtimes.
- Documented access reviews (quarterly) and off-boarding.
- Mobile: release builds without debug flags; no secrets embedded in the app binary; OTA update channel protected.

## 10. Vulnerability disclosure

- Publish a security contact (e.g. `security@` address and `/.well-known/security.txt`) before public launch — needs a real mailbox (G-06).
- Triage targets (proposal): acknowledge in 3 business days; critical fix or mitigation in 7 days.

## 11. M1 verification checklist (for engineering at M1 exit)

- [ ] Password hashing algorithm and parameters documented
- [ ] Cross-user access tests present and passing (tracker, sync, assistant, settings)
- [ ] Admin overview endpoint returns 401/403 correctly and exposes aggregates only
- [ ] Secret scan clean on full git history
- [ ] Dependency scan clean or exceptions documented
- [ ] Cookies flagged `HttpOnly`/`Secure`/`SameSite`; CSRF protection in place
- [ ] Basic rate limits on login, signup, assistant
- [ ] Logs contain no passwords, tokens, or message bodies
- [ ] No real personal data or real credentials in fixtures
- [ ] CORS allow-list explicit
