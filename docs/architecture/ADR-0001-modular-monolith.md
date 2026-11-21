# ADR-0001: One API service, internal modules

Status: accepted (M1)

## Context

The initial plan listed separate `services/api`, `services/odds`, `services/ai`, `services/notifications` and an
`apps/admin`. There is one team, no production traffic and no licensed data feed yet.

## Decision

Ship a single FastAPI application, `services/api`, organized as modules with explicit boundaries:

| Module | Responsibility | Would become its own service when |
|---|---|---|
| `quant` | Pure odds math. No I/O. | Never. It is a library. |
| `providers` | `SportsDataProvider` contract and adapters | Ingestion needs its own scaling or schedule |
| `assistant` | Intent router, data tools, explainer | An LLM runtime needs isolation or separate scaling |
| `sync` | Sportsbook-account sync contract and adapters | A vendor webhook volume requires it |
| `auth`, `db`, bets, admin | Accounts, persistence, tracking, operations | Not planned |

The admin console is a route group in `apps/web` (`apps/web/src/app/app/admin`) behind the `admin` role, not a
separate app, until it needs different deployment or access controls.

## Consequences

One deployable, one database, one test suite. Module boundaries are enforced by convention and review: modules talk
through their public functions and protocols, and `quant` imports nothing from the rest of the app.
