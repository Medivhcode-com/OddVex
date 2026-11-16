# ADR-0003: Web app talks to the API through a server-side boundary

Status: accepted (M1)

- `apps/web` is one Next.js app holding the marketing site (static) and the product under `/app` (dynamic).
- Pages are React Server Components that fetch from the API on the server. The API base URL is server-only
  configuration (`ODDVEX_API_URL`).
- The session is the API's JWT stored in an `HttpOnly`, `SameSite=Lax` cookie set by server actions. Browser
  JavaScript never sees the token.
- Client components that need data after load (calculators, forms, the assistant) call `/api/ov/*`, a thin route
  handler that forwards to the API's `/v1/*` with the session token, and rejects cross-origin writes.
- The web app contains no odds math. Prices arrive with American, decimal and implied-probability values already
  computed, and calculators call the API's quant endpoints. One engine, one set of tests.
- Types come from `packages/types`, generated from the API's OpenAPI schema. CI fails when they drift.
- Filters live in the URL so they are shareable and survive reloads. Theme and odds format are stored per browser.

## Addendum: request metadata, proxy trust and security headers

### The visitor's address and the request id

- `src/proxy.ts` gives every page request one request id: a well-formed incoming `X-Request-ID`
  (`[A-Za-z0-9._-]{8,64}`, the shape the API accepts) is kept, anything else is replaced with a UUID. The response
  carries it back as `X-Request-ID`.
- The server-side `api()` and the `/api/ov` bridge send that id to the API as `X-Request-ID`, and send the visitor's
  address as a single-value `X-Forwarded-For`. The address is the first `X-Forwarded-For` hop the hosting platform
  reports, else `X-Real-IP` (`src/lib/request-meta.ts`). Without this every web user shared the web server's
  address, and so one per-IP rate-limit bucket.
- An API error keeps the id (`ApiError.requestId`, also set as the error's `digest`), so the app's error screen
  shows "Reference <id>" and the same id is in the API's log line and audit row.
- **Proxy trust.** The API ignores `X-Forwarded-For` unless it runs with `ODDVEX_TRUST_PROXY=true`. Set that only
  when the API is reachable solely through the web server or another trusted proxy. If the API can also be reached
  directly, any caller can forge the header and choose its own rate-limit bucket and audit-log address.
- Two assumptions to check at deployment: (1) the platform in front of the web server must overwrite a
  client-supplied `X-Forwarded-For` rather than append to it, because the web server trusts the first hop;
  (2) mobile clients call the API directly, so "reachable solely through the web server" needs a trusted proxy in
  front of the API for them as well, or the flag stays off.
- Reading request headers makes a route dynamic. `api()` is therefore only called from request-scoped code (the
  `/app` tree, the auth pages, server actions). Marketing pages never call it and stay static; `next build` shows
  them as `○`/`●`.

### Security headers

- Fixed headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`) stay in
  `next.config.ts`. The Content-Security-Policy and HSTS are set by `src/proxy.ts`, because they depend on the
  request and on runtime configuration. The policy text is built by `src/lib/csp.ts`, which is unit-tested.
- Scripts: `script-src 'self'` plus, per page, either a nonce or hashes. No `unsafe-eval` and no `unsafe-inline`
  for scripts in production.
  - Next.js writes inline scripts into every page (the React payload and its bootstrap). The bundled CSP guide
    covers them with a per-request nonce, which needs dynamic rendering. Routes that are already rendered per
    request (`/app`, login, signup, password reset, email confirmation) use that.
  - Using nonces everywhere would make every marketing page dynamic. The guide's nonce-free alternative is
    `'unsafe-inline'`. Instead, `pnpm build` runs `scripts/csp-hashes.mjs` after `next build`; it writes
    `.next/csp-hashes.json` with the SHA-256 hashes of each prerendered page's inline scripts, and the proxy allows
    exactly those for that page. Marketing pages stay static.
  - The theme script in the root layout is allowed by its hash on every page, because the static root layout
    cannot read a nonce. JSON-LD blocks are data, not script, and need no allowance.
  - Trade-off: the manifest must ship with the server (the build script also copies it into the standalone
    output, which is what the Dockerfile copies). If it is missing in production the proxy logs an error and falls
    back to `script-src 'self' 'unsafe-inline'` so the site keeps working. A page that is revalidated at runtime
    (ISR) would get new inline scripts that the manifest does not know; there is none today, and one must not be
    added without changing this.
  - `'strict-dynamic'` from the guide's example is not used: it would make browsers ignore `'self'`, which the
    prerendered pages rely on for their script files.
- Styles: `style-src 'self'` with `style-src-attr 'unsafe-inline'`. Stylesheets are files from this origin and no
  `<style>` element is allowed. Inline style attributes are allowed because charts and meters set computed widths
  and colours through React's `style` prop, and an attribute cannot carry a nonce or hash.
- Also set: `default-src 'self'`, `img-src 'self' data:`, `font-src 'self'`, `connect-src 'self'`,
  `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`, `frame-ancestors 'none'`.
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` and `upgrade-insecure-requests` are sent only
  when `NODE_ENV=production` and `ODDVEX_INSECURE_COOKIES` is not `true`. That flag exists for running the
  production build over plain http on a developer machine and in the e2e suite; it must never be set in production.
- `next dev` adds `'unsafe-eval'`, inline styles and websocket connections, which React and the dev tooling need.
- The e2e suite fails any test in which the browser reports a CSP violation (`e2e/fixtures.ts`).

### Not-found status for `/app/admin`

The `/app` tree streams behind `loading.tsx`, and a streamed response is a `200` even when the page then calls
`notFound()`. The bundled docs say to run such a check before streaming starts. The proxy therefore asks the API
who the visitor is for `/app/admin` only, and rewrites to the not-found page (a real `404`) unless the API says the
visitor is an admin. The page keeps its own check. Other pages that call `notFound()` after loading data (an unknown
game or player id) still answer `200` with the not-found UI and a `noindex` tag; `/app` is not indexed anyway.
