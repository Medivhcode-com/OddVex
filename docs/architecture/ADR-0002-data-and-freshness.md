# ADR-0002: Provider contract, synthetic data and freshness

Status: accepted (M1)

- All sports data reaches the app through the `SportsDataProvider` protocol. M1 ships one implementation,
  `SyntheticProvider`: deterministic, seeded, relative to the current time, with fictional names throughout.
- Every record carries provenance (`provider`, `provider_id`, `fetched_at`). API responses expose `data_mode` so the
  UI can label synthetic data on every screen.
- Every price has `last_updated`. The API, not the client, decides `is_stale` (default: 120 s live, 15 min pre-game).
  Stale, suspended and unavailable prices are excluded from best-price marks and consensus.
- In M1 canonical sports entities are served from the provider and not persisted. User data (accounts, bets, sync
  connections, audit log) is persisted in PostgreSQL (SQLite in tests and local development).
- Connecting a real provider is a new adapter plus a persistence/ingestion job. It needs a signed data licence and
  Founder approval. See `docs/research/DATA_PROVIDER_EVALUATION.md`.
- PostgreSQL is the only datastore. Redis and ClickHouse are deferred until measured load requires them. Caching
  sits behind a small protocol with an in-memory implementation.
