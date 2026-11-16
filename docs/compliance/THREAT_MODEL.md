# OddVex — Threat model

Last updated: 2026-11-16 · Method: STRIDE per trust boundary · Status: **first pass, written from the code on `main`
at commit `bdd77a5`. Not reviewed by a security specialist. No penetration test has been done.**

> Not a certification and not legal advice. This lists what the code does today, what it does not do, and who should
> pick up each gap. "Mitigation" means a control that exists in a cited file, not a control that has been attacked
> and held.

Scope: `services/api` (FastAPI), `apps/web` (Next.js), `apps/mobile` (Expo), the database, CI. Nothing is deployed,
so hosting, network and vendor threats are stated as requirements for when it is.

Out of scope until they exist: licensed data provider, real sportsbook sync vendor, language-model assistant,
billing, push and email delivery, community. Each needs its own pass before it ships.

In progress and not covered: feature flags, entitlements, the value screen, tracker analytics, admin user
management, email verification and password reset writing to an outbox, and a community module behind a flag that
is off by default. They are being built in the API and are not yet in `services/api/README.md`. **Re-run this model
when they merge** (section 8).

## 1. Assets

| # | Asset | Where | Why it matters |
|---|---|---|---|
| A-1 | Password hashes | `users.password_hash` | Account takeover if cracked. argon2id |
| A-2 | Email addresses and display names | `users` | Personal data |
| A-3 | Bet records: sportsbook, selections, stakes, results, notes | `bets`, `bet_legs` | Financial behaviour. Rated highest sensitivity in PRIVACY_AND_DATA (D-05) |
| A-4 | Weekly staking reminder threshold and week total | `stake_reminders` | Could suggest a gambling concern |
| A-5 | Watchlist, alert rules, notifications | `watchlist_items`, `alert_rules`, `notifications` | Interests and behaviour |
| A-6 | Access tokens (JWT) | Web: `ov_session` cookie. Mobile: SecureStore | Bearer credential, valid for up to `ODDVEX_JWT_TTL_MINUTES` |
| A-7 | `ODDVEX_JWT_SECRET` | API environment | Anyone holding it can mint a token for any user id, including admins |
| A-8 | `DATABASE_URL` | API environment | Full database access |
| A-9 | Audit log, including IP addresses | `audit_log` | Evidence; also personal data that survives account deletion |
| A-10 | Admin role | `users.role`, `ODDVEX_ADMIN_EMAILS` | Sees service counts and the audit log today; user management is in progress |
| A-11 | Integrity of numbers | `services/api/src/oddvex_api/quant`, `board.py` | A wrong price or payout misleads a betting decision |
| A-12 | Honesty labels: `data_mode`, stale flags, "Synthetic data" | API responses and UI | Constitution section 2 |
| A-13 | Source and CI | GitHub | Supply chain |
| A-14 | Sportsbook credentials | **Not collected or stored anywhere** | Listed so that nobody adds them |

## 2. Trust boundaries and data flow

```
 [Browser] ==B1== [Next.js server: pages, server actions, /api/ov proxy] ==B2== [FastAPI] ==B3== [PostgreSQL]
 [Mobile app] ===================B4==================================== [FastAPI]
 [Operator / CI] ==B5== [environment variables, scripts, migrations] == [FastAPI, PostgreSQL]
 [GitHub: contributors, Actions, dependencies] ==B6== [build artifacts]
```

| Boundary | Crossing | Authentication | Notes |
|---|---|---|---|
| B1 | Browser to Next.js | `ov_session` cookie: `HttpOnly`, `SameSite=Lax`, `Secure` in production (`apps/web/src/lib/session.ts`) | The browser never sees the token (ADR-0003) |
| B2 | Next.js server to API | Forwards the user's JWT as a bearer header (`apps/web/src/lib/api.ts`, `apps/web/src/app/api/ov/[...path]/route.ts`) | **No service-to-service credential.** The API cannot tell the web server from any other client. The API is as public as its hostname |
| B3 | API to database | Database credential in `DATABASE_URL` | ORM only (`db/models.py`); no string-built SQL found |
| B4 | Mobile to API | Bearer JWT from SecureStore (`apps/mobile/src/session/store.ts`) | Direct, over the public internet. `EXPO_PUBLIC_API_URL` is public |
| B5 | Operators and scripts | Whoever holds the environment | `scripts/seed_demo.py`, `scripts/evaluate_alerts.py`, Alembic |
| B6 | Contributors and dependencies | GitHub permissions | `.github/workflows/ci.yml`, `.github/dependabot.yml`, `.github/CODEOWNERS` |

## 3. Threats, current mitigations and gaps

Risk is a coarse judgement for **launch with real users**: H, M or L. Owner names a role, not a person. To be
assigned: Founder.

### 3.1 Spoofing

| # | Threat | Boundary | Current mitigation (file) | Residual risk or gap | Risk | Proposed owner and next step |
|---|---|---|---|---|---|---|
| S-1 | Password guessing or credential stuffing | B2, B4 | argon2id (`auth/security.py`); per-IP limit of 10 per minute across register, login and password change (`ratelimit.py`, `auth/router.py`); failed logins audited (`auth.login_failed`); dummy hash keeps timing uniform for unknown emails | Limit is per IP only, not per account. No lockout or progressive delay (SECURITY_BASELINE AU-08 asks for one). No breached-password check (AU-02). Counters are per process and reset on restart | H | Backend: per-account limit and shared counter store before launch. Founder: G-02 if the store is paid |
| S-2 | Stolen access token replayed | B1, B4 | Token expires after `ODDVEX_JWT_TTL_MINUTES` (60). Password change bumps `token_version` and rejects all earlier tokens (`deps.py`, `auth/router.py`). Web cookie is `HttpOnly` | **Logout does not revoke anything.** Web logout only deletes the cookie (`apps/web/src/lib/auth-actions.ts`); a copied token stays valid until it expires. No refresh tokens, no per-session list, no device view. SECURITY_BASELINE AU-04 and AU-06 are not met | M | Backend: server-side logout (bump `token_version` or session table). Decide with refresh-token design |
| S-3 | No second factor | B1, B4 | None | No MFA for users or admins. SECURITY_BASELINE AU-10 makes MFA mandatory for admins before production | H for admins | Backend: MFA for admin accounts before any production admin exists. Founder: confirm it blocks launch |
| S-4 | Admin by email allowlist, with no email verification | B5, B2 | `ODDVEX_ADMIN_EMAILS` promotes on register or login (`auth/router.py`); role is checked from the database on each request (`deps.py`) | Whoever **registers a listed address first** becomes admin; ownership of the address is never proven. Promotion is not audited. Removing an address does not demote | H | Operations: only list addresses that already have an account (RUNBOOK section 8). Backend: require a verified email for promotion once verification lands; audit role changes |
| S-5 | Forged JWT | B2, B4 | HS256 with issuer check and required `exp`, `sub`, `iat`; algorithm pinned (`auth/security.py`). Production refuses to start with the development secret or one under 32 characters (`config.py`) | One symmetric secret, no key id, no overlap during rotation. The `role` claim in the token is not trusted for authorization, which is correct, but it is still emitted | M | Operations: generate and store per RUNBOOK section 7 (G-09). Backend: consider key ids when rotation without sign-out is wanted |
| S-6 | Client forges its address to dodge limits or poison audit rows | B2, B4 | Forwarded header ignored unless `ODDVEX_TRUST_PROXY=true`; then only the last entry is used, capped at 64 characters (`ratelimit.py`) | Correct only behind exactly one trusted proxy. The web proxy route forwards the browser's own `X-Forwarded-For` unchanged; with a platform proxy in front the chain length is unknown | M | Operations: confirm the header chain on the chosen host before enabling (DEPLOYMENT_PLAN section 5) |
| S-7 | Impersonating the web server to the API | B2 | Not needed: the API authorizes by user token only | No gap in authorization. It does mean network allowlisting of the API is impossible while mobile calls it directly | L | None |
| S-8 | Phishing or lookalike domain | B1 | None in code | No HSTS on the web app (`apps/web/next.config.ts`). Whether the host adds it: to confirm | M | Web: add HSTS, or confirm the host does |

### 3.2 Tampering

| # | Threat | Boundary | Current mitigation (file) | Residual risk or gap | Risk | Proposed owner and next step |
|---|---|---|---|---|---|---|
| T-1 | Cross-site request forgery against cookie-authenticated writes | B1 | `SameSite=Lax` cookie (`session.ts`); proxy rejects non-GET requests whose `Origin` host differs from `Host` (`api/ov/[...path]/route.ts`); proxy forwards only an allowlist of `/v1` prefixes | A request with **no** `Origin` header passes the proxy check. Server actions rely on the framework's own protections, which have not been reviewed here against the Next.js 16 documentation. Behind a proxy that rewrites `Host`, the comparison needs re-testing | M | Web: review server-action protections in the bundled Next.js docs; test the origin check on the real host |
| T-2 | Cross-site scripting | B1 | React escaping. `dangerouslySetInnerHTML` is used only for JSON-LD built with `JSON.stringify` and a fixed theme script (`apps/web/src/app/layout.tsx`, marketing pages). API responses carry `Content-Security-Policy: default-src 'none'` (`middleware.py`) | **The web app sends no Content-Security-Policy** (`next.config.ts`). The inline theme script means a policy needs a nonce or hash. JSON-LD via `JSON.stringify` does not escape `</script>`; safe only while the content is authored in the repository, not user-supplied | M | Web: add a CSP with nonces; keep user content out of JSON-LD. Becomes H when community content exists |
| T-3 | SQL injection | B3 | SQLAlchemy ORM and bound parameters throughout `services/api/src` | None found. Not independently reviewed | L | Security review at penetration test |
| T-4 | User changes another user's records | B2, B4 | Every bet, watchlist, alert, notification and sync query is filtered by the authenticated user; another user's id returns 404. Cross-user tests in `services/api/tests/test_api_bets.py`, `test_api_alerts.py`, `test_api_notifications.py`, `test_api_watchlist.py`, `test_api_account.py` | New modules in progress have not been checked. Authorization is by convention in each route, not enforced centrally | M | Backend: cross-user tests for every new module are a merge condition |
| T-5 | Tampering with numbers shown to users | B2 | All math is in `quant/` with tests; the web and mobile apps compute nothing (ADR-0003). Stale, suspended and unavailable quotes are excluded from best price (ADR-0002) | Data is synthetic. Integrity of a real feed (provider compromise, wrong mapping) is unmodelled | M at real data | Backend with data provider selection (G-01): sanity checks and freshness monitors |
| T-6 | Oversized or malformed input | B2, B4 | Pydantic validation; body limit `ODDVEX_MAX_BODY_BYTES` with 413 for declared and streamed bodies (`middleware.py`); list caps (bets `limit` up to 1000, 200 watchlist items, 100 active alerts, 500 notifications kept) | Limits exist per feature, not globally | L | None |
| T-7 | Malicious dependency or CI change | B6 | Lockfile for JavaScript with `--frozen-lockfile`; Dependabot weekly for npm, pip and Actions; gitleaks on full history; workflow token is `contents: read` (`ci.yml`) | **No Python lockfile**: `pip install -e ".[dev]"` resolves version ranges at build time, in CI and in the Docker image. **No vulnerability audit job** (SECURITY_BASELINE DS-02 requires one). Actions are pinned to tags, not commit ids (DS-07). No image scan or SBOM (DS-08). `CODEOWNERS` names a placeholder team. Whether `main` branch protection is on cannot be seen from the repository | H | Founder: decide the audit job, CODEOWNERS team and branch protection (open decisions in DECISION_LOG). Backend: pin Python dependencies |
| T-8 | Tampering with the audit log | B3 | Rows are only ever added by application code | Any database credential can alter or delete rows. No separate store, no integrity check. AL-04 (append-only, restricted) is not met | M | Operations: restrict database roles at provisioning. Backend: consider export to a write-once store |
| T-9 | Migration damages data | B5 | Migrations 0001 to 0003 are additive and tested up and down in CI on SQLite and PostgreSQL | The Docker image runs `alembic upgrade head` at every start, so a migration ships the moment an image starts. Every downgrade drops data | M | Operations: migrations as an explicit release step (DEPLOYMENT_PLAN section 6). G-08 for anything destructive |

### 3.3 Repudiation

| # | Threat | Current mitigation (file) | Residual risk or gap | Risk | Proposed owner and next step |
|---|---|---|---|---|---|
| R-1 | A user or operator denies an action | Audit rows for auth events, password changes, bet create, settle, auto-settle and delete, watchlist, alert rules and firings, notification deletion, preference and reminder changes, sync, export and account deletion, with request id and IP (`deps.py` `write_audit`) | **Admin access is not audited**: `GET /v1/admin/overview` writes no audit row (`api/admin.py`). Role promotion is not audited. Logout is not an API event. AL-01 lists all three | M | Backend: audit admin reads and role changes before admin write actions ship (AL-05) |
| R-2 | Operator actions outside the app (scripts, manual SQL, config changes) | None | No record except what the host keeps | M | Operations: decision log entry for every production change (RUNBOOK section 11); host audit logs to confirm with vendor docs |
| R-3 | Request cannot be traced end to end | Request id on every API response and log line (`middleware.py`) | The web server does not pass a request id to the API, so a web error cannot be joined to an API log line | L | Web: forward `X-Request-ID` |

### 3.4 Information disclosure

| # | Threat | Boundary | Current mitigation (file) | Residual risk or gap | Risk | Proposed owner and next step |
|---|---|---|---|---|---|---|
| I-1 | One user reads another's bets or settings | B2, B4 | As T-4 | As T-4 | M | As T-4 |
| I-2 | Account enumeration | B2 | Login returns one message for unknown email and wrong password; timing equalised (`auth/security.py`) | **Registration answers `409 email_taken`** (`auth/router.py`), which confirms an address has an account. SECURITY_BASELINE AU-03 and SCREEN_MAP A-02 say this must not be revealed. For a betting-related product, membership itself is sensitive | M | Backend and Founder: decide the registration response once email verification exists. Counsel: note in privacy review |
| I-3 | Token leaks through logs, URLs or storage | B1, B4 | Token in `HttpOnly` cookie on web and SecureStore on mobile; never in a URL; access log records path only, not headers or bodies (`middleware.py`) | Query strings are not logged by the API, but the host's own logs may record them. No query string carries a secret today | L | Operations: check host log contents at provisioning |
| I-4 | Sensitive data in logs | B5 | Access line has method, path, status, duration, IP. No bodies. Audit `details` hold ids, kinds, counts and results, not notes or free text (checked across `write_audit` call sites) | IP addresses in logs and in `audit_log.ip`. Unhandled errors log a full stack trace, which could include values from the failing line. Retention undecided | M | Founder with counsel: retention. Backend: review what stack traces can contain |
| I-5 | Personal data survives account deletion | B3 | `DELETE /v1/me` removes the user and cascades to bets, legs, watchlist, alerts, notifications, preferences, reminder, sync connections and runs (`db/models.py`, `auth/router.py`) | **Audit rows keep the user id and the IP address of every past action.** Server logs and any backups keep everything until they age out. No deletion ledger exists to re-apply after a restore. PRIVACY_AND_DATA section 4 describes re-authentication, a pending state and de-identification, none of which the code does | H | Counsel: is retaining id and IP after deletion acceptable, and for how long. Backend: deletion ledger; scrub or coarsen `audit_log.ip` |
| I-6 | Data in transit | B1 to B4 | API adds HSTS in production (`middleware.py`). Mobile release builds refuse cleartext (`apps/mobile/README.md`) | Nothing in code forces TLS to the database; it depends on the URL. Web has no HSTS (S-8) | M | Operations: require TLS in `DATABASE_URL`; confirm with vendor docs |
| I-7 | Data at rest | B3 | None in the application | No field-level encryption. Bet notes, stakes and the reminder threshold are plain columns. Database and backup encryption depend on the host (BK-01): to confirm with vendor docs | M | Operations at provisioning |
| I-8 | Admin overview exposes personal data | B2 | Returns counts, provider health and the last 25 audit rows (`api/admin.py`). Web page returns 404 to non-admins (`apps/web/src/app/app/admin/page.tsx`) | Audit rows include user ids and action details, though not IP. SCREEN_MAP D-01 says "no per-user personal data"; user ids with actions are per-user | L | Product: reconcile the document or the endpoint |
| I-9 | API documentation exposed | B2 | `/docs` and `/openapi.json` are disabled when `ODDVEX_ENV=production` (`main.py`) | `openapi.json` is committed to the repository anyway. Not a secret | L | None |
| I-10 | Cross-origin reads | B2 | CORS allowlist, no credentials, `*` refused in production (`main.py`, `config.py`); `Cross-Origin-Resource-Policy: same-site` | None found | L | None |
| I-11 | Demo account with a published password | B5 | `seed_demo.py` refuses production without `--allow-production`; auto-seed is ignored in production | Staging runs as production in the plan, so it is covered. A preview environment in `development` mode with auto-seed on would expose a known login on a public URL | M | Operations: never enable auto-seed on a reachable host; protect previews |
| I-12 | Secrets in the repository | B6 | gitleaks on every push and pull request with full history (`ci.yml`); `.env.example` files hold names and development defaults only | No pre-commit hook (SE-02 asks for both). The documented demo password and development JWT secret are in the repository by design and must never be used on a reachable host | L | Engineering: optional pre-commit hook |
| I-13 | Data export misuse | B2, B4 | Authenticated, owner-only, audited, never includes the password hash (`account/router.py`) | No re-authentication before export or deletion (AU-11). A stolen session can take the full history in one request | M | Backend: re-authentication for export, deletion and password-adjacent actions |

### 3.5 Denial of service

| # | Threat | Current mitigation (file) | Residual risk or gap | Risk | Proposed owner and next step |
|---|---|---|---|---|---|
| D-1 | Flooding expensive endpoints | Per-IP limits on auth and assistant only (`ratelimit.py`); body size limit | **No limit on any other route**: public data routes, calculators, bets, alerts, export. In-memory, per process. No edge protection | H | Operations: edge rate limiting or firewall on the host (to confirm with vendor docs, G-02). Backend: general per-user and per-IP limits (SECURITY_BASELINE section 4) |
| D-2 | Locking real users out through the shared web bucket | None | All web sign-ins reach the API from the web server's address, so they share one 10-per-minute bucket. One script hitting the login form can block every web user from signing in. Also a self-inflicted outage at modest traffic | H | Web and backend: decide how the client address is passed and trusted, or move the limit. Must be resolved before real traffic |
| D-3 | Argon2 cost as an amplifier | Auth rate limit | Each login attempt costs memory and CPU by design. Bounded only by D-2's bucket | M | Covered by D-1 and D-2 |
| D-4 | Alert evaluation load | Per-user throttle `ODDVEX_ALERT_EVAL_MIN_SECONDS` (`alerts/throttle.py`); caps on rules | Throttle is in memory and per process. Evaluation runs inside a read request | L | Backend: move to a worker when one exists |
| D-5 | Large export | Built in memory in one response (`services/api/README.md`) | Bounded by per-user caps except bets, which are uncapped in count | L | Backend: stream or cap if accounts grow |
| D-6 | Memory growth in the limiter | Empty keys pruned past 10,000 entries (`ratelimit.py`) | Non-empty keys are never pruned beyond their window; a wide address spread grows memory until windows pass | L | Covered by a shared store |
| D-7 | Database exhaustion | `pool_pre_ping` (`db/session.py`) | Default pool settings, untested against any real host or instance model | M | Operations: test in staging |
| D-8 | Loss of the single database | None | No backups exist because nothing exists | H at launch | Operations: DEPLOYMENT_PLAN section 11; restore test before launch |

### 3.6 Elevation of privilege

| # | Threat | Current mitigation (file) | Residual risk or gap | Risk | Proposed owner and next step |
|---|---|---|---|---|---|
| E-1 | User reaches admin functions | `require_admin` checks the stored role (`deps.py`); tests in `test_api_admin.py`; `/api/ov` proxy does not forward `/v1/admin` | Two roles only. No least-privilege split (AZ-06). Admin user management is in progress and raises the stakes of S-3 and S-4 | M, rising | Backend: admin MFA and audited admin writes with a reason field before any admin write ships (AL-05) |
| E-2 | Self-promotion through the allowlist | As S-4 | As S-4 | H | As S-4 |
| E-3 | Holder of the JWT secret becomes anyone | Production start-up checks (`config.py`) | Secret handling is entirely procedural until a secret store exists (SE-04) | H | Founder: G-09 process. Operations: managed secret store, least access |
| E-4 | Open redirect after login used for phishing | `safeNext` accepts only same-site relative paths (`apps/web/src/lib/session.ts`) | None found | L | None |
| E-5 | Container escape or root in container | Both images run as a non-root user (`services/api/Dockerfile`, `apps/web/Dockerfile`) | Base images are not pinned by digest and not scanned | M | Engineering: image scanning (DS-08) |
| E-6 | Entitlement bypass | Not applicable: no plans enforced on `main` | Entitlements without billing are in progress. Checks must be server-side (AZ-07) | — | Backend: tests that a free account cannot reach a gated route |
| E-7 | Assistant used to reach other users' data or run instructions | Keyword and template router with fixed tools; no language model (`assistant/`); the assistant route writes nothing to the database or logs | Not applicable until a model is connected (M4). Prompt injection must be modelled then | L today | Backend at M4 |

## 4. Mobile-specific

| # | Threat | Current mitigation | Gap | Risk | Owner and next step |
|---|---|---|---|---|---|
| M-1 | Token theft from the device | SecureStore only; nothing account-related in AsyncStorage (`apps/mobile/README.md`) | **Never run on a device.** SecureStore behaviour on real hardware, backup exclusion and behaviour on a rooted or jailbroken device are unobserved | M | Mobile: device testing (open decision) |
| M-2 | Interception | Release builds block cleartext by platform default | No certificate pinning. Not proposed for launch | L | None |
| M-3 | Secrets in the bundle | Only `EXPO_PUBLIC_API_URL`, which is public | Anything added under `EXPO_PUBLIC_*` ships to every user | L | Mobile: keep it that way (SE-03) |
| M-4 | Over-the-air update channel | None configured (no EAS project) | Unmodelled until one exists | — | Mobile, with G-04 |
| M-5 | Screen capture or app-switcher snapshot showing bets | None | Not assessed | L | Mobile: decide at device testing |

## 5. Abuse and trust threats that are not classic security

| # | Threat | Current mitigation | Gap | Owner |
|---|---|---|---|---|
| X-1 | Under-21 user signs up | 21+ attestation required by the API and both clients (`auth/schemas.py`); timestamp stored | Self-attestation only. No version of the terms is stored with it, although COMPLIANCE_OVERVIEW AG-01 says one is | Counsel (AG-01); Founder (Q-05) |
| X-2 | Synthetic data mistaken for real | `data_mode` on responses; "Synthetic data" labels; fictional names (ADR-0002) | A public deployment on synthetic data depends entirely on those labels staying visible | Product; Founder at G-03 |
| X-3 | Notification wording that pushes betting | All wording in `notifications/templates.py`; banned-phrase scan in `tests/test_notification_copy.py` | Scan covers templates, not future channels | Compliance review per release |
| X-4 | Staking reminder mistaken for a limit | Copy says reminder, not limit, on API, web and mobile | A user may still rely on it. It counts only bets recorded in OddVex, in UTC weeks | Counsel (packet section 5) |
| X-5 | Bulk fake accounts | Per-IP auth limit | No email verification on `main`, no CAPTCHA (deliberately, for accessibility) | Backend when verification lands |

## 6. Top risks before any real user

Ordered by judgement, not by score.

1. **D-2 / S-1**: web sign-ins share one rate-limit bucket; limits are per process and per IP only.
2. **S-4 / E-2**: admin by allowlist without verified email, and no demotion path.
3. **S-3**: no MFA for admins.
4. **T-7**: no dependency audit in CI, no Python lockfile, placeholder CODEOWNERS, branch protection unconfirmed.
5. **I-5**: IP and user id retained after deletion; no deletion ledger; backups will resurrect deleted accounts.
6. **D-1**: no general rate limiting or edge protection.
7. **S-2**: logout does not revoke the token; no refresh tokens.
8. **T-2 / S-8**: no CSP and no HSTS on the web app.
9. **R-1**: admin access and role changes are not audited.
10. **D-8**: backups and restore are unproven because nothing is provisioned.
11. No penetration test (SECURITY_BASELINE DS-09; needs spend, G-02).
12. Mobile app never run on a device (M-1).

## 7. Assumptions

- The API will be reachable from the public internet because the mobile app calls it directly.
- The host terminates TLS. Certificates and their renewal are the host's job: to confirm with vendor docs.
- One API process per instance. Instance count and lifetime on the chosen host are unknown.
- No third party receives user data today. Each one added later is G-13.

## 8. Review triggers

Re-run this model when any of these merges or changes:

- [ ] Feature flags, entitlements, value screen, tracker analytics (in progress)
- [ ] Admin user management (in progress): every admin write action
- [ ] Email verification and password reset (in progress): token generation, expiry, single use, enumeration through
      the reset form, what the outbox table stores, and the moment a real sender is connected (G-06)
- [ ] Community behind a flag (later): user content changes T-2, adds moderation and reporting threats
- [ ] A real data provider, sync vendor, language model, push service or payment processor
- [ ] First deployment to any reachable host
- [ ] Any new category of personal data (G-13)

## 9. Sign-off

| Role | Name | Date | Notes |
|---|---|---|---|
| Author | Launch-readiness documentation pass | 2026-11-16 | Written from code; not a security review |
| Engineering reviewer | | | |
| Independent security reviewer | | | |
| Founder (risk acceptance for anything left open at launch) | | | |
