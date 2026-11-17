# Agent guide

Read `PROJECT_CONSTITUTION.md` first. It is binding. This file is the practical map.

## Layout

| Path | What | Stack |
|---|---|---|
| `apps/web` | Marketing site and web app | Next.js 16 (App Router), React 19, Tailwind 4, TypeScript |
| `apps/mobile` | iOS/Android app | Expo, React Native, TypeScript |
| `services/api` | The backend, a modular monolith | Python 3.13, FastAPI, SQLAlchemy 2, Alembic |
| `packages/types` | TypeScript types generated from the API's OpenAPI schema | openapi-typescript |
| `data/fixtures` | Synthetic sample data used by contract tests | JSON |
| `data/external` | Third-party open data for the internal replay preview. Raw files are never committed (real names) | CSV, Parquet, JSON |
| `docs/` | Architecture, product, design, research, compliance, marketing | Markdown |

Top-level `services/odds`, `services/ai`, `services/notifications` and `apps/admin` from the original plan do not
exist as separate deployables. They are modules inside `services/api` (see `docs/architecture/ADR-0001`).

## Commands

```bash
# API
cd services/api && python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest            # tests
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/uvicorn oddvex_api.main:app --reload --port 8000

# Web
pnpm install
pnpm --filter @oddvex/web dev          # needs the API on :8000
pnpm --filter @oddvex/web lint && pnpm --filter @oddvex/web typecheck && pnpm --filter @oddvex/web test
pnpm --filter @oddvex/web test:e2e     # Playwright; starts API + web itself

# After changing any API response model
cd services/api && .venv/bin/python scripts/export_openapi.py && cd ../.. && pnpm types:generate
```

## Rules that bite

- The web app never computes odds math. It renders what the API returns. New math goes in
  `services/api/src/oddvex_api/quant` with tests.
- Regenerate `packages/types` whenever the API schema changes. CI fails if it is out of date.
- `apps/web/AGENTS.md` matters: Next.js 16 differs from older versions. Read the bundled docs in
  `apps/web/node_modules/next/dist/docs/` before using an API you have not used in this repo.
- UI copy follows `docs/marketing/BRAND_VOICE.md`. Sentence case, plain verbs, no hype.
- Never use color alone to carry meaning. Best price, over/under, win/loss all have a text or shape cue.
- Do not add a dependency for something a few lines of code can do.
