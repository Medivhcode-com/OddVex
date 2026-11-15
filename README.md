# OddVex

Sports betting intelligence: compare odds across sportsbooks, research player props, measure expected value and track
every bet. **OddVex is research and analytics only. It never takes a wager.**

> **Status: preview, synthetic data.** Everything runs on generated data with fictional teams, players and
> sportsbooks. No licensed data provider, payment system or production infrastructure is connected. See
> `docs/product/ROADMAP.md` for what is built and what is not.

## What's here

- **Web** (`apps/web`): marketing site plus the app. Games and live scores, odds comparison with line history, player
  prop analyzer, calculators, parlay research, bet tracker, OddVex AI, account settings.
- **API** (`services/api`): FastAPI modular monolith. Quant engine, synthetic data provider behind a provider
  contract, auth, bet tracking, mock sportsbook sync, rule-based assistant, admin overview.
- **Mobile** (`apps/mobile`): Expo app, first slice.
- **Docs** (`docs/`): product requirements, research, design system, compliance drafts, marketing drafts.

## Run it locally

Requirements: Node 22+, pnpm 10, Python 3.13.

```bash
# 1. API on http://localhost:8000
cd services/api
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/python scripts/seed_demo.py        # optional demo account
.venv/bin/uvicorn oddvex_api.main:app --port 8000
```

```bash
# 2. Web on http://localhost:3000
pnpm install
pnpm dev:web
```

Or with Docker: `docker compose up --build`.

## Test

```bash
cd services/api && .venv/bin/pytest
pnpm --filter @oddvex/web test
pnpm --filter @oddvex/web test:e2e
```

## Working here

Read `PROJECT_CONSTITUTION.md` and `AGENTS.md`. Work on a branch named for the Linear issue and open a pull request.
Spending money, deploying to production, store submissions and external publishing all need Founder approval first.
