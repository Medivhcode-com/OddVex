# Synthetic fixtures

Everything in this directory is **synthetic**. The teams, players, sportsbooks,
scores, prices and statistics are invented and do not describe any real
organisation, person, game or market.

These files are sample payloads in a made-up "vendor wire format" (camelCase
keys, string prices, vendor enumerations). They are consumed by the contract
tests in `services/api/tests/test_provider_contract.py`, which pin how
`services/api/src/oddvex_api/providers/normalize.py` translates raw provider
payloads into OddVex's canonical models.

| File | Contents |
| --- | --- |
| `events.sample.json` | Three events: scheduled, in progress, final (3-way soccer) |
| `odds_snapshots.sample.json` | Moneyline / spread / total quotes incl. suspended and off-the-board books |
| `player_game_log.sample.json` | One fictional player's recent stat lines |
| `invalid_payloads.sample.json` | Payloads the adapter must reject |

Do not put real provider responses, credentials or personal data here.
