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
