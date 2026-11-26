# ADR-0002: Provider contract, synthetic data and freshness

Status: accepted (M1)

- All sports data reaches the app through the `SportsDataProvider` protocol. M1 ships one implementation,
  `SyntheticProvider`: deterministic, seeded, relative to the current time, with fictional names throughout.
- Every record carries provenance (`provider`, `provider_id`, `fetched_at`). API responses expose `data_mode` so the
  UI can label synthetic data on every screen.
- Every price has `last_updated`. The API, not the client, decides `is_stale`, with one rule (`Board.is_stale` in
  `services/api/src/oddvex_api/board.py`) for event markets, prop offers, the best moneyline in event lists and the
  best price used by alerts and community picks. A quote is stale when any of these holds:
  1. it has no timestamp;
  2. its timestamp is more than 60 s in the future (`MAX_CLOCK_SKEW_SECONDS` in `providers/base.py`);
  3. it is older than the threshold for the event's status (`ODDVEX_STALE_LIVE_SECONDS`, default 120 s, for a live
     game; `ODDVEX_STALE_PREGAME_SECONDS`, default 900 s, otherwise);
  4. the game is live and the quote was made before the latest score change. A price from before a score change is
     a price for another game state.

  Stale, suspended and unavailable prices are still listed, with `is_stale` set, but are excluded from best-price
  marks and consensus.
- Rule 4 needs the provider to report when the score last changed: the field `Event.score_updated_at`
  (`providers/base.py`; `scoreUpdatedAt` in a vendor payload, read by `providers/normalize.py`). The synthetic
  provider sets it. Where it is missing, only rules 1 to 3 apply, and a live price made before a score change keeps
  counting for up to the live threshold. So a live vendor feed must supply `score_updated_at`, or the live threshold
  must be lowered for that feed, before its live prices are compared or used in a consensus.
- In M1 canonical sports entities are served from the provider and not persisted. User data (accounts, bets, sync
  connections, audit log) is persisted in PostgreSQL (SQLite in tests and local development).
- Connecting a real provider is a new adapter plus a persistence/ingestion job. It needs a signed data licence and
  Founder approval. See `docs/research/DATA_PROVIDER_EVALUATION.md`.
- PostgreSQL is the only datastore. Redis and ClickHouse are deferred until measured load requires them. Caching
  sits behind a small protocol with an in-memory implementation.

## Amendment, 2026-11-26: the snapshot archive (P0.1, MED-72)

Market data is now persisted, behind the `snapshot_archive` flag (off by default). `scripts/capture_snapshots.py`
copies what the provider reports into five append-only tables (`snapshot_runs`, `event_snapshots`,
`odds_snapshots`, `prop_snapshots`, `status_snapshots`, migration 0008), keyed on
`(provider, event_id | player_id, market, sportsbook_id, captured_at)` with the provider's own provenance columns.
`captured_at` is the provider clock. The live board still reads the provider directly; the archive is read only
when a time T is asked for, through `ArchiveView`, a read-only `SportsDataProvider` that answers from rows captured
at or before T. Staleness as of T is judged by the same `Board.is_stale` rule, with the thresholds stored on the
capture run, so a later change of `ODDVEX_STALE_*_SECONDS` does not rewrite history. Rows are never updated; the only
deletion is the retention prune (7 days at full resolution, 400 days for closing and bet-anchor rows). Details,
storage bounds and limits: `docs/features/p0-1.md`.
