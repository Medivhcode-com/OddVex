# @oddvex/types

Types generated from `services/api/openapi.json`.

```bash
cd services/api && .venv/bin/python scripts/export_openapi.py
pnpm types:generate
```

`src/api.d.ts` is generated. `src/index.ts` exports friendly aliases. CI fails if the generated file is stale.
