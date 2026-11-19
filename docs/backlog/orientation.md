# Orientation: where the already-built features live

Step 1 of the Founder's build prompt (`BUILD_PROMPT.md`). One section per already-built feature, plus three shared
foundations the backlog leans on. Each section was produced by reading the code on 2026-11-19 and every path was
checked to exist at that time. When code moves, correct the section rather than trusting it.

## Summary table

| # | Already-built feature | Main code | Entry points | Tests | Backlog items that touch it |
|---|---|---|---|---|---|
| 1 | [Odds comparison with best price per outcome and stale-price flags](#1-odds-comparison-with-best-price-per-outcome-and-stale-price-flags) | `services/api/src/oddvex_api/board.py`<br>`services/api/src/oddvex_api/api/data.py`<br>and 19 more<br>`apps/web/src/app/app/odds/page.tsx`<br>and 15 more<br>`apps/mobile/src/screens/games.tsx`<br>and 15 more | GET /v1/events<br>GET /v1/events/{event_id}<br>GET /v1/events/{event_id}/odds?market=moneyline\|spread\|total<br>and 11 more | `services/api/tests/test_board.py`<br>`services/api/tests/test_api_data.py`<br>and 17 more | P0.1, P0.2, P0.3, P0.4, P0.5, F01, F06, F07, F08, F09, F11, F13, F16, F17, F20, F22, F25, F26, F27, F28, F30, F32, F34, F42, F44 |
| 2 | [Line movement history](#2-line-movement-history) | `services/api/src/oddvex_api/api/data.py`<br>`services/api/src/oddvex_api/board.py`<br>and 20 more<br>`apps/web/src/app/app/games/[id]/page.tsx`<br>and 8 more<br>`apps/mobile/src/screens/game-detail.tsx`<br>and 9 more | GET /v1/events/{event_id}/line-history?market=moneyline\|spread\|total<br>GET /v1/alerts, POST /v1/alerts (kind line_move), POST /v1/alerts/evaluate, PATCH /v1/alerts/{alert_id}, DELETE /v1/alerts/{alert_id}<br>PUT /v1/me/notification-preferences<br>and 7 more | `services/api/tests/test_api_data.py`<br>`services/api/tests/test_provider_synthetic.py`<br>and 12 more | P0.1, P0.3, P0.4, P0.6, F08, F11, F17, F34, F43 |
| 3 | [Player prop research: lines, best prices, hit rates with confidence intervals, game logs, splits](#3-player-prop-research-lines-best-prices-hit-rates-with-confidence-intervals-game-logs-splits) | `services/api/src/oddvex_api/board.py`<br>`services/api/src/oddvex_api/api/data.py`<br>and 16 more<br>`apps/web/src/app/app/props/page.tsx`<br>and 13 more<br>`apps/mobile/src/screens/props.tsx`<br>and 13 more | GET /v1/players?league=&q=<br>GET /v1/players/{player_id}<br>GET /v1/players/{player_id}/props?market=&window=5\|10\|20\|season&split=all\|home\|away\|vs_opponent<br>and 9 more | `services/api/tests/quant/test_hitrate.py`<br>`services/api/tests/quant/test_properties.py`<br>and 13 more | P0.1, P0.2, P0.6, F01, F06, F07, F08, F10, F11, F13, F16, F22, F27, F31, F32, F33 |
| 4 | [A value screen comparing each book with the no-vig consensus of the others](#4-a-value-screen-comparing-each-book-with-the-no-vig-consensus-of-the-others) | `services/api/src/oddvex_api/quant/value.py`<br>`services/api/src/oddvex_api/board.py`<br>and 13 more<br>`apps/web/src/app/app/value/page.tsx`<br>and 11 more<br>`apps/mobile/src/screens/value.tsx`<br>and 9 more | GET /v1/value?league=&market=&min_edge=&limit=<br>GET /v1/flags<br>Web: /app/value?league=&market=&min_edge=<br>and 4 more | `services/api/tests/quant/test_value.py`<br>`services/api/tests/test_api_value.py`<br>and 14 more | P0.1, P0.2, P0.3, P0.4, P0.6, F01, F06, F07, F08, F09, F11, F16, F20, F22, F25, F26, F34, F42 |
| 5 | [Calculators: expected value, no-vig, parlay, closing line value (CLV)](#5-calculators-expected-value-no-vig-parlay-closing-line-value-clv) | `services/api/src/oddvex_api/api/quant_routes.py`<br>`services/api/src/oddvex_api/quant/__init__.py`<br>and 16 more<br>`apps/web/src/app/app/tools/page.tsx`<br>and 12 more<br>`apps/mobile/src/screens/tools.tsx`<br>and 12 more | POST /v1/quant/convert<br>POST /v1/quant/no-vig<br>POST /v1/quant/ev<br>and 10 more | `services/api/tests/test_api_quant.py`<br>`services/api/tests/quant/test_novig_ev_clv.py`<br>and 13 more | P0.2, P0.3, P0.4, P0.6, F01, F03, F06, F07, F08, F09, F19, F20, F26, F28, F29, F32, F40, F41 |
| 6 | [Bet tracker with auto-settlement, ROI analytics and sportsbook sync](#6-bet-tracker-with-auto-settlement-roi-analytics-and-sportsbook-sync) | `services/api/src/oddvex_api/bets/router.py`<br>`services/api/src/oddvex_api/bets/service.py`<br>and 25 more<br>`apps/web/src/app/app/tracker/page.tsx`<br>and 14 more<br>`apps/mobile/src/screens/tracker.tsx`<br>and 17 more | GET /v1/bets<br>POST /v1/bets<br>GET /v1/bets/summary<br>and 23 more | `services/api/tests/test_api_bets.py`<br>`services/api/tests/test_api_auto_settle.py`<br>and 24 more | P0.1, P0.2, P0.3, P0.4, P0.6, F01, F02, F03, F04, F05, F06, F07, F11, F14, F15, F18, F19, F20, F21, F23, F24, F26, F30, F35, F36, F38, F39, F41 |
| 7 | [Watchlist, price and line-move alerts, in-app notifications](#7-watchlist-price-and-line-move-alerts-in-app-notifications) | `services/api/src/oddvex_api/alerts/evaluator.py`<br>`services/api/src/oddvex_api/alerts/service.py`<br>and 27 more<br>`apps/web/src/app/app/alerts/page.tsx`<br>and 14 more<br>`apps/mobile/src/screens/notifications.tsx`<br>and 19 more | GET /v1/watchlist (optional ?kind=)<br>POST /v1/watchlist<br>GET /v1/watchlist/events<br>and 22 more | `services/api/tests/test_alert_evaluator.py`<br>`services/api/tests/test_api_alerts.py`<br>and 23 more | P0.1, P0.2, P0.3, P0.4, P0.6, F04, F06, F07, F08, F11, F14, F16, F17, F23 |
| 8 | [A rule-based assistant that answers from the app's own data and math](#8-a-rule-based-assistant-that-answers-from-the-app-s-own-data-and-math) | `services/api/src/oddvex_api/assistant/engine.py`<br>`services/api/src/oddvex_api/assistant/explainer.py`<br>and 12 more<br>`apps/web/src/app/app/assistant/page.tsx`<br>and 9 more<br>`apps/mobile/src/screens/assistant.tsx`<br>and 8 more | POST /v1/assistant/query<br>Web: /app/assistant (page), calls go through the /api/ov/v1/assistant/query proxy route<br>Web marketing: /ai links to /app/assistant<br>and 2 more | `services/api/tests/test_api_assistant.py`<br>`services/api/tests/test_platform.py`<br>and 8 more | P0.2, P0.3, P0.4, P0.6, F01, F07, F11, F13, F16 |
| 9 | [Community features (built, switched off)](#9-community-features-built-switched-off) | `services/api/src/oddvex_api/community/service.py`<br>`services/api/src/oddvex_api/community/router.py`<br>and 20 more<br>`apps/web/src/app/app/community/page.tsx`<br>and 27 more<br>`apps/mobile/src/screens/community-feed.tsx`<br>and 31 more | GET /v1/community/guidelines<br>PUT /v1/community/profile<br>GET /v1/community/profile<br>and 41 more | `services/api/tests/test_api_community.py`<br>`services/api/tests/test_api_community_moderation.py`<br>and 24 more | P0.2, P0.3, P0.6, F07, F11, F19, F38 |
| 10 | [Admin tools, feature flags, staking-limit reminders](#10-admin-tools-feature-flags-staking-limit-reminders) | `services/api/src/oddvex_api/api/admin.py`<br>`services/api/src/oddvex_api/flags/catalog.py`<br>and 23 more<br>`apps/web/src/lib/admin.ts`<br>and 20 more<br>`apps/mobile/src/providers/flags.tsx`<br>and 13 more | GET /v1/admin/overview<br>GET /v1/admin/users<br>POST /v1/admin/users/{user_id}/suspend<br>and 19 more | `services/api/tests/test_api_admin.py`<br>`services/api/tests/test_api_admin_manage.py`<br>and 19 more | P0.3, P0.4, P0.6, F05, F11, F20, F23, F24, F26, F30, F39, F40, F42, F44 |
| 11 | [Shared foundation: accounts, sessions and per-user settings](#11-shared-foundation-accounts-sessions-and-per-user-settings) | `services/api/src/oddvex_api/auth/router.py`<br>`services/api/src/oddvex_api/deps.py`<br>and 25 more<br>`apps/web/src/lib/session.ts`<br>and 25 more<br>`apps/mobile/src/session/store.ts`<br>and 19 more | POST /v1/auth/register<br>POST /v1/auth/login<br>POST /v1/auth/logout<br>and 22 more | `services/api/tests/test_api_auth.py`<br>`services/api/tests/test_api_account.py`<br>and 19 more | P0.3, P0.4, P0.6, F05, F06, F08, F11, F14, F16, F23, F24, F25, F31, F39, F41, F42 |
| 12 | [Shared foundation: data providers, fixtures and the data model](#12-shared-foundation-data-providers-fixtures-and-the-data-model) | `services/api/src/oddvex_api/providers/base.py`<br>`services/api/src/oddvex_api/providers/synthetic.py`<br>and 37 more<br>`apps/web/src/app/app/layout.tsx`<br>and 10 more<br>`apps/mobile/src/providers/meta.tsx`<br>and 8 more | GET /health<br>GET /v1/meta<br>GET /v1/leagues<br>and 19 more | `services/api/tests/test_provider_contract.py`<br>`services/api/tests/test_provider_synthetic.py`<br>and 12 more | P0.1, P0.2, P0.4, P0.5, F01, F03, F09, F10, F12, F13, F16, F17, F18, F20, F22, F26, F27, F28, F29, F30, F32, F33, F34, F35, F37, F40, F43, F44 |
| 13 | [Shared foundation: CI, tests and quality gates](#13-shared-foundation-ci-tests-and-quality-gates) | `services/api/tests/conftest.py`<br>`services/api/tests/test_notification_copy.py`<br>and 27 more<br>`apps/web/package.json`<br>and 18 more<br>`apps/mobile/package.json`<br>and 14 more | CI: .github/workflows/ci.yml jobs api, api-postgres, web, mobile, e2e, docker, audit, secrets (on pull_request and push to main)<br>Script: services/api/scripts/export_openapi.py [--check]<br>Script: pnpm types:generate (packages/types: openapi-typescript ../../services/api/openapi.json -o src/api.d.ts)<br>and 11 more | `services/api/tests/test_notification_copy.py`<br>`services/api/tests/test_api_flags_entitlements.py`<br>and 14 more | P0.1, P0.3, P0.4, P0.5, P0.6, F07, F08, F11, F12, F23, F41, F42 |

## 1. Odds comparison with best price per outcome and stale-price flags

Odds comparison is a read model computed per request in services/api/src/oddvex_api/board.py: Board pulls each book's current OddsSnapshot from the configured SportsDataProvider (synthetic or replay), marks a quote stale when its age against provider.now() exceeds ODDVEX_STALE_PREGAME_SECONDS (900) or ODDVEX_STALE_LIVE_SECONDS (120), and picks the highest decimal price per outcome among open, non-stale, fully priced books (for spread/total only books on the consensus line), plus mean no-vig consensus and per-book hold. It is served unauthenticated by GET /v1/events, /v1/events/{id}, /v1/events/{id}/odds and /v1/events/{id}/line-history; web renders it at /app/odds, /app/games and /app/games/[id], mobile on the Games tab and the event/[id] screen. Both clients only display what the API returns (is_best, is_stale, best[], consensus, holds); nothing is persisted.

**API (`services/api`)**

- `services/api/src/oddvex_api/board.py`: Board: _quote_rows, _usable, _best_prices, best_price, event_odds, _best_moneyline, is_stale, consensus_line
- `services/api/src/oddvex_api/api/data.py`: /v1 events, odds, line-history routes; _event_or_404, _check_market
- `services/api/src/oddvex_api/api/schemas.py`: EventOddsOut, BookOddsOut, OddsOutcomeOut, BestOutcomeOut, ConsensusOut, BookHoldOut, BestMoneylineOut, EventSummaryOut
- `services/api/src/oddvex_api/schemas.py`: PriceOut, price_out, BestPriceOut, SportsbookRef
- `services/api/src/oddvex_api/providers/base.py`: SportsDataProvider protocol, OddsSnapshot, OddsOutcome, LineSeries
- `services/api/src/oddvex_api/providers/synthetic.py`: get_odds, _last_updated, fictional books incl. always-stale 'oldmill'
- `services/api/src/oddvex_api/providers/replay.py`: replay get_odds; per-book prices simulated around a real closing line
- `services/api/src/oddvex_api/providers/normalize.py`: vendor payload to OddsSnapshot adapter seam (used by contract tests only)
- `services/api/src/oddvex_api/providers/__init__.py`: provider exports
- `services/api/src/oddvex_api/quant/novig.py`: no_vig: fair probabilities and hold
- `services/api/src/oddvex_api/quant/odds.py`: american_to_decimal, describe_price
- `services/api/src/oddvex_api/quant/value.py`: best_price_vs_consensus (value screen, same usable quotes)
- `services/api/src/oddvex_api/deps.py`: get_board / BoardDep, ProviderDep
- `services/api/src/oddvex_api/config.py`: stale_live_seconds, stale_pregame_seconds, data_provider
- `services/api/src/oddvex_api/main.py`: build_provider, router mounting under /v1
- `services/api/src/oddvex_api/cache.py`: TTL cache (value and props boards only, not event_odds)
- `services/api/src/oddvex_api/alerts/service.py`: consumer: Board.best_price, consensus_outcome_line
- `services/api/src/oddvex_api/community/service.py`: consumer: Board.best_price for pick price
- `services/api/src/oddvex_api/assistant/engine.py`: consumer: compare_odds tool calls Board.event_odds
- `services/api/src/oddvex_api/seed.py`: consumer: demo bets priced with Board.best_price
- `services/api/openapi.json`: generated contract feeding packages/types

**Web (`apps/web`)**

- `apps/web/src/app/app/odds/page.tsx`: odds board: best price per outcome for up to 12 games
- `apps/web/src/app/app/games/page.tsx`: games list with best moneyline cards
- `apps/web/src/app/app/games/[id]/page.tsx`: game page: OddsTable, line chart, quick bet, alert, share pick
- `apps/web/src/components/app/odds-table.tsx`: books x outcomes table, Best mark, stale/suspended text, hold, consensus footer
- `apps/web/src/components/app/freshness.tsx`: 'Updated/Stale, Ns ago' ticking label
- `apps/web/src/components/app/event-bits.tsx`: EventCard, StatusBadge, best moneyline per side
- `apps/web/src/components/app/odds-format.tsx`: Price, OddsFormatProvider (ov_odds cookie), toggle
- `apps/web/src/components/app/auto-refresh.tsx`: router.refresh() interval toggle
- `apps/web/src/components/ui/charts.tsx`: LineHistoryChart
- `apps/web/src/lib/format.ts`: formatPrice, formatLine, formatPercent, formatAge
- `apps/web/src/lib/types.ts`: OddsComparison, Outcome, EventSummary aliases of generated schemas
- `apps/web/src/lib/api.ts`: server fetch helper api/apiOrNull/withQuery
- `apps/web/src/lib/leagues.ts`: getLeagues, MARKETS, pick
- `apps/web/src/lib/session.ts`: reads ov_odds cookie for initial format
- `apps/web/src/app/(marketing)/odds-comparison/page.tsx`: marketing copy for the feature
- `apps/web/src/app/(marketing)/methodology/page.tsx`: explains best price, stale, consensus

**Mobile (`apps/mobile`)**

- `apps/mobile/src/screens/games.tsx`: Games tab: sectioned GameCards, watchlist, league filter
- `apps/mobile/src/screens/game-detail.tsx`: event screen: OddsBoard, market switch, quick bet, alert, share pick
- `apps/mobile/src/components/odds-row.tsx`: OddsRow, PriceCell, ConsensusRow, lineText
- `apps/mobile/src/components/game-card.tsx`: GameCard, EventStatus, best moneyline per side
- `apps/mobile/src/components/freshness.tsx`: 'Stale, 9 min ago' label
- `apps/mobile/src/components/price.tsx`: Price in chosen format
- `apps/mobile/src/components/quick-bet.tsx`: quickBetOptions built from odds.best
- `apps/mobile/src/providers/odds-format.tsx`: format in AsyncStorage (oddvex.odds-format)
- `apps/mobile/src/api/client.ts`: getEvents, getEvent, getEventOdds
- `apps/mobile/src/api/types.ts`: OddsComparison, BookRow, Outcome, BestSide aliases
- `apps/mobile/src/hooks/use-resource.ts`: fetch/reload hook (pull to refresh, no polling)
- `apps/mobile/src/hooks/use-now.ts`: 10s clock for age labels
- `apps/mobile/src/utils/format.ts`: formatPrice, formatLine, formatPercent, formatAge
- `apps/mobile/src/utils/routes.ts`: maps /app/games/{id} and /app/odds to event screen
- `apps/mobile/src/app/(tabs)/(games)/index.tsx`: Games tab route
- `apps/mobile/src/app/(tabs)/(games)/event/[id].tsx`: game detail route

**Entry points**

- GET /v1/events - list with best_moneyline per side (query: league, status, date)
- GET /v1/events/{event_id} - event detail with available_markets
- GET /v1/events/{event_id}/odds?market=moneyline|spread|total - odds comparison
- GET /v1/events/{event_id}/line-history?market= - about 48h of per-book history
- GET /v1/sportsbooks - books in the comparison
- GET /v1/leagues - leagues and their markets
- Web /app/odds?league=&market= - odds board
- Web /app/games?league=&status= - games list
- Web /app/games/[id]?market= - game odds comparison
- Web /odds-comparison and /methodology - marketing/explanation
- Mobile route / (Games tab) - GamesScreen
- Mobile route /event/[id]?market= - GameDetailScreen
- Script services/api/scripts/export_openapi.py - regenerates openapi.json for packages/types
- Script services/api/scripts/build_replay_data.py - builds the replay provider dataset

**Tests**

- `services/api/tests/test_board.py`: best price, stale/suspended/unavailable exclusion, live vs pregame thresholds, consensus line, ties, Board.best_price parity
- `services/api/tests/test_api_data.py`: /v1/events, best_moneyline, /odds per market, three-way, live stale threshold, final events, line history
- `services/api/tests/fakes.py`: ScriptedProvider used by board tests
- `services/api/tests/test_provider_synthetic.py`: synthetic feed has suspended, unavailable and one stale book
- `services/api/tests/test_provider_contract.py`: odds snapshot normalisation from data/fixtures
- `services/api/tests/test_provider_replay.py`: replay provider odds behaviour
- `services/api/tests/test_replay_build_and_api.py`: API over replay data
- `services/api/tests/quant/test_novig_ev_clv.py`: no-vig and hold math
- `services/api/tests/quant/test_odds.py`: odds conversions
- `services/api/tests/test_api_value.py`: value screen ignores stale/suspended books (same usable set)
- `services/api/tests/test_migrations_seed_openapi.py`: openapi.json in sync
- `apps/web/e2e/app.spec.ts`: games to odds table, 'best price is never on a stale or closed book', odds format toggle
- `apps/web/src/lib/format.test.ts`: formatPrice, formatLine, formatAge
- `apps/mobile/src/components/odds-row.test.tsx`: Best label, stale, suspended, not offered, lines, consensus row
- `apps/mobile/src/components/game-card.test.tsx`: best moneyline, no price, draw, final
- `apps/mobile/src/screens/game-detail.test.tsx`: market from link, quick bet, alert, watchlist section
- `apps/mobile/src/providers/odds-format.test.tsx`: format default and persistence
- `apps/mobile/src/utils/format.test.ts`: price, line, age formatting
- `apps/mobile/src/utils/routes.test.ts`: /app/games and /app/odds link mapping

**Data model**

none: computed on request. No table or migration holds odds, quotes, best prices, consensus or line history; services/api/src/oddvex_api/db/models.py has only users, bets, bet_legs, sync_*, watchlist_items, alert_rules, notifications, notification_preferences, stake_reminders, feature_flags, email_tokens, email_outbox, audit_log and community_* tables. Odds come from the in-memory provider (synthetic generator or replay dataset file at ODDVEX_REPLAY_DATA_PATH); line history is generated by the provider on each call. Other features copy a best price into their own rows (bets, alert_rules, community_picks) at the time of use.

**Flags and plan checks today**

None gate it. The events, odds and line-history routes are public (no auth, no require_flag, no plan check). The only flag touching the surface is value_screen, which hides the link from /app/odds to /app/value (web) and the ValueEntry card on the mobile Games tab; the community flag gates the share-pick panel on the game page. entitlements/catalog.py defines odds_history_hours (48 for free and premium) but nothing enforces it: require_entitlement in entitlements/service.py is not used by any route, and premium_gating is off by default. Tuning is by env only: ODDVEX_STALE_LIVE_SECONDS, ODDVEX_STALE_PREGAME_SECONDS, ODDVEX_DATA_PROVIDER.

**Backlog items that will touch it**

- **P0.1**: The archive must capture exactly what Board._quote_rows reads from provider.get_odds (per-book OddsSnapshot with status and last_updated) and let Board be built as of a time T instead of provider.now().
- **P0.2**: Board.event_odds outputs (best, consensus no-vig probability, hold) need method id/version, inputs and as_of attached, which means extending EventOddsOut and the code in board.py that builds it.
- **P0.3**: The events/odds routes in api/data.py have no auth or plan dependency today, and the unused odds_history_hours entitlement would first be enforced on /v1/events/{id}/line-history.
- **P0.4**: Replaces the web ov_odds cookie and the mobile AsyncStorage odds-format providers with a synced profile setting, adds an implied-probability format to Price/formatPrice, and supplies books-held for filtering the odds table.
- **P0.5**: New provider interfaces sit beside SportsDataProvider in providers/base.py and follow the synthetic.py fixture pattern the odds feed already uses.
- **F01**: Reuses Board.best_price and the no-vig consensus from event_odds for each matched leg, needing a books-held filter added to _usable/_best_prices.
- **F06**: Adds a dollars-per-$100 rendering to the web Price/OddsTable and mobile Price/PriceCell, using the consensus fair probability already in EventOddsOut.
- **F07**: Every price cell, Best mark, hold and consensus figure in odds-table.tsx and odds-row.tsx becomes tappable and needs the inputs and source books from event_odds.
- **F08**: OddsTable, Freshness, AutoRefresh and the mobile OddsRow/GameCard need high-contrast variants and throttled polite announcements of refreshed prices.
- **F09**: Extends the consensus computed in Board.event_odds with per-book contribution, quote age and leave-one-out values, shown beside the consensus row on web and mobile.
- **F11**: The odds board, games list and game detail screens are current-market screens that must be hidden while a break is active.
- **F13**: Search results route to /app/games/[id]?market= and the mobile /event/[id] screen, and matching reuses the event and market lists from the provider.
- **F16**: Board._usable and the odds table must filter books by the user's state and books held, and explain each hidden or missing price where the UI now says only 'Not offered'.
- **F17**: Adds lineup status and timestamped markers to the game page and to LineHistoryOut / LineHistoryChart; mobile has no line chart yet.
- **F20**: Fair value of an open bet comes from the current no-vig consensus and best prices that Board.event_odds and best_price already produce.
- **F22**: A receipt snapshots the EventOddsOut the user saw on the game page and diffs it against a fresh Board.event_odds call.
- **F25**: Adds a per-book stake-limit filter to the book rows of the odds table and to best-price selection.
- **F26**: Stage 1 takes each leg's no-vig fair probability and hold from the same per-book quotes and consensus logic in Board.
- **F27**: Grading-rule differences are displayed beside each book's price in odds-table.tsx and odds-row.tsx.
- **F28**: Converts the three-way moneyline consensus from event_odds (has_draw leagues) into derived markets shown on the game page.
- **F30**: Replays best-price selection (_usable/_best_prices) over archived snapshots at each bet's placement time, including books the user does not hold.
- **F32**: Fits to the no-vig spread/total consensus and line that Board.event_odds and consensus_line produce.
- **F34**: Reopens the games list and odds comparison for a past time, which needs Board and its staleness check driven by an as-of clock instead of provider.now().
- **F42**: The bot returns fair price and best book through F01, which is built on Board.best_price and event_odds.
- **F44**: Feed gaps, update delays and stale rates are measured on the same OddsSnapshot.last_updated and status fields the stale flag uses.

**What a builder would get wrong by assuming**

1. Nothing is stored: there is no odds, snapshot or line-history table. OddsSnapshot is a provider record of the current quote only, and "line history" is regenerated by the provider on each call, so anything needing a past price (P0.1, F30, F34) starts from zero.
2. All prices are synthetic. The replay provider uses real schedules and one real closing line per game, but every per-book price, the books themselves and prop lines are simulated; there is no real vendor adapter (providers/normalize.py is only exercised by contract tests).
3. Staleness is judged against provider.now(), computed once per Board (one per request), while both clients show age against the device clock. event_odds is not cached (only value and props boards are, 10s).
4. best[].sportsbook_key and holds[].sportsbook_key carry the provider sportsbook id, not SportsbookRef.key. Web and mobile join them to books[].sportsbook.key; that works only because the synthetic provider sets id == key.
5. For spread and total, best price only compares books on the consensus (most common) line. A book off that line is never is_best in event_odds, whereas Board.best_price(line=...) compares books quoting the requested line, so the two can name different books.
6. Ties: is_best is true for every tied book, but best[] lists only the first book in provider order.
7. holds are returned for stale and suspended books too (any book with two or more prices), although those books are excluded from best and consensus.
8. Board._best_moneyline (used for event summaries and game cards) is a separate loop from _best_prices/_usable; it has the same open and non-stale rule but not the 'fully priced' check, so a rule change must be made in both.
9. The API returns american, decimal, fractional and implied_probability for every price, but both clients offer only American and decimal, and the preference is stored separately (web cookie ov_odds, mobile AsyncStorage) and not synced.
10. Mobile has no odds board and no line-history chart: /app/odds links map to the Games tab or the event screen, and getEventOdds is the only odds call. Mobile refreshes on pull only; web polls with router.refresh().
11. Web /app/odds makes one /odds request per game (up to 12) and swallows failures into 'No book has this market open right now'.
12. Display helpers are duplicated between web and mobile (format.ts, lineText, oddsColumns logic, quick-bet option building, Freshness); a change to one does not reach the other.
13. Provider status 'closed' is reported to clients as 'unavailable', and final events return no best prices at all.
14. premium_gating and the entitlement catalog exist but no route in this part calls require_entitlement, so turning the flag on changes nothing here.

## 2. Line movement history

Line history is a public, unauthenticated read: GET /v1/events/{event_id}/line-history calls Board.line_history, which reshapes provider.get_line_history (hourly per-book, per-outcome points over about 48 hours) into LineHistoryOut; nothing is stored, the synthetic and replay providers regenerate the series deterministically on every request. The web game page fetches it server-side and draws one outcome as an SVG step chart (LineHistoryChart); the mobile app has no line-history chart or client call at all. Line-move alerts are a separate mechanism: they compare the current consensus line (Board.consensus_outcome_line, from live odds) with a baseline_line stored on alert_rules, and never read line history.

**API (`services/api`)**

- `services/api/src/oddvex_api/api/data.py`: route get_event_line_history (line 186), _event_or_404, _check_market
- `services/api/src/oddvex_api/board.py`: Board.line_history (454) read model; consensus_outcome_line (290) used by line-move alerts
- `services/api/src/oddvex_api/api/schemas.py`: LinePointOut, LineSeriesOut, LineHistoryOut (178-196)
- `services/api/src/oddvex_api/providers/base.py`: LinePoint, LineSeries, protocol get_line_history (185)
- `services/api/src/oddvex_api/providers/synthetic.py`: get_line_history (878), HISTORY_HOURS=48, hourly _quote per book
- `services/api/src/oddvex_api/providers/replay.py`: get_line_history (527), own HISTORY_HOURS=48, near-copy of synthetic
- `services/api/src/oddvex_api/providers/__init__.py`: re-exports LinePoint, LineSeries
- `services/api/src/oddvex_api/alerts/evaluator.py`: line_moved, _line_move: pure rule evaluation
- `services/api/src/oddvex_api/alerts/service.py`: arms baseline_line, builds consensus_line input, evaluate_user_alerts
- `services/api/src/oddvex_api/alerts/schemas.py`: LineMoveAlertCreate, AlertKind, min_move/baseline_line fields
- `services/api/src/oddvex_api/alerts/router.py`: /v1/alerts CRUD and /evaluate; re-arm resets baseline
- `services/api/src/oddvex_api/alerts/throttle.py`: alert throttling (same package)
- `services/api/src/oddvex_api/notifications/templates.py`: line_move() notification copy ('Line moved to {current}')
- `services/api/src/oddvex_api/notifications/schemas.py`: line_move kind and per-channel preference
- `services/api/src/oddvex_api/db/models.py`: AlertRule (min_move, baseline_line), Notification kind line_move
- `services/api/src/oddvex_api/assistant/engine.py`: line_movement tool: open vs current moneyline from Board.line_history
- `services/api/src/oddvex_api/assistant/explainer.py`: _line_movement wording
- `services/api/src/oddvex_api/community/seed.py`: _past_pick prices demo picks from provider.get_line_history
- `services/api/src/oddvex_api/seed.py`: seeds a 3-point total line_move alert
- `services/api/src/oddvex_api/entitlements/catalog.py`: odds_history_hours (48 for both plans), not enforced anywhere
- `services/api/scripts/evaluate_alerts.py`: batch alert evaluation script (stand-in for a worker)
- `services/api/openapi.json`: get_event_line_history and LineHistoryOut contract

**Web (`apps/web`)**

- `apps/web/src/app/app/games/[id]/page.tsx`: fetches line-history, historySeries() picks one outcome, renders 'Line movement' panel
- `apps/web/src/components/ui/charts.tsx`: LineHistoryChart: hand-rolled SVG step chart, Series type
- `apps/web/src/lib/types.ts`: LineHistory = Schemas['LineHistoryOut']
- `apps/web/src/app/design/page.tsx`: LineHistoryChart sample on the design page
- `apps/web/src/components/app/alert-form.tsx`: 'Line moves' alert kind (spread/total only)
- `apps/web/src/components/app/alerts-panels.tsx`: 'Line move' label in alert/notification lists
- `apps/web/src/components/app/notification-settings.tsx`: 'Line moves' preference toggle
- `apps/web/src/app/app/alerts/page.tsx`: alerts list page
- `packages/types/src/api.d.ts`: generated LineHistoryOut and route types (shared with mobile)

**Mobile (`apps/mobile`)**

- `apps/mobile/src/screens/game-detail.tsx`: game detail; no line-history chart or fetch
- `apps/mobile/src/app/(tabs)/(games)/event/[id].tsx`: route for game detail
- `apps/mobile/src/api/client.ts`: alerts calls (getAlerts, createAlert, updateAlert); no line-history method
- `apps/mobile/src/api/types.ts`: LineMoveAlertCreate in AlertCreate union
- `apps/mobile/src/components/alert-form.tsx`: 'Line moves' alert (points, default 1)
- `apps/mobile/src/components/alert-list.tsx`: alert rules list
- `apps/mobile/src/components/notification-list.tsx`: 'Line move' label
- `apps/mobile/src/components/notification-settings.tsx`: 'Line moves' toggle
- `apps/mobile/src/components/game-log-chart.tsx`: only existing mobile chart (player game log), possible pattern to follow
- `apps/mobile/README.md`: line 170 lists line movement charts as not built on mobile

**Entry points**

- GET /v1/events/{event_id}/line-history?market=moneyline|spread|total - public, operation get_event_line_history
- GET /v1/alerts, POST /v1/alerts (kind line_move), POST /v1/alerts/evaluate, PATCH /v1/alerts/{alert_id}, DELETE /v1/alerts/{alert_id} - authenticated
- PUT /v1/me/notification-preferences - line_move toggle per channel
- Assistant route (assistant/router.py) - intent line_movement
- Web /app/games/[id]?market= - 'Line movement' panel
- Web /app/alerts - alert rules and notifications
- Web /design - chart sample
- Mobile /event/{id}?market= (game-detail screen) - line-move alert form only, no chart
- Script services/api/scripts/evaluate_alerts.py [--dry-run]
- Script services/api/scripts/seed_demo.py - seeds the line_move rule via seed.py

**Tests**

- `services/api/tests/test_api_data.py`: test_line_history (total market) and 404 for unknown event
- `services/api/tests/test_provider_synthetic.py`: determinism, test_line_history_covers_about_48_hours
- `services/api/tests/test_provider_replay.py`: history ends at close, never after kickoff; empty for missing market
- `services/api/tests/test_replay_build_and_api.py`: line-history route under the replay provider
- `services/api/tests/test_api_assistant.py`: test_line_movement matches the route's data
- `services/api/tests/test_alert_evaluator.py`: line_move fires at min_move both directions, copy, no consensus line
- `services/api/tests/test_api_alerts.py`: baseline recorded, away side and totals, needs a current line, pause/resume/re-arm
- `services/api/tests/test_api_notifications.py`: evaluation and evaluate_alerts script run
- `services/api/tests/test_notification_copy.py`: line_move template copy
- `services/api/tests/test_migrations_seed_openapi.py`: operation id pinned, seeded line_move rule
- `apps/web/e2e/app.spec.ts`: 'line movement' img visible on game page; line-move alert creation; preference toggle
- `apps/mobile/src/components/alert-form.test.tsx`: line-move alert form
- `apps/mobile/src/components/notification-settings.test.tsx`: line_move toggle
- `No unit test exists for LineHistoryChart or historySeries (web)`: e2e only

**Data model**

Line history: none, computed on request by the provider (no table, no migration). Line-move alerts: alert_rules (kind, market, outcome_key, min_move, baseline_line, arm_count, state) and notifications (kind line_move, dedupe_key), created in services/api/alembic/versions/0003_alerts_notifications_stake_reminder.py; notification preferences hold the line_move toggle.

**Flags and plan checks today**

None gate it. The line-history route has no auth, no require_flag and no plan check. Entitlement key odds_history_hours exists in entitlements/catalog.py (48 for free and premium) but nothing reads it; the window is the HISTORY_HOURS=48 constant in each provider. premium_gating flag is off by default. Alerts need a signed-in user and are capped by alerts.max_active (MAX_ACTIVE_ALERTS, same for both plans).

**Backlog items that will touch it**

- **P0.1**: Board.line_history and both providers' get_line_history regenerate the series on request; the archive becomes the stored source they must read from (or be replaced by) and gives as-of-T queries.
- **P0.3**: The unused odds_history_hours entitlement must be wired into the line-history route in place of the hard-coded HISTORY_HOURS=48.
- **P0.4**: The web chart hard-codes formatAmerican for moneyline values and must take the profile odds format.
- **P0.6**: The line_move notification path (alerts/service.py evaluate_user_alerts, notifications/templates.py line_move) must call the suppression hook before sending.
- **F08**: LineHistoryChart exposes only an aria-label summary; Clear Mode needs a high-contrast variant and a readable data alternative for it.
- **F11**: Line-move alert firing in alerts/service.py must stop during a quiet period, and the game page's Line movement panel is a current-market surface to hide.
- **F17**: Adds timestamped injury, lineup, pitcher and weather markers to LineHistoryOut and LineHistoryChart, and builds the missing mobile chart to carry them.
- **F34**: Replay needs line history truncated at a chosen time T, so line_history/get_line_history gain an as-of parameter and the chart is reused.
- **F43**: The embeddable chart of a past market event reuses LineHistoryChart and the line-history read model with sources and timestamps.

**What a builder would get wrong by assuming**

1) Nothing is persisted: every line-history point is recomputed per request from a deterministic model (hourly stamps plus the book's last_updated); there is no snapshot table, so no true history exists yet. 2) The 'replay' provider's history is also modelled: only the closing line is real, the movement before it is generated. 3) get_line_history is duplicated almost line for line in providers/synthetic.py and providers/replay.py, each with its own HISTORY_HOURS; they differ for live games (synthetic runs to now, replay stops at the close). 4) Mobile has no line-history chart and no client method, despite the starting hint; game-detail.tsx only carries the line-move alert form. 5) Line-move alerts do not use line history: they compare the current consensus line with alert_rules.baseline_line captured when the rule was armed, work for spread and total only (moneyline has no line), and are evaluated only when a user reads notifications, calls POST /v1/alerts/evaluate, or the script runs (no worker). 6) The web chart draws only the first outcome the API lists (price for moneyline, line for spread/total, so price moves on spread/total are invisible), and the '48 hours' text is hard-coded in page.tsx. 7) The page swallows a failed line-history fetch (.catch(() => null)) and shows 'No line history'. 8) odds_history_hours looks like a working plan limit but is read nowhere. 9) LineSeries carries provider provenance fields that LineSeriesOut drops; the response has only one as_of for the whole payload. 10) Alert-form and label logic for line moves is implemented separately in web and mobile.

## 3. Player prop research: lines, best prices, hit rates with confidence intervals, game logs, splits

Prop research is a read-only, unauthenticated slice: two GET routes in services/api/src/oddvex_api/api/data.py call Board.props_board and Board.player_props (board.py), which pull players, per-book PropOffer rows and game logs from the active SportsDataProvider (synthetic or replay), pick a consensus line (most common line among open, non-stale books), mark the best over/under at that line, and grade the game log with quant.hit_rate (Wilson 95% interval). Web renders it as server components at /app/props and /app/props/[playerId]; mobile renders the same two payloads in screens/props.tsx and screens/prop-analyzer.tsx; the assistant's player_trend tool reuses Board.player_props. Nothing is stored: every number is computed per request (10 s board cache, 30 s game-log cache). I ran no tests (read-only brief).

**API (`services/api`)**

- `services/api/src/oddvex_api/board.py`: Board.player_props, props_board/_props_board, _prop_offers (best price), _game_log, consensus_line, HIT_RATE_CAVEAT, _WINDOW_SIZES, cache TTLs
- `services/api/src/oddvex_api/api/data.py`: routes list_players, get_player, get_player_props, list_props; market_not_available 422
- `services/api/src/oddvex_api/quant/hitrate.py`: hit_rate, wilson_interval, HitRate dataclass
- `services/api/src/oddvex_api/api/schemas.py`: PlayerOut, PlayerDetailOut, PropOfferOut, GameLogEntryOut, HitRateOut, AveragesOut, PlayerPropsOut, PropBoardRowOut, PropWindow, PropSplit
- `services/api/src/oddvex_api/providers/base.py`: Player, GameLogEntry, PropOffer records; list_players, get_player, get_player_game_log, get_prop_offers protocol
- `services/api/src/oddvex_api/providers/synthetic.py`: fictional players, game logs (40-game cap), prop offers
- `services/api/src/oddvex_api/providers/replay.py`: real game logs, simulated prop lines from trailing 6-game average
- `services/api/src/oddvex_api/providers/normalize.py`: normalize_game_log
- `services/api/src/oddvex_api/deps.py`: get_board / BoardDep, ProviderDep
- `services/api/src/oddvex_api/schemas.py`: PriceOut, BestPriceOut, SportsbookRef, price_out used in prop rows
- `services/api/src/oddvex_api/quant/__init__.py`: re-exports hit_rate, wilson_interval
- `services/api/src/oddvex_api/quant/record.py`: other caller of wilson_interval (tracker record)
- `services/api/src/oddvex_api/assistant/engine.py`: player_trend tool calls Board.player_props; _find_players, _MARKET_WORDS
- `services/api/src/oddvex_api/assistant/explainer.py`: _player_trend wording
- `services/api/src/oddvex_api/main.py`: mounts data.router under /v1
- `services/api/scripts/build_replay_data.py`: builds replay players and per-game stat lines
- `services/api/docs/QUANT_METHODOLOGY.md`: method notes
- `services/api/openapi.json and packages/types/src/api.d.ts`: generated contract both clients type against

**Web (`apps/web`)**

- `apps/web/src/app/app/props/page.tsx`: props board table; league and stat filters in URL query
- `apps/web/src/app/app/props/[playerId]/page.tsx`: prop analyzer: hit rate, 95% range, averages, chart, offers by book, game log, watch button
- `apps/web/src/components/ui/charts.tsx`: GameLogBars and Meter
- `apps/web/src/components/app/odds-format.tsx`: Price component used for prop prices
- `apps/web/src/components/app/freshness.tsx`: quote age / stale label on offers
- `apps/web/src/components/app/watch-button.tsx`: follow a player
- `apps/web/src/lib/types.ts`: PropAnalysis, PropBoardRow aliases
- `apps/web/src/lib/api.ts`: api, apiOrNull, withQuery
- `apps/web/src/lib/format.ts`: formatLine, formatPercent, titleCase, formatDay
- `apps/web/src/lib/leagues.ts`: getLeagues, pick (query validation)
- `apps/web/src/app/app/page.tsx`: dashboard fetches /v1/props and links to analyzer
- `apps/web/src/app/app/assistant/page.tsx`: fetches /v1/props for suggestions
- `apps/web/src/components/app/nav.tsx`: /app/props nav entry
- `apps/web/src/app/(marketing)/player-props/page.tsx`: marketing page

**Mobile (`apps/mobile`)**

- `apps/mobile/src/screens/props.tsx`: props board list, league and stat chips
- `apps/mobile/src/screens/prop-analyzer.tsx`: PropAnalyzerScreen and PropAnalysisView; window/split in local state
- `apps/mobile/src/components/game-log-chart.tsx`: GameLogChart and GameLogList
- `apps/mobile/src/app/(tabs)/(props)/_layout.tsx`: props stack, anchor 'props'
- `apps/mobile/src/app/(tabs)/(props)/props.tsx`: route wrapper for board
- `apps/mobile/src/app/(tabs)/(props)/player/[id].tsx`: route wrapper for analyzer, reads id and market
- `apps/mobile/src/app/(tabs)/_layout.tsx`: (props) tab trigger
- `apps/mobile/src/api/client.ts`: getProps, getPlayerProps
- `apps/mobile/src/api/types.ts`: PropBoardRow, PropAnalysis, PropOffer, PropWindow, PropSplit
- `apps/mobile/src/utils/routes.ts`: maps web /app/props/{id} links to /player/[id]
- `apps/mobile/src/components/price.tsx`: price display
- `apps/mobile/src/utils/format.ts`: formatLine, formatPercent, formatPrice, titleCase
- `apps/mobile/src/screens/assistant.tsx`: also calls getProps for suggestions
- `apps/mobile/src/test/fixtures.ts`: prop fixtures for tests

**Entry points**

- GET /v1/players?league=&q= - search players
- GET /v1/players/{player_id} - player and next event
- GET /v1/players/{player_id}/props?market=&window=5|10|20|season&split=all|home|away|vs_opponent - analyzer payload
- GET /v1/props?league=&market= - props board
- POST /v1/assistant (player_trend tool) - reuses Board.player_props; see services/api/src/oddvex_api/assistant
- Web /app/props?league=&market=
- Web /app/props/{playerId}?market=&window=&split=
- Web /player-props - marketing
- Mobile tab (props): /props - PropsScreen
- Mobile /player/[id]?market= - PropAnalyzerScreen
- services/api/scripts/build_replay_data.py - builds replay data incl. player stat lines
- services/api/scripts/export_openapi.py - regenerates openapi.json after schema changes

**Tests**

- `services/api/tests/quant/test_hitrate.py`: Wilson values, extremes, pushes, under direction, validation
- `services/api/tests/quant/test_properties.py`: Hypothesis: interval brackets estimate, hit_rate partitions sample
- `services/api/tests/test_api_data.py`: player search/detail, player props, windows and splits, validation, props board, board matches analyzer
- `services/api/tests/test_board.py`: prop best flags, season-median fallback line
- `services/api/tests/test_provider_synthetic.py`: 25+ game logs, player search, prop offers
- `services/api/tests/test_provider_replay.py`: prop lines use only prior games, no prop without history
- `services/api/tests/test_provider_contract.py`: game log normalizes, newest first
- `services/api/tests/test_replay_build_and_api.py`: build players with volume
- `services/api/tests/test_api_assistant.py`: player_trend matches props endpoint, ambiguous names
- `apps/web/e2e/app.spec.ts`: board table and analyzer show sample, range, caveat
- `apps/web/e2e/a11y.spec.ts and apps/web/e2e/security.spec.ts`: props pages in axe and header sweeps
- `apps/web/src/lib/format.test.ts`: format helpers
- `apps/mobile/src/screens/prop-analyzer.test.tsx`: sample text, Wilson range, caveat, offer labels, game log order, no-line state, GameLogChart
- `apps/mobile/src/utils/routes.test.ts`: /app/props link mapping
- `apps/mobile/src/utils/format.test.ts`: format helpers

**Data model**

none: computed on request. Players, game logs and prop offers come from the SportsDataProvider (in-memory synthetic or replay file); no table or Alembic migration holds lines, prices, logs or hit rates. Only adjacent table: watchlist_items (kind 'player', ref_id = provider player id, not a foreign key; migration 0002). In-process cache only: gamelog:{player_id} 30 s, propsboard:{league}:{market} 10 s.

**Flags and plan checks today**

None. The four routes have no require_flag, no auth dependency and no plan check; they are public. No prop key exists in flags/catalog.py or entitlements/catalog.py (catalog has only alerts, value_screen, tracker_analytics, odds_history_hours, and premium_gating is off). Mobile providers/flags.tsx notes props never ask for flags. Only the watch button needs a signed-in user.

**Backlog items that will touch it**

- **P0.1**: Prop offers and game logs are read live from the provider with no history, so the archive must capture PropOffer rows per book and Board must accept an as-of time instead of provider.now().
- **P0.2**: PlayerPropsOut and PropBoardRowOut carry consensus line, best price, hit rate and Wilson bounds with only as_of and a caveat; they need method id, version and inputs attached in board.py.
- **P0.6**: The props board shows best prices, so Board.props_board/player_props (or their routes) must call the suppression function, and HIT_RATE_CAVEAT plus the page notices fall under the copy check.
- **F01**: Matching a prop leg and pricing it reuses provider.list_players search, player.prop_markets and Board._prop_offers for the consensus line and best price.
- **F06**: Prop prices render through web Price/PriceCell and mobile Price in the board and analyzer, which need the dollars-per-$100 restatement.
- **F07**: Over rate, 95% range, consensus line and averages on both analyzers need an explain target fed by hit_rate inputs (hits, sample, pushes, line_source).
- **F08**: GameLogBars and Meter (web charts.tsx) and GameLogChart (mobile) need the Clear Mode variants.
- **F10**: Extends Board.player_props and quant/hitrate.py with a season baseline beside the window rate and leave-one-out and no-overtime recomputes; GameLogEntry has no overtime field today.
- **F11**: The props board and the offers panel show current markets and must be hidden while Quiet Mode is on, on web and mobile.
- **F13**: Reuses GET /v1/players?q= and the assistant's _find_players and _MARKET_WORDS matching to land on /app/props/{id}?market=.
- **F16**: Board._prop_offers computes best price over all books; it must filter to the user's state and books and explain missing offers.
- **F22**: A receipt of prop research stores the PlayerPropsOut payload (offers, line, hit rate, as_of) that is otherwise never persisted.
- **F27**: Grading-rule differences sit beside the per-book rows of the analyzer offers table (PropOfferOut).
- **F31**: A saved prop panel is the analyzer state (player, market, window, split), which web keeps in the URL and mobile in local state.
- **F32**: Fits a distribution to the no-vig prop over/under from Board._prop_offers and the game log; today only offers at the consensus line are compared and alt lines are ignored.
- **F33**: Adds condition-based cohorts to the PropSplit filter in Board.player_props; GameLogEntry only has opponent, is_home and stats.

**What a builder would get wrong by assuming**

1) Nothing is persisted: no table for players, lines, prices, game logs or hit rates; all provider-derived per request. 2) When no book posts a line the API still grades against a fallback (hit_rate.line_source = 'season_median', half-point at the season median), but both clients read consensus_line, say 'nothing to measure against' and hide the chart while still showing the over rate, range and per-game Over/Under computed against that fallback. 3) Hit rate is always 'over'; quant.hit_rate supports 'under' but no route exposes it. 4) Split is applied before the window, so 'last 10 + home' is the last 10 home games; the board's l10 is always all games. 5) 'season' is not a season: both providers cap the log at 40 games (GAME_LOG_GAMES). 6) Best over/under is chosen only among open, non-stale books at the consensus line; a better price at a different line is never flagged. 7) In replay mode prop lines are simulated from the player's trailing 6-game average, so hit rates against them are partly circular; no real book line exists. 8) Both clients filter the stat client-side and never send /v1/props?market=; they also each re-sort the game log and slice 20 for the chart, and duplicate the format helpers (web lib/format.ts, mobile utils/format.ts). 9) Window and split live in the URL on web but in local state on mobile, so mobile deep links carry only market. 10) Mobile route is /player/[id] inside the (props) group, not /props/[id]; utils/routes.ts translates web-style /app/props/{id} links. 11) wilson_interval is shared with quant/record.py (tracker record), so changing it changes tracker output. 12) There are two schema modules: api/schemas.py (prop models) and top-level schemas.py (PriceOut, BestPriceOut). 13) Rates are rounded to 4 decimals in board.py, not in quant. 14) Coverage gaps: mobile screens/props.tsx has no test and the web prop pages have only Playwright e2e. 15) Routes are public with no flag or plan check, so gating must be added, not adjusted.

## 4. A value screen comparing each book with the no-vig consensus of the others

A public, flag-gated GET /v1/value computes on each request (10 s cache) every outcome of non-final events whose best open, non-stale price beats the mean multiplicative no-vig probability of the other books at the same line (best book excluded, at least 2 others), sorted by edge. Board._value_rows in board.py groups provider odds snapshots by line and calls the pure quant.value.best_price_vs_consensus; the response carries rows plus method, caveat, as_of and data_mode. Web (/app/value, server component) and mobile (/value in the Tools stack) only render the API numbers with league, market and min-edge filters.

**API (`services/api`)**

- `services/api/src/oddvex_api/quant/value.py`: pure maths: BookQuote, ValueResult, consensus_probability, best_price_vs_consensus, MIN_CONSENSUS_BOOKS=2
- `services/api/src/oddvex_api/board.py`: Board.value_screen, _value_rows, _event_value_rows, _quote_rows, _usable, VALUE_METHOD, VALUE_CAVEAT, _VALUE_MARKETS, 10 s cache
- `services/api/src/oddvex_api/api/data.py`: list_value route (GET /value under /v1), require_flag dependency, query params
- `services/api/src/oddvex_api/api/schemas.py`: ValueRowOut, ValueScreenOut
- `services/api/src/oddvex_api/quant/ev.py`: expected_value, gives edge and break-even
- `services/api/src/oddvex_api/quant/novig.py`: no_vig multiplicative fair probabilities
- `services/api/src/oddvex_api/quant/odds.py`: validate_decimal_odds, american_to_decimal
- `services/api/src/oddvex_api/flags/catalog.py`: value_screen FlagSpec, default on
- `services/api/src/oddvex_api/flags/service.py`: require_flag, 404 feature_disabled
- `services/api/src/oddvex_api/entitlements/catalog.py`: value_screen entry, enabled for free and premium
- `services/api/src/oddvex_api/entitlements/service.py`: require_entitlement, exists but not used by the value route
- `services/api/src/oddvex_api/deps.py`: get_board / BoardDep builds Board per request
- `services/api/src/oddvex_api/schemas.py`: PriceOut, SportsbookRef, price_out used in rows
- `services/api/docs/QUANT_METHODOLOGY.md`: section 'Best price against the consensus of the other books'
- `services/api/openapi.json`: /v1/value and ValueScreenOut, source of generated types

**Web (`apps/web`)**

- `apps/web/src/app/app/value/page.tsx`: the whole screen: requireFlag, filters in URL, card list and table, Track this link
- `apps/web/src/lib/site.ts`: nav entry and path-to-flag map for /app/value
- `apps/web/src/lib/flags.ts`: requireFlag / flagOn, notFound when off
- `apps/web/src/app/app/odds/page.tsx`: link to /app/value when flag on
- `apps/web/src/app/(marketing)/methodology/page.tsx`: #edge-vs-consensus formula anchor linked from the screen
- `apps/web/src/app/(marketing)/features/page.tsx`: marketing blurb linking /app/value
- `apps/web/src/components/app/odds-format.tsx`: Price component used for best price
- `apps/web/src/components/app/freshness.tsx`: quote age display
- `apps/web/src/components/app/auto-refresh.tsx`: 60 s refresh
- `apps/web/src/lib/format.ts`: formatPercent, formatSignedPercent, formatLine
- `apps/web/src/lib/leagues.ts`: getLeagues, MARKETS, pick
- `packages/types/src/api.d.ts`: generated ValueScreenOut / ValueRowOut types

**Mobile (`apps/mobile`)**

- `apps/mobile/src/screens/value.tsx`: ValueScreen, ValueRowCard, EDGE_LABEL, MIN_EDGES, outcomeText, consensusText
- `apps/mobile/src/app/(tabs)/(tools)/value.tsx`: route file rendering ValueScreen
- `apps/mobile/src/app/(tabs)/(tools)/_layout.tsx`: Stack.Screen 'value' title
- `apps/mobile/src/components/value-entry.tsx`: ValueEntry panel / compact link, pushes /value
- `apps/mobile/src/screens/tools.tsx`: shows ValueEntry when flag on
- `apps/mobile/src/screens/games.tsx`: shows compact ValueEntry when flag on
- `apps/mobile/src/api/client.ts`: getValueScreen
- `apps/mobile/src/api/types.ts`: ValueScreen / ValueRow aliases
- `apps/mobile/src/providers/flags.tsx`: FlagKey includes value_screen, useFlag
- `apps/mobile/src/test/fixtures.ts`: valueScreen / valueRow fixtures, flagsAllOn

**Entry points**

- GET /v1/value?league=&market=&min_edge=&limit= - public, operation_id list_value, limit default 50 max 200, min_edge 0..10
- GET /v1/flags - clients read value_screen here
- Web: /app/value?league=&market=&min_edge=
- Web: link from /app/odds and app navigation
- Mobile: route /value (Tools stack), entered from Tools tab and Games screen via ValueEntry
- Mobile row tap: /event/[id]?market=
- Scripts: none specific to this part

**Tests**

- `services/api/tests/quant/test_value.py`: pure consensus and best-price maths
- `services/api/tests/test_api_value.py`: route rows, filters, limit, flag off 404, OpenAPI shape, banned-phrase scan
- `services/api/tests/test_api_flags_entitlements.py`: value_screen flag toggling and entitlement listing
- `services/api/tests/test_migrations_seed_openapi.py`: operation id list_value, route responds after seed
- `services/api/tests/test_security.py`: /v1/value in public-route lists
- `services/api/tests/test_api_review_followups.py`: /v1/value in public paths
- `services/api/tests/test_replay_build_and_api.py`: /v1/value works in replay mode
- `services/api/tests/test_api_admin_manage.py`: value_screen in admin flag list
- `apps/web/e2e/value-analytics.spec.ts`: screen content, URL filters, nav link, row to tracker panel
- `apps/web/e2e/admin.spec.ts`: flag off gives 404 on /app/value
- `apps/web/e2e/a11y.spec.ts`: a11y scan of /app/value
- `apps/web/e2e/app.spec.ts and apps/web/e2e/security.spec.ts`: /app/value in page sweeps
- `apps/web/src/lib/site.test.ts`: flagsForPath for /app/value
- `apps/mobile/src/screens/value.test.tsx`: ValueScreen states, filters, feature_disabled, ValueEntry navigation
- `apps/mobile/src/api/client.test.ts`: getValueScreen query building
- `apps/mobile/src/providers/flags.test.tsx`: value_screen flag handling

**Data model**

none: computed on request from SportsDataProvider.get_odds / list_events and cached about 10 s in the app Cache (key value:{league}:{market}). The only table involved is feature_flags (services/api/src/oddvex_api/db/models.py, migration services/api/alembic/versions/0004_flags_plans_admin_email.py) for the value_screen override.

**Flags and plan checks today**

Flag value_screen (default on) is enforced on the API route by require_flag (404 feature_disabled), on web by requireFlag in the page plus the site.ts nav/path map, and on mobile only by hiding ValueEntry (the screen itself just shows the API 404 state). The route is public: no sign-in. The entitlements catalog has a value_screen feature enabled for both free and premium, but the route does not call require_entitlement, so no plan check gates it today; premium_gating changes nothing here.

**Backlog items that will touch it**

- **P0.1**: Board._quote_rows reads only the provider's current odds, so the archive must capture the same per-book quotes and consensus inputs that _event_value_rows uses, to let value rows be rebuilt as of a time T.
- **P0.2**: ValueScreenOut carries method as free prose and one as_of; edge, consensus_probability and breakeven need a method id, version and stored inputs added in board.py and the schemas.
- **P0.3**: The value_screen entry in entitlements/catalog.py is not enforced on GET /v1/value, so server-side entitlement resolution has to be wired into the list_value route or left explicitly public.
- **P0.4**: Web and mobile value screens need the profile's books held, state and odds format instead of the current per-app odds-format providers and unfiltered rows.
- **P0.6**: The value screen is an opportunity surface, so list_value / Board.value_screen must call the suppression hook first and its strings (VALUE_METHOD, VALUE_CAVEAT, web and mobile copy) fall under the copy guard, replacing the local banned-phrase test.
- **F01**: Check My Bet's fair price and best price at the user's books should reuse quant.value consensus_probability and Board's _quote_rows/_usable grouping rather than a second implementation.
- **F06**: Dollar View must restate best price, break-even and edge in the web value page and mobile ValueRowCard as dollars per $100.
- **F07**: Every figure on the value rows (edge, consensus, break-even) needs a tap-to-explain target fed by the method, inputs and source books that the response does not yet return per row.
- **F08**: The web value table/cards with 60 s AutoRefresh and the mobile cards need Clear Mode styling and throttled polite announcements.
- **F09**: Directly extends this part: best_price_vs_consensus and ValueRowOut must return the contributing books, each quote's age and the edge recomputed with each book removed, shown beside every value figure on web and mobile.
- **F11**: Quiet Mode must hide this opportunity screen and its entry points (web nav, odds-page link, mobile ValueEntry) and block the route for the user.
- **F16**: Value rows must be filtered to the user's state and books, which changes which quotes _event_value_rows treats as the best book versus consensus inputs and needs an explanation for hidden prices.
- **F20**: Cash-Out Checker's fair value from current no-vig prices can reuse consensus_probability and the usable-quote selection in board.py.
- **F22**: Research Receipts needs a save action on value rows that snapshots the price, consensus and as_of shown, which are not stored anywhere today.
- **F25**: Limit Log's filter to books where the user's size fits has to restrict the best-book choice in the value screen.
- **F26**: SGP True Cost stage 1 needs per-leg no-vig fair prices, which should come from the same consensus function and quote grouping used here.
- **F34**: Historical Replay of a past slate needs Board.value_screen to run against archived quotes at a chosen time instead of provider.now().
- **F42**: The Discord bot returns fair price and best book through F01's API, which sits on this part's consensus and best-price code.

**What a builder would get wrong by assuming**

The starting hints had the wrong roots: the code is under apps/web/src/app/app/value and apps/mobile/src/screens, src/components, not apps/web/app or apps/mobile/screens. Nothing is persisted: rows are recomputed from the live provider with a 10 s cache, so there is no history, no stored inputs and no way to reproduce a past row. The response does not say which books fed the consensus or how old each quote was, only books_in_consensus and the best book's last_updated (F09 needs new fields and a new quant return shape). The consensus here is a mean of no-vig probabilities over books on the exact same line and outcome set, excluding the best book; it is a different thing from consensus_line / ConsensusOut used by the odds and props boards (most common line), so 'consensus' means two things in board.py. 'edge' is EV per unit assuming the consensus is true, and only positive-EV rows are returned, so the endpoint cannot be used as a general fair-price lookup for an arbitrary outcome. Only moneyline, spread and total are covered (_VALUE_MARKETS); props are not. The cache key ignores min_edge and limit, which are applied after caching. The value_screen entitlement exists in the catalog but is never checked; only the flag gates the route, and the route needs no sign-in. Mobile does not guard the route by flag: it hides the entry points and relies on the API 404. Presentation logic is duplicated: MIN_EDGES differ (web offers Any, 0.5%, 1%, 2%, 5% in the URL; mobile offers 1%, 2%, 5% in local state), and outcome/consensus label helpers are written separately in each app. Web has a 'Track this' link to the game's quick-bet panel for signed-in users; mobile rows only open the event. I ran no tests (read-only mapping task).

## 5. Calculators: expected value, no-vig, parlay, closing line value (CLV)

Five stateless public POST endpoints under /v1/quant (convert, no-vig, ev, parlay, clv) are thin wrappers in api/quant_routes.py over the pure-math package services/api/src/oddvex_api/quant; each response carries the numbers plus a human-readable `steps` list. Web (/app/tools, /app/parlay) and mobile (Tools tab: /tools, /parlay) do no betting math themselves: they post what was typed and render the reply, and the parlay builders pre-fill legs with best moneylines from GET /v1/events. Nothing is stored, nothing is gated by auth, flag, plan or rate limit.

**API (`services/api`)**

- `services/api/src/oddvex_api/api/quant_routes.py`: the 5 routes, request/response models, `steps` text, EV_CAVEAT
- `services/api/src/oddvex_api/quant/__init__.py`: public exports of the pure math package (no I/O, no clock)
- `services/api/src/oddvex_api/quant/odds.py`: American/decimal/fractional parsing, implied probability, describe_price
- `services/api/src/oddvex_api/quant/novig.py`: no_vig(): multiplicative de-vig, overround, hold
- `services/api/src/oddvex_api/quant/ev.py`: expected_value, payout, profit, roi, money (cent rounding), validate_stake
- `services/api/src/oddvex_api/quant/clv.py`: closing_line_value: price CLV plus optional no-vig CLV from the opposite close
- `services/api/src/oddvex_api/quant/parlay.py`: combine_parlay (price, correlation warnings, independence-only probability); also settle_bet/settle_parlay used by the tracker
- `services/api/src/oddvex_api/quant/errors.py`: QuantError with stable `code`
- `services/api/src/oddvex_api/schemas.py`: PriceOut, price_out, OddsFormatIn, OddsValue, odds_to_decimal shared with other routers
- `services/api/src/oddvex_api/errors.py`: QuantError handler: 422 error envelope
- `services/api/src/oddvex_api/main.py`: mounts quant router under /v1, 'quant' OpenAPI tag
- `services/api/docs/QUANT_METHODOLOGY.md`: formulas and limitations per calculator (no method ids or versions)
- `services/api/openapi.json`: generated contract with the /v1/quant/* paths
- `packages/types/src/api.d.ts`: generated TS types (quant_* operations, ConvertResponse, NoVigResponse, EVResponse, CLVResponse, ParlayRequest/Response)
- `services/api/src/oddvex_api/quant/value.py`: sibling: consensus/best-price math for the value screen, built on no_vig and expected_value
- `services/api/src/oddvex_api/bets/service.py`: other consumer: _leg_clv/bet_clv call closing_line_value for tracker CLV
- `services/api/src/oddvex_api/board.py`: other consumer: no_vig for fair probabilities and per-book hold
- `services/api/src/oddvex_api/assistant/engine.py`: other consumer: expected_value and no_vig for assistant explanations

**Web (`apps/web`)**

- `apps/web/src/app/app/tools/page.tsx`: Calculators page: convert, no-vig, EV, CLV with anchor nav and link to parlay
- `apps/web/src/app/app/parlay/page.tsx`: server page; builds leg options from GET /v1/events best moneylines
- `apps/web/src/components/app/calculators.tsx`: client components ConvertCalculator, NoVigCalculator, EvCalculator, ClvCalculator; useCalc hook; Working (steps) disclosure
- `apps/web/src/components/app/parlay-builder.tsx`: ParlayBuilder client component, posts /v1/quant/parlay
- `apps/web/src/lib/client-api.ts`: clientApi(): browser calls via same-origin /api/ov bridge
- `apps/web/src/app/api/ov/[...path]/route.ts`: bridge that forwards to the API
- `apps/web/src/lib/site.ts`: APP_NAV entries for /app/tools and /app/parlay (no flag)
- `apps/web/src/lib/format.ts`: formatAmerican, formatPercent, formatMoney used for display
- `apps/web/src/components/app/odds-format.tsx`: Price component and odds-format cookie context (used by parlay builder)
- `apps/web/src/components/ui/primitives.tsx`: Panel, Stat, Field, Notice used by calculators
- `apps/web/src/app/(marketing)/methodology/page.tsx`: public copy of the formulas
- `apps/web/src/app/(marketing)/features/page.tsx`: marketing links to /app/tools and /app/parlay
- `apps/web/src/app/(marketing)/pricing/page.tsx`: states 'All calculators and parlay research' as included

**Mobile (`apps/mobile`)**

- `apps/mobile/src/screens/tools.tsx`: ToolsScreen (4 calculators, value entry, parlay link) and ParlayScreen
- `apps/mobile/src/components/calculators.tsx`: Convert/NoVig/Ev/Clv calculators, useCalc hook
- `apps/mobile/src/components/parlay-builder.tsx`: ParlayBuilder, ParlayResultView, legOptions, parlayPayload
- `apps/mobile/src/app/(tabs)/(tools)/tools.tsx`: route file for /tools
- `apps/mobile/src/app/(tabs)/(tools)/parlay.tsx`: route file for /parlay
- `apps/mobile/src/app/(tabs)/(tools)/_layout.tsx`: Tools stack: tools, parlay, value
- `apps/mobile/src/api/client.ts`: quantConvert, quantNoVig, quantEv, quantClv, quantParlay
- `apps/mobile/src/api/types.ts`: ConvertResult, NoVigResult, EvResult, ClvResult, ParlayRequest, ParlayResult from generated schemas
- `apps/mobile/src/utils/format.ts`: cleanOdds, showTypedAmerican, formatAmerican, formatPercent, formatSignedPercent
- `apps/mobile/src/utils/routes.ts`: maps web /app/tools and /app/parlay links to /tools and /parlay
- `apps/mobile/src/components/states.tsx`: Working (steps toggle), Stat, StatGrid, Panel
- `apps/mobile/src/components/price.tsx`: Price display in the user's odds format
- `apps/mobile/src/providers/odds-format.tsx`: odds format provider used by parlay builder

**Entry points**

- POST /v1/quant/convert - operation quant_convert
- POST /v1/quant/no-vig - operation quant_no_vig (2 to 20 outcomes)
- POST /v1/quant/ev - operation quant_ev
- POST /v1/quant/parlay - operation quant_parlay (1 to 20 legs)
- POST /v1/quant/clv - operation quant_clv
- GET /v1/events - read by both parlay builders for moneyline leg options
- Web: /app/tools (anchors #convert, #no-vig, #ev, #clv)
- Web: /app/parlay
- Web: /api/ov/v1/quant/* - same-origin bridge the browser calls
- Web: /methodology - public formulas page
- Mobile: /tools - (tabs)/(tools)/tools, title 'Calculators'
- Mobile: /parlay - (tabs)/(tools)/parlay, title 'Parlay research'
- Scripts: none for the calculators (services/api/scripts/export_openapi.py regenerates the contract)

**Tests**

- `services/api/tests/test_api_quant.py`: HTTP tests for all 5 routes: worked examples, validation codes, parlay correlation and all-legs-dropped
- `services/api/tests/quant/test_novig_ev_clv.py`: unit tests for no_vig, payout/profit/roi, expected_value, closing_line_value
- `services/api/tests/quant/test_parlay_settlement.py`: combine_parlay, settle_bet, settle_parlay
- `services/api/tests/quant/test_odds.py`: conversions, parsing, implied probability
- `services/api/tests/quant/test_properties.py`: Hypothesis properties: round trips, no-vig sums to 1, EV/CLV sign, parlay product
- `services/api/tests/test_migrations_seed_openapi.py`: pins the 5 quant operation ids in the OpenAPI contract
- `services/api/tests/test_platform.py`: uses /v1/quant/convert for error envelope, bad JSON, body size limit
- `services/api/tests/test_security.py`: lists /v1/quant as a public prefix (no token required)
- `services/api/tests/test_api_review_followups.py`: lists /v1/quant as public for suspended-account check
- `apps/web/e2e/app.spec.ts`: EV example, no-vig -110/-110, bad odds message, same-game parlay warning, cross-origin POST to /api/ov/v1/quant/convert
- `apps/web/e2e/a11y.spec.ts`: axe checks include /app/tools and /app/parlay
- `apps/web/e2e/security.spec.ts`: header/CSP checks include /app/tools
- `apps/mobile/src/components/calculators.test.tsx`: all four calculators: payload sent, result shown, API error shown
- `apps/mobile/src/components/parlay-builder.test.tsx`: legOptions, parlayPayload, ParlayResultView, ParlayBuilder flow
- `apps/mobile/src/utils/routes.test.ts`: web-link to mobile-route mapping (file exists; tools/parlay cases not confirmed)

**Data model**

none: computed on request. The /v1/quant routes take no DB session and write nothing; no migration belongs to them. Related but separate: bet_legs.closing_odds_decimal and bet_legs.closing_opposite_odds_decimal (services/api/src/oddvex_api/db/models.py) feed the tracker's CLV through the same closing_line_value function.

**Flags and plan checks today**

None. The quant router has no auth dependency, no require_flag, no entitlement check and no rate_limit dependency; tests assert /v1/quant is public. No flag in flags/catalog.py and no key in entitlements/catalog.py covers calculators or parlay. Web nav entries for /app/tools and /app/parlay carry no flag and are not in FLAGGED_PATHS; mobile shows them without asking for flags (only the value entry on the Tools screen checks value_screen). The pricing page lists calculators and parlay research as included.

**Backlog items that will touch it**

- **P0.2**: The quant functions and the /v1/quant responses carry only a hard-coded method="multiplicative" on no-vig and free-text steps, so method id, version, inputs and as-of time must be added to the result dataclasses and response models here.
- **P0.3**: The quant router is fully public today, so any plan or b2b-key resolution (and the rate limits F41/F42 need) has to be added as a dependency on these routes.
- **P0.4**: Calculators and parlay builders hold their odds-format choice in local component state (parlay is American-only) and default stakes are hard-coded, so they must read the synced odds format and unit size.
- **P0.6**: The copy guard will scan EV_CAVEAT, the generated steps strings in quant_routes.py and the calculator/parlay UI copy on web and mobile.
- **F01**: Reuses no_vig, probability_to_decimal, combine_parlay and price_out to produce the fair price and cost per $100 for each parsed leg and the whole slip.
- **F03**: Reuses closing_line_value and the price-versus-fair comparison from quant to compute CLV and dollars paid above the best price.
- **F06**: Needs a dollars-risked, dollars-won and vig-cost-per-$100 calculation added beside no_vig/payout in quant and shown in the calculator and parlay results on both clients.
- **F07**: Generalises the existing steps list and the Working disclosure components (web calculators.tsx, mobile states.tsx) into the formula-and-inputs explanation for every number.
- **F08**: Calculator and parlay result regions already use aria-live/accessibilityLiveRegion and tables, which Clear Mode must restyle and throttle.
- **F09**: Reuses no_vig and the consensus functions in quant/value.py to recompute the value figure with each book removed.
- **F19**: Reuses closing_line_value's ev_at_close_percent, roi and wilson_interval for the CLV-implied ROI and interval.
- **F20**: Reuses no_vig, combine_parlay and settle_bet's cashout handling to price an open bet's fair value and adds hedge sizing next to them in quant.
- **F26**: Extends combine_parlay, POST /v1/quant/parlay and both ParlayBuilder components to de-vig each leg, show the fair parlay price and hold, and later replace the same-event refusal with a correlation model.
- **F28**: Reuses no_vig on three-way prices and adds draw-no-bet, double-chance and Asian-handicap conversions as a new quant module and calculator.
- **F29**: Reuses no_vig, hold and odds conversion to score drill answers for fair price and hold.
- **F32**: Reuses no_vig and probability_to_decimal as the input and output of the distribution fit, and adds a new module to the quant package.
- **F40**: Reuses the odds conversion functions (probability_to_decimal, describe_price) to restate contract prices as odds after fees.
- **F41**: Would expose the existing /v1/quant calculations as read-only sheet functions, which needs keys and rate limits these routes lack.

**What a builder would get wrong by assuming**

1) Nothing is stored: no calculation, input or timestamp is persisted, and the routes take no DB session. 2) The routes are public with no rate limit of their own (only auth and assistant routers use rate_limit). 3) The EV calculator never estimates a probability; the user supplies it. Fair price exists only via no-vig. 4) Parlay: the user-facing copy says it shows "how often it has to win", but that break-even is just the combined price's implied probability; combined_probability needs per-leg win_probability, which neither client sends, so it is always null from the apps. Same-event legs or legs without event_id only produce a warning; there is no SGP pricing and no de-vig of legs. 5) Parlay builders offer only best moneylines from /v1/events (first 20 non-final events on web), custom legs are American-only, and the request sends American odds regardless of the user's odds format. 6) ParlayLegIn.result accepts only pending/won/push/void, while quant.parlay also handles lost/half_won/half_lost; quant/parlay.py also holds bet settlement (settle_bet, settle_parlay) used by the tracker, so the file name understates its reach. 7) CLV exists twice: the stateless calculator and the tracker (bets/service.py), and the tracker uses only price-based CLV even though closing_opposite_odds_decimal is stored. 8) Web calculators.tsx and parlay-builder.tsx declare hand-written response types inline rather than using the generated schemas; mobile uses generated types. UI logic is duplicated across web and mobile (two useCalc hooks, two ParlayBuilders, two odds-cleaning helpers), but no arithmetic is duplicated: both only convert percent to fraction. 9) No-vig supports only the multiplicative method; `method` is a Literal with one value. 10) QuantError maps to 422 with a specific code, distinct from pydantic's validation_error. 11) The odds format in the calculators is American/decimal/fractional per form; the global toggle (web cookie ov_odds) offers only American/decimal and no implied-probability mode. 12) quant/__init__.py does not export value.py, tracker.py or record.py names; consumers import those submodules directly.

## 6. Bet tracker with auto-settlement, ROI analytics and sportsbook sync

A complete manual bet tracker exists: users log straight/parlay/sgp/future bets with free-text or structured legs (POST /v1/bets), settle them manually or via on-demand auto-settle that grades structured legs from provider final scores (quant/grading.py) through the single bets.service.settle path, and read summary/analytics that are recomputed from the bets table on every request. "Sportsbook sync" is a mock-only provider behind a SyncProvider protocol and registry; an import run fetches a deterministic fictional history, de-duplicates on (user, provider, external_bet_id) and inserts Bet rows with source="sync". Web (/app/tracker, /app/tracker/analytics) and mobile ((tracker) tab: tracker, log-bet, analytics) render API numbers only; the only gate is the tracker_analytics feature flag.

**API (`services/api`)**

- `services/api/src/oddvex_api/bets/router.py`: /v1/bets routes, owner scoping, audit, notifications
- `services/api/src/oddvex_api/bets/service.py`: create/update/settle, auto_settle, bet_out, bet_clv, summarize
- `services/api/src/oddvex_api/bets/schemas.py`: BetCreate/BetOut/settle/summary/analytics models, literals
- `services/api/src/oddvex_api/bets/analytics.py`: analyze(): odds bands, weekdays, months, streaks, CLV, stake buckets
- `services/api/src/oddvex_api/sync/router.py`: /v1/sync routes, import run, disconnect
- `services/api/src/oddvex_api/sync/service.py`: run_import retries, dedupe, _to_bet mapping
- `services/api/src/oddvex_api/sync/base.py`: SyncProvider protocol, ExternalBet/ExternalLeg, FetchResult
- `services/api/src/oddvex_api/sync/mock.py`: MockSyncProvider, fictional deterministic history
- `services/api/src/oddvex_api/sync/registry.py`: SyncRegistry, default_registry (mock only)
- `services/api/src/oddvex_api/sync/schemas.py`: sync request/response models
- `services/api/src/oddvex_api/sync/__init__.py`: package exports
- `services/api/src/oddvex_api/quant/grading.py`: grade_leg, is_gradeable, valid_outcome_keys (moneyline/spread/total)
- `services/api/src/oddvex_api/quant/parlay.py`: settle_bet, settle_parlay, ParlayLeg, Settlement
- `services/api/src/oddvex_api/quant/clv.py`: closing_line_value (price-based CLV)
- `services/api/src/oddvex_api/quant/tracker.py`: odds_band, bucket_index, win_rate, mean, streaks
- `services/api/src/oddvex_api/quant/ev.py`: money, payout, profit, roi used by tracker
- `services/api/src/oddvex_api/db/models.py`: Bet, BetLeg, SyncConnection, SyncImportRun; sportsbook_key mapper event
- `services/api/src/oddvex_api/main.py`: mounts bets and sync routers under /v1, app.state.sync_registry
- `services/api/src/oddvex_api/config.py`: sync_max_attempts (ODDVEX_SYNC_MAX_ATTEMPTS, default 3)
- `services/api/src/oddvex_api/flags/catalog.py`: tracker_analytics flag (default on)
- `services/api/src/oddvex_api/entitlements/catalog.py`: tracker_analytics entitlement, same for both plans
- `services/api/src/oddvex_api/notifications/service.py`: staked_this_week, check_stake_reminder read bets
- `services/api/src/oddvex_api/notifications/templates.py`: bet_settled, sync_finished templates
- `services/api/src/oddvex_api/account/router.py`: data export reuses bets.service.bet_out
- `services/api/src/oddvex_api/assistant/engine.py`: bet_summary answer reuses bets.service.summarize
- `services/api/src/oddvex_api/seed.py`: demo bets incl. gradeable pending bets for auto-settle
- `services/api/src/oddvex_api/api/admin.py`: bet and sync-connection counts only

**Web (`apps/web`)**

- `apps/web/src/app/app/tracker/page.tsx`: tracker page: summary, open/settled bets, form, sync panel
- `apps/web/src/app/app/tracker/analytics/page.tsx`: analytics page, requireFlag(tracker_analytics)
- `apps/web/src/components/app/bet-form.tsx`: log-a-bet form, POST /v1/bets
- `apps/web/src/components/app/bet-actions.tsx`: settle, leg-by-leg settle, edit, closing odds, delete
- `apps/web/src/components/app/auto-settle.tsx`: AutoSettleButton, POST /v1/bets/auto-settle
- `apps/web/src/components/app/sync-panel.tsx`: connect, import, disconnect (always delete_data=true)
- `apps/web/src/components/app/quick-bet.tsx`: structured quick bet from a game page
- `apps/web/src/app/app/games/[id]/page.tsx`: hosts QuickBet, builds its options
- `apps/web/src/components/app/notification-settings.tsx`: StakeReminderNotice shown on tracker
- `apps/web/src/components/ui/charts.tsx`: ProfitChart, Meter used by tracker pages
- `apps/web/src/lib/flags.ts`: getFlags, flagOn, requireFlag
- `apps/web/src/lib/site.ts`: nav entry and flag-gated path /app/tracker/analytics
- `apps/web/src/lib/types.ts`: Bet, BetSummary, Breakdown type aliases
- `apps/web/src/lib/client-api.ts`: clientApi used by all tracker mutations
- `apps/web/src/app/(marketing)/bet-tracking/page.tsx`: marketing page for the tracker

**Mobile (`apps/mobile`)**

- `apps/mobile/src/screens/tracker.tsx`: tracker screen: summary, bets, sync, auto-settle
- `apps/mobile/src/screens/analytics.tsx`: analytics screen, API numbers only
- `apps/mobile/src/screens/log-bet.tsx`: log-a-bet screen wrapper
- `apps/mobile/src/components/bet-form.tsx`: form plus buildBetPayload
- `apps/mobile/src/components/bet-card.tsx`: bet card with settle/edit/delete payload builders
- `apps/mobile/src/components/sync-panel.tsx`: connect, import, disconnect
- `apps/mobile/src/components/auto-settle.tsx`: AutoSettleButton and result text
- `apps/mobile/src/components/quick-bet.tsx`: QuickBet, quickBetOptions, quickBetPayload
- `apps/mobile/src/screens/game-detail.tsx`: hosts QuickBet
- `apps/mobile/src/app/(tabs)/(tracker)/_layout.tsx`: stack: tracker, log-bet, analytics
- `apps/mobile/src/app/(tabs)/(tracker)/tracker.tsx`: route file
- `apps/mobile/src/app/(tabs)/(tracker)/log-bet.tsx`: route file
- `apps/mobile/src/app/(tabs)/(tracker)/analytics.tsx`: route file
- `apps/mobile/src/api/client.ts`: getBets, getBetSummary, getBetAnalytics, settle, autoSettle, sync calls
- `apps/mobile/src/api/types.ts`: Bet, BetSummary, SyncConnection type aliases
- `apps/mobile/src/providers/flags.tsx`: useFlag('tracker_analytics')
- `apps/mobile/src/providers/session.tsx`: session.changed('bets') revision counter for refetch
- `apps/mobile/src/utils/routes.ts`: maps web /app/tracker links to /tracker

**Entry points**

- GET /v1/bets - list, filters status/sport/market/sportsbook/bet_type, sort, limit/offset
- POST /v1/bets - record a bet
- GET /v1/bets/summary - totals, breakdowns, cumulative profit timeline
- GET /v1/bets/analytics - flag tracker_analytics
- POST /v1/bets/auto-settle - grade pending bets from final scores
- GET /v1/bets/{bet_id}
- PATCH /v1/bets/{bet_id} - edit; closing odds per leg
- DELETE /v1/bets/{bet_id}
- POST /v1/bets/{bet_id}/settle - manual settle or correction
- GET /v1/sync/providers
- GET /v1/sync/connections
- POST /v1/sync/connections - mock authorization
- POST /v1/sync/connections/{connection_id}/sync - run import
- GET /v1/sync/connections/{connection_id}/runs - import history (no client uses it)
- DELETE /v1/sync/connections/{connection_id}?delete_data=bool
- GET /v1/me/stake-reminder - read by the web tracker page
- Web: /app/tracker
- Web: /app/tracker/analytics
- Web: /app/games/[id] - QuickBet panel
- Web: /bet-tracking - marketing
- Mobile: /tracker ((tabs)/(tracker)/tracker)
- Mobile: /log-bet ((tabs)/(tracker)/log-bet)
- Mobile: /analytics ((tabs)/(tracker)/analytics)
- Mobile: event/[id] game detail - QuickBet
- Script: services/api/scripts/seed_demo.py - seeds demo bets
- No scheduled settle or sync job: auto-settle and import run only when a client calls them

**Tests**

- `services/api/tests/test_api_bets.py`: bet CRUD, settle, filters, summary, ownership (23 tests)
- `services/api/tests/test_api_auto_settle.py`: structured legs, auto-settle outcomes and skip reasons (22)
- `services/api/tests/test_api_analytics.py`: /bets/analytics and flag (7)
- `services/api/tests/test_api_sync.py`: connect, import, dedupe, retries, disconnect (15)
- `services/api/tests/test_api_review_followups.py`: assorted follow-ups touching bets/sync
- `services/api/tests/test_api_notifications.py`: bet_settled, sync_finished, stake reminder
- `services/api/tests/test_api_account.py`: export/delete include bets and sync
- `services/api/tests/test_api_flags_entitlements.py`: tracker_analytics flag and entitlement
- `services/api/tests/test_migrations_seed_openapi.py`: schema, seed bets, OpenAPI in sync
- `services/api/tests/quant/test_grading.py`: grade_leg, is_gradeable
- `services/api/tests/quant/test_parlay_settlement.py`: settle_bet, settle_parlay
- `services/api/tests/quant/test_novig_ev_clv.py`: closing_line_value, roi, payout
- `services/api/tests/quant/test_tracker.py`: odds_band, streaks, win_rate
- `services/api/tests/quant/test_properties.py`: property tests over quant
- `apps/web/e2e/app.spec.ts`: log/settle/delete, edit and closing odds, leg-by-leg parlay, isolation, quick bet
- `apps/web/e2e/value-analytics.spec.ts`: tracker analytics describe block
- `apps/web/e2e/a11y.spec.ts`: axe on /app/tracker and /app/tracker/analytics
- `apps/mobile/src/screens/tracker.test.tsx`: tracker screen
- `apps/mobile/src/screens/analytics.test.tsx`: analytics screen
- `apps/mobile/src/components/bet-form.test.tsx`: buildBetPayload and form
- `apps/mobile/src/components/bet-card.test.tsx`: settle/edit payloads, card
- `apps/mobile/src/components/sync-panel.test.tsx`: sync panel
- `apps/mobile/src/components/auto-settle.test.tsx`: auto-settle button
- `apps/mobile/src/components/quick-bet.test.tsx`: quick bet options and payload
- `apps/mobile/src/api/client.test.ts`: API client incl. bets/sync paths
- No web unit tests for tracker components; web coverage is Playwright only. No tests were run for this mapping.

**Data model**

Tables: bets (user_id, bet_type, status pending|settled, result, sport, sportsbook free text + sportsbook_key, stake, odds_decimal, odds_source legs|override, payout, profit, notes, placed_at, settled_at, settled_by user|auto|null, source manual|sync, sync_connection_id FK SET NULL, external_provider, external_bet_id; unique uq_bets_user_external on user_id+external_provider+external_bet_id); bet_legs (bet_id, position, selection, market, league, event_id, event_label, line, outcome_key, odds_decimal, closing_odds_decimal, closing_opposite_odds_decimal, result); sync_connections (user_id, provider, status, label, provider_state JSON, last_synced_at, disconnected_at); sync_import_runs (connection_id, status, attempts, fetched/imported/duplicate counts, retryable, error_message, started_at, finished_at). Also writes audit_log and notifications, reads stake_reminders and feature_flags. Migrations: services/api/alembic/versions/0001_initial_schema.py (all four tables), 0002_watchlist_structured_legs_password.py (bets.settled_by, bet_legs.outcome_key), 0005_community_and_search_keys.py (bets.sportsbook_key). Summary, analytics, CLV, ROI, potential payout and gradeable are computed on request and never stored.

**Flags and plan checks today**

Only one gate: feature flag tracker_analytics (default on) via require_flag on GET /v1/bets/analytics (404 feature_disabled when off), requireFlag on the web analytics page, flagOn/useFlag to hide the analytics link on web and mobile, and FLAG_PATHS in apps/web/src/lib/site.ts. Everything else (bets CRUD, summary, auto-settle, sync) needs only a logged-in user (CurrentUserDep); no flag. Entitlements catalog has a tracker_analytics key but it is enabled for both free and premium, the premium_gating flag is off by default, and no bets/sync route calls an entitlement check. No plan limits on bet count or sync connections (one connection per provider per user is a 409 rule, not a plan check).

**Backlog items that will touch it**

- **P0.1**: Bets store only user-entered closing odds per leg, so placement-time best price and closing lines for bets must come from the archive keyed on bet_legs.event_id/market/outcome_key/placed_at.
- **P0.2**: ROI, CLV, summary and analytics figures in bets/service.py and bets/analytics.py are returned as bare floats with no method id, version or as-of time and will need provenance attached.
- **P0.3**: bets and sync routers gate only on login plus the tracker_analytics flag, so server-side entitlement checks would be added to these routes.
- **P0.4**: Bet forms take a free-text sportsbook and per-request odds_format and there is no unit size, so tracker forms and displays will read books held, odds format and unit size from profile settings.
- **P0.6**: notifications.notify calls for bet_settled and sync_finished in bets/router.py and sync/router.py are notification senders that must call the suppression hook first.
- **F01**: One-tap logging reuses BetCreate/BetLegIn, resolve_structured_legs and POST /v1/bets, the same path QuickBet already uses.
- **F02**: Builds directly on sync_connections, sync_import_runs and run_import, which today only count duplicates and record no date coverage, gaps or grading disagreements, and on settle() for confirmed corrections.
- **F03**: Extends summarize/analyze (results by bet type, CLV) with a weekly window and price-paid-versus-best figures per bet.
- **F04**: Open-bets and settlements-needing-a-look cards read pending bets and auto-settle skip reasons from bets/service.py.
- **F05**: Tax-year winnings and losses by book and day aggregate bets.profit by sportsbook_key and settled_at, and statement/CSV import needs a new SyncProvider or importer feeding _to_bet with the same dedupe key.
- **F06**: Tracker pages and bet cards render prices through Price/price_out and would need the dollar restatement for bet and leg prices.
- **F07**: Tracker and analytics numbers (ROI, CLV, win rate, streaks) need explanations and formulas sourced from quant/clv.py, quant/ev.py and quant/tracker.py.
- **F11**: Quiet Mode must stop the bet_settled, sync_finished and stake_reminder notifications emitted from the bets and sync routers.
- **F14**: Onboarding's connect-a-book step reuses POST /v1/sync/connections and run_import, then derives books and unit size from imported bets.
- **F15**: Adds tags to bets (new table or column), a tag filter on list_bets, and a per-tag breakdown alongside _breakdown/analyze with interval and average CLV.
- **F18**: Lists every open leg from pending bets via bet_legs.event_id/outcome_key/line and can reuse quant.grade_leg logic against live box scores.
- **F19**: Extends bets/analytics.py and quant/tracker.py with ROI intervals and CLV-implied ROI over the same settled-bet set.
- **F20**: Operates on an open Bet and its legs, and the existing cashout result with cashout_amount in settle() records the outcome.
- **F21**: Computes worst-case loss from pending bets grouped by bet_legs.event_id, restricted to verified bets (source=sync or structured legs).
- **F23**: Weekly budget and bet count reuse notifications.staked_this_week and the create_bet/run_sync hooks where check_stake_reminder is called today.
- **F24**: Pause must keep bets and sync records readable under a reduced entitlement, which touches gating on the bets and sync routes.
- **F26**: Fair price and hold for a logged cross-game parlay reuse bet legs plus quant/parlay.py combine_parlay in the tracker's bet view.
- **F30**: Reads each bet's sportsbook_key, leg event/market/outcome and placed_at to compare against archived prices at other books.
- **F35**: Evidence pack is built from a settled Bet, its legs, settled_by, external_bet_id and the bet.settle/bet.auto_settle audit entries.
- **F36**: Complaint drafts pull the user's bet and settlement records from the bets tables.
- **F38**: Creator pages count only bets with source=sync, reusing bet_clv and ROI from bets/service.py.
- **F39**: Shares the F05 tax-year report built from bets, so it reuses the same aggregation over the bets table.
- **F41**: Sheets functions for the user's own bets wrap GET /v1/bets and /v1/bets/summary and need key-based auth and rate limits on them.

**What a builder would get wrong by assuming**

1. Sync is mock-only: sync/registry.py registers just MockSyncProvider ("Mockingbird Sportsbook (mock)"), authorize takes no credentials, and the history is a hardcoded tuple; the first import returns 10 bets and later imports the full list. 2. Synced legs carry no event_id or outcome_key (ExternalLeg has neither and _to_bet sets neither), so synced pending bets are never auto-settleable and cannot be joined to events, odds or an archive without a matching step. 3. Synced bets that arrive settled bypass bets.service.settle: profit is payout minus stake from the provider and settled_by stays null; _to_bet also duplicates sport_of/product_of_legs logic from bets/service.py. 4. Auto-settlement is not a background job; it runs only when a user presses the button (POST /v1/bets/auto-settle), covers moneyline/spread/total only (GRADEABLE_MARKETS), and does not handle props. Likewise sync has no scheduler. 5. Summary and analytics are recomputed from all of the user's bets in Python on every request; nothing is stored, there is no date-range parameter, and list_bets defaults to limit 500 while web and mobile fetch without paging. 6. CLV is price-based from closing odds the user typed in (or the mock supplied); there is no closing-line capture, closing_opposite_odds_decimal is stored but not used by bet_clv, and summarize averages CLV over all bets including pending while everything else is settled-only. 7. Re-import after an edit never updates: dedupe skips any existing (user, provider, external_bet_id), so a bet that was pending at first import and later settled at the book stays pending; "duplicate_count" means already-imported, not a likely duplicate of a manual bet. No manual-versus-sync duplicate detection exists. 8. sportsbook is free text (folded into sportsbook_key), not a foreign key to the sportsbooks catalog; by_sportsbook groups on the raw string, so case variants split rows there even though the list filter folds them. 9. Disconnect in both clients always sends delete_data=true; the keep-bets branch exists only in the API, and its UPDATE is not filtered by user_id (connection ownership is checked first). GET /v1/sync/connections/{id}/runs and simulate_failures are used by no client. SyncConnection.status and disconnected_at exist but connection_out hardcodes status "active" and disconnect hard-deletes the row and its runs. 10. Web and mobile duplicate client logic: payload building and validation live separately in web bet-form.tsx/bet-actions.tsx and mobile bet-form.tsx (buildBetPayload)/bet-card.tsx (settlePayload, legSettlePayload, editPayload), and quick-bet option building is separate too (mobile quickBetOptions is also imported by alert-form and share-pick; web share-pick imports the QuickBetOption type). 11. Names that mislead: quant/tracker.py is descriptive statistics, not the tracker; quant/record.py is flat-stake records for community picks, not bets; Bet.sport holds a league key or "multi"/"unknown"; wins/losses/pushes in the summary are derived from profit sign, so a cashout or half result counts by its profit; the stake "reminder" never blocks a bet. 12. bet_type includes sgp and future but they get no special handling: an sgp priced from legs is multiplied as if legs were independent unless the user supplies an override price. 13. There are no tags, unit size, account identifier or statement fields on bets today; adding any needs a migration plus OpenAPI export and packages/types regeneration.

## 7. Watchlist, price and line-move alerts, in-app notifications

Signed-in users can follow teams, players and events (watchlist_items), create four kinds of alert rule (price_at_least, line_move, game_start, game_final) and read in-app notifications with per-kind switches and a weekly staking reminder. Rules are evaluated lazily: on GET /v1/notifications and /v1/notifications/unread-count (throttled per user in process memory), on POST /v1/alerts/evaluate, and by scripts/evaluate_alerts.py, which the Hostinger compose worker loops every 120 s. A pure evaluator decides fire/expire from the live Board (best price, consensus line), and notifications.service.notify writes rows through the single InAppChannel with a (user_id, dedupe_key) unique constraint; bets, sync and community also call notify. Web and mobile are thin clients over the same routes; there is no push, email or SMS.

**API (`services/api`)**

- `services/api/src/oddvex_api/alerts/evaluator.py`: pure fire/expire decision, dedupe_key, drafts
- `services/api/src/oddvex_api/alerts/service.py`: from_body, arm, gather_inputs, evaluate_user_alerts, rule_out
- `services/api/src/oddvex_api/alerts/router.py`: /v1/alerts CRUD, evaluate, state transitions, limits
- `services/api/src/oddvex_api/alerts/schemas.py`: AlertCreate union, MAX_ACTIVE_ALERTS=100, MAX_TOTAL_ALERTS=500
- `services/api/src/oddvex_api/alerts/throttle.py`: EvaluationThrottle (in-memory), evaluate_if_due
- `services/api/src/oddvex_api/notifications/service.py`: notify, trim, preferences, cursor paging, stake reminder
- `services/api/src/oddvex_api/notifications/channels.py`: NotificationChannel protocol, InAppChannel, DEFAULT_CHANNELS
- `services/api/src/oddvex_api/notifications/templates.py`: TEMPLATES, NotificationDraft, all notification copy and hrefs
- `services/api/src/oddvex_api/notifications/router.py`: notifications, preferences, stake-reminder routes
- `services/api/src/oddvex_api/notifications/schemas.py`: NotificationKind (10 kinds), MAX_NOTIFICATIONS=500
- `services/api/src/oddvex_api/watchlist/router.py`: /v1/watchlist routes, MAX 200 items, idempotent add
- `services/api/src/oddvex_api/watchlist/service.py`: describe, item_out, watched_events
- `services/api/src/oddvex_api/watchlist/schemas.py`: WatchlistKind team|player|event
- `services/api/scripts/evaluate_alerts.py`: batch evaluation for all users, --dry-run
- `services/api/src/oddvex_api/db/models.py`: WatchlistItem, AlertRule, Notification, NotificationPreference, StakeReminder
- `services/api/alembic/versions/0002_watchlist_structured_legs_password.py`: creates watchlist_items
- `services/api/alembic/versions/0003_alerts_notifications_stake_reminder.py`: creates alert_rules, notifications, notification_preferences, stake_reminders
- `services/api/src/oddvex_api/board.py`: best_price and consensus_outcome_line used by alerts
- `services/api/src/oddvex_api/main.py`: mounts routers under /v1, app.state.alert_throttle
- `services/api/src/oddvex_api/config.py`: alert_eval_min_seconds (ODDVEX_ALERT_EVAL_MIN_SECONDS, default 30)
- `services/api/src/oddvex_api/entitlements/catalog.py`: alerts.max_active entry (declared, not enforced)
- `services/api/src/oddvex_api/bets/router.py`: calls notify (bet_settled) and check_stake_reminder
- `services/api/src/oddvex_api/sync/router.py`: calls notify (sync_finished) and check_stake_reminder
- `services/api/src/oddvex_api/community/router.py`: notify for pick_comment, new_follower
- `services/api/src/oddvex_api/community/service.py`: notify for pick_graded
- `services/api/src/oddvex_api/account/router.py`: data export includes watchlist, alerts, notifications
- `services/api/src/oddvex_api/seed.py`: seed_demo_alerts builds and evaluates demo rules
- `services/api/src/oddvex_api/middleware.py`: no-store prefixes include /v1/watchlist, not /v1/alerts or /v1/notifications
- `infrastructure/hostinger/compose.yaml`: worker loop runs evaluate_alerts.py every 120 s

**Web (`apps/web`)**

- `apps/web/src/app/app/alerts/page.tsx`: /app/alerts: notifications panel plus rule list
- `apps/web/src/components/app/alerts-panels.tsx`: NotificationList and AlertRuleList (read, delete, pause, re-arm, Check now)
- `apps/web/src/components/app/alert-form.tsx`: Set an alert form on a game (event-scoped only)
- `apps/web/src/components/app/watch-button.tsx`: Follow/Following toggle
- `apps/web/src/components/app/notification-settings.tsx`: NotificationPreferences, StakeReminderForm, StakeReminderNotice
- `apps/web/src/lib/watchlist.ts`: getWatchlist, watchId (server-only)
- `apps/web/src/app/app/layout.tsx`: header bell with unread count, links to /app/alerts
- `apps/web/src/app/app/page.tsx`: Your watchlist section on the app home
- `apps/web/src/app/app/games/[id]/page.tsx`: WatchButtons and AlertForm panel
- `apps/web/src/app/app/props/[playerId]/page.tsx`: player WatchButton
- `apps/web/src/app/app/settings/page.tsx`: notification switches and stake reminder
- `apps/web/src/app/app/tracker/page.tsx`: StakeReminderNotice
- `apps/web/src/lib/site.ts`: Alerts nav entry
- `apps/web/src/components/app/nav.tsx`: alerts icon
- `apps/web/src/app/api/ov/[...path]/route.ts`: proxy allowlist includes watchlist, alerts, notifications, me

**Mobile (`apps/mobile`)**

- `apps/mobile/src/screens/notifications.tsx`: Notifications/Alerts segmented inbox
- `apps/mobile/src/app/(tabs)/(games)/notifications.tsx`: route /notifications, ?tab=alerts
- `apps/mobile/src/app/(tabs)/(games)/_layout.tsx`: NotificationBell in Games header, registers the screen
- `apps/mobile/src/components/notification-list.tsx`: paged list, mark read, delete, kind labels
- `apps/mobile/src/components/alert-list.tsx`: rule list, pause/resume/re-arm/delete, check now
- `apps/mobile/src/components/alert-form.tsx`: Set an alert, incl. team game_start alert; suggestedThreshold, readThreshold
- `apps/mobile/src/components/notification-bell.tsx`: header bell and unread badge
- `apps/mobile/src/components/notification-settings.tsx`: preference switches, stake reminder form and notice
- `apps/mobile/src/components/watch-button.tsx`: follow toggle
- `apps/mobile/src/hooks/use-notifications.ts`: useUnreadCount, useReloadOnReturn, useStakeReminder
- `apps/mobile/src/hooks/use-watchlist.ts`: useWatchlist, watchId
- `apps/mobile/src/api/client.ts`: watchlist, alerts, notifications, preferences calls
- `apps/mobile/src/api/types.ts`: aliases over @oddvex/types (AlertCreate, Notification, WatchItem)
- `apps/mobile/src/utils/routes.ts`: maps web hrefs in notifications to mobile routes
- `apps/mobile/src/providers/session.tsx`: revision counters: watchlist, alerts, notifications, reminder
- `apps/mobile/src/screens/game-detail.tsx`: WatchButtons and SetAlert panel
- `apps/mobile/src/screens/games.tsx`: Your watchlist section
- `apps/mobile/src/screens/prop-analyzer.tsx`: player WatchButton
- `apps/mobile/src/screens/settings.tsx`: notification preferences panel
- `apps/mobile/src/screens/tracker.tsx`: StakeReminderNotice

**Entry points**

- GET /v1/watchlist (optional ?kind=)
- POST /v1/watchlist
- GET /v1/watchlist/events
- DELETE /v1/watchlist/{item_id}
- GET /v1/alerts (optional ?state=)
- POST /v1/alerts
- POST /v1/alerts/evaluate
- PATCH /v1/alerts/{alert_id}
- DELETE /v1/alerts/{alert_id}
- GET /v1/notifications (?unread, limit, before) - also triggers lazy evaluation
- GET /v1/notifications/unread-count - also triggers lazy evaluation
- POST /v1/notifications/read-all
- POST /v1/notifications/{notification_id}/read
- DELETE /v1/notifications/{notification_id}
- GET /v1/me/notification-preferences
- PUT /v1/me/notification-preferences
- GET /v1/me/stake-reminder
- PUT /v1/me/stake-reminder
- Web: /app/alerts (inbox and rules); bell in /app layout header
- Web: /app/games/[id] (follow, Set an alert), /app/props/[playerId] (follow), /app (Your watchlist), /app/settings (switches, stake reminder)
- Web proxy: /api/ov/v1/... used by client components
- Mobile: /notifications and /notifications?tab=alerts in the (games) stack; bell in Games header
- Mobile: game detail (follow, Set an alert), prop analyzer (follow), Games (Your watchlist), Settings (switches)
- Script: services/api/scripts/evaluate_alerts.py [--dry-run]; run every 120 s by the worker in infrastructure/hostinger/compose.yaml
- Script: services/api/scripts/seed_demo.py seeds demo rules and notifications via seed.seed_demo_alerts

**Tests**

- `services/api/tests/test_alert_evaluator.py`: pure evaluator: thresholds, line moves, start window, finals, dedupe
- `services/api/tests/test_api_alerts.py`: alert routes, validation, limits, pause/resume/re-arm, ownership
- `services/api/tests/test_api_notifications.py`: notification routes, paging, preferences, stake reminder, lazy evaluation, evaluate_alerts.py script
- `services/api/tests/test_api_watchlist.py`: watchlist routes, idempotent add, events, ownership
- `services/api/tests/test_notification_copy.py`: banned phrases and copy rules over TEMPLATES
- `services/api/tests/test_migrations_seed_openapi.py`: migrations 0002/0003 up and down, seed, operation ids
- `services/api/tests/test_api_flags_entitlements.py`: alerts.max_active appears in entitlements output
- `services/api/tests/test_api_account.py`: export includes watchlist, alerts, notifications
- `services/api/tests/test_security.py`: cross-user access to these routes
- `apps/web/e2e/app.spec.ts`: watchlist flow and 'alerts and notifications' describe block
- `apps/web/e2e/community.spec.ts`: community notifications lose links with flag off; settings switches
- `apps/web/e2e/a11y.spec.ts`: /app/alerts in axe page list
- `apps/web/e2e/security.spec.ts`: /app/alerts in protected pages list
- `apps/mobile/src/components/alert-form.test.tsx`: form, suggestedThreshold, readThreshold, readMove
- `apps/mobile/src/components/alert-list.test.tsx`: rule list actions
- `apps/mobile/src/components/notification-list.test.tsx`: list, paging, read, delete
- `apps/mobile/src/components/notification-bell.test.tsx`: bell label and badge
- `apps/mobile/src/components/notification-settings.test.tsx`: switches and stake reminder
- `apps/mobile/src/components/watch-button.test.tsx`: follow toggle
- `apps/mobile/src/screens/notifications.test.tsx`: inbox screen tabs and signed-out state
- `apps/mobile/src/screens/game-detail.test.tsx`: follow buttons and Set an alert panel
- `apps/mobile/src/screens/settings.test.tsx`: notifications panel
- `apps/mobile/src/utils/routes.test.ts`: notification href to mobile route mapping
- `apps/mobile/src/api/client.test.ts`: client calls incl. watchlist/alerts/notifications
- No web unit tests exist for alert-form, alerts-panels, watch-button or notification-settings (e2e only)

**Data model**

watchlist_items (migration 0002): id, user_id FK cascade, kind team|player|event, ref_id (provider id, not FK), label, league, created_at; unique (user_id, kind, ref_id). alert_rules (0003): id, user_id, kind, state active|triggered|expired|paused, event_id, team_id, market, outcome_key, line, threshold_decimal (decimal odds), min_move, baseline_line, minutes_before, fired_event_ids JSON, arm_count, label, league, created_at, updated_at, triggered_at; index (user_id, state). notifications (0003): id, user_id, kind, title, body, href, data JSON, rule_id (plain id, no FK), dedupe_key, created_at, read_at; unique (user_id, dedupe_key), index (user_id, created_at). notification_preferences (0003): user_id PK, in_app_disabled JSON list, updated_at. stake_reminders (0003): user_id PK, weekly_stake_threshold, last_reminded_week, updated_at. Not stored: evaluation throttle (process memory), prices/lines at fire time beyond the notification's text and data JSON, watchlist events (computed from provider on request).

**Flags and plan checks today**

No feature flag and no plan check gates watchlist, alerts or notifications; all routes need only an authenticated user (CurrentUserDep). Limits are hard-coded constants: 200 watchlist items, 100 active and 500 total alert rules, 500 notifications kept. entitlements/catalog.py declares "alerts.max_active" (same limit 100 for free and premium) but alerts/router.py never calls require_entitlement; it compares against MAX_ACTIVE_ALERTS directly, so premium_gating would change nothing here. The `community` flag only affects this part indirectly: community kinds are created only while it is on, and web/mobile hide community switches and strip /app/community links when it is off.

**Backlog items that will touch it**

- **P0.1**: alerts.service.gather_inputs reads live Board.best_price/consensus_outcome_line and line_move stores only baseline_line; the archive becomes the source for baselines and for what a fired alert saw.
- **P0.2**: Notification rows carry price/line numbers only as formatted text plus a loose data JSON; drafts in notifications/templates.py need method id, version, inputs and as-of time attached.
- **P0.3**: alerts/router.py _check_room must resolve alerts.max_active through the entitlement service instead of the MAX_ACTIVE_ALERTS constant, and watchlist/notification caps likely follow.
- **P0.4**: notification_preferences and stake_reminders are per-user settings that the profile settings model must absorb or sit beside, and templates.american hard-codes American odds where odds format becomes a setting.
- **P0.6**: notifications.service.notify is the single sender to call the suppression hook first, and BANNED_PHRASES in tests/test_notification_copy.py is the existing copy guard to generalise.
- **F04**: Today cards for watchlist changes and threshold crossings reuse watchlist.service.watched_events and the notifications/alert_rules tables, replacing the Your watchlist section on web /app and mobile Games.
- **F06**: Dollar View restates every price, including thresholds and best-now prices in alert forms, rule summaries and price_alert notification text.
- **F07**: Every alert needs a 'why is this here' link, so NotificationOut/notification data must expose rule and inputs and both notification lists must render the link.
- **F08**: Clear Mode's polite, throttled live announcements apply to the bell unread count and notification lists on web layout.tsx and mobile notification-bell/notification-list.
- **F11**: Quiet Mode must stop alerts on every channel: notify(), evaluate_user_alerts, evaluate_if_due and scripts/evaluate_alerts.py need a quiet check, and the bell and alert forms must hide.
- **F14**: Onboarding proposes a watchlist to confirm, which will bulk-create watchlist_items through the watchlist add logic (label capture, 200 cap, idempotency).
- **F16**: price_at_least uses Board.best_price across all books; state and books-held filtering must apply to alert evaluation and to the best-now prices shown in both alert forms.
- **F17**: Lineup and line-move notes extend the line_move alert/notification path (new kinds or markers in templates and NotificationKind) for watched players and events.
- **F23**: Plan Mode's weekly budget overlaps the stake reminder (week_start, staked_this_week, check_stake_reminder in notifications/service.py) and starts Quiet Mode, which suppresses alerts.

**What a builder would get wrong by assuming**

1. "No background worker" is stated in alerts/throttle.py, the POST /v1/alerts description, web and mobile copy ("checked when you open OddVex"), yet infrastructure/hostinger/compose.yaml runs scripts/evaluate_alerts.py every 120 s in a worker container. Locally evaluation is lazy only. 2. GET /v1/notifications and GET /v1/notifications/unread-count have write side effects (they evaluate rules and commit). The web bell in app/app/layout.tsx therefore triggers evaluation on every app page render. 3. EvaluationThrottle is per-process memory, not shared across API workers and unknown to the script; correctness relies on the (user_id, dedupe_key) unique constraint, not on the throttle. 4. alerts.max_active exists in the entitlement catalog but is not enforced; limits are constants. 5. Nothing about a fired alert is stored except the notification row; there is no price history or firing log beyond audit entries, and rule_id on notifications is a plain string with no FK (rules can be deleted, notifications stay). 6. A disabled notification kind still lets the rule fire and move to triggered; only the row is skipped. Preferences exist for the in_app channel only (disabled_kinds returns empty for any other channel). 7. Naming: rule kind is price_at_least but its notification kind is price_alert; the JSON column fired_event_ids actually means "handled" (includes games already final at arm time); notifications/ also owns the stake reminder (/v1/me/stake-reminder), which is fed by bets and sync, not alerts. 8. Event-scoped rules are one-shot (triggered), team-scoped rules stay active and fire per game. Team alerts can be created only from mobile (game_start, fixed 60 minutes); the web form sends event_id only, and no client creates team game_final rules or watch-based alerts. The watchlist and alerts are unconnected: following something creates no alert. 9. Logic duplicated between web and mobile and already divergent: threshold suggestion (web suggest: -105 gives +100; mobile suggestedThreshold: -105 gives +105, -110 gives -100), threshold validation, kind labels (KIND_LABEL vs NOTIFICATION_KIND_LABELS), preference switch lists, minutes options, watchId helper. 10. Notification href values are web routes (/app/games/{id}?market=); mobile translates them in utils/routes.ts, so any new href shape needs a mapping there. 11. Notification copy is fixed at creation in American odds with English text; changing odds format or wording later does not affect stored rows. 12. Watchlist and rule labels are captured at creation; ref_id/event_id/team_id are provider ids, so items go `available: false` when the provider drops them. 13. The no-store Cache-Control prefix list in middleware.py covers /v1/watchlist and /v1/me but not /v1/alerts or /v1/notifications. 14. Web has no unit tests for this part; coverage is Playwright e2e only, while mobile has per-component tests.

## 8. A rule-based assistant that answers from the app's own data and math

A stateless, rule-based assistant exists end to end: POST /v1/assistant/query runs a regex/keyword intent router (engine.py) over eight intents (compare_odds, line_movement, player_trend, bet_summary, explain_ev, explain_no_vig, help, fallback), each "tool" calling the shared Board read models, the quant library or bets.service.summarize, then a TemplateExplainer turns the facts dict into prose with sources, suggestion links (web /app/... hrefs) and a disclaimer. No language model is connected and nothing is stored. Web (/app/assistant) and mobile (/assistant screen in the Games stack) are thin single-turn chat UIs over that one endpoint; mobile maps the web hrefs to its own screens with appRoute.

**API (`services/api`)**

- `services/api/src/oddvex_api/assistant/engine.py`: Assistant class: regex intent router, entity matching, 8 data tools, DISCLAIMER/REPLAY_DISCLAIMER, ToolResult
- `services/api/src/oddvex_api/assistant/explainer.py`: Explainer protocol and TemplateExplainer (one _<intent> template per intent)
- `services/api/src/oddvex_api/assistant/router.py`: POST /assistant/query, optional auth, rate_limit("assistant")
- `services/api/src/oddvex_api/assistant/schemas.py`: AssistantIntent literal, request (message 1-500 chars), response, source and suggestion models
- `services/api/src/oddvex_api/assistant/__init__.py`: exports Assistant, Explainer, TemplateExplainer, ToolResult
- `services/api/src/oddvex_api/main.py`: mounts assistant router under /v1 (line 253), OpenAPI tag
- `services/api/src/oddvex_api/board.py`: Board read models the tools call: event_odds, line_history, player_props, book_ref, provider
- `services/api/src/oddvex_api/bets/service.py`: summarize() used by bet_summary intent
- `services/api/src/oddvex_api/ratelimit.py`: rate_limit(bucket) per-IP sliding window
- `services/api/src/oddvex_api/config.py`: rate_limit_assistant_per_minute = 20 (ODDVEX_RATE_LIMIT_ASSISTANT_PER_MINUTE)
- `services/api/src/oddvex_api/deps.py`: BoardDep, DbDep, OptionalUserDep
- `services/api/src/oddvex_api/db/models.py`: User and Bet models read by bet_summary
- `services/api/openapi.json`: assistant_query operation and Assistant* schemas
- `packages/types/src/api.d.ts`: generated AssistantResponse etc. (outside services/api, consumed by web and mobile)

**Web (`apps/web`)**

- `apps/web/src/app/app/assistant/page.tsx`: server page titled OddVex AI; seeds example prompts from /v1/events and /v1/props
- `apps/web/src/components/app/assistant-chat.tsx`: client chat: turns in useState, posts to /v1/assistant/query, renders suggestions, sources, disclaimer, 429 copy
- `apps/web/src/lib/types.ts`: AssistantReply alias of Schemas AssistantResponse
- `apps/web/src/lib/client-api.ts`: clientApi and ClientApiError used by the chat
- `apps/web/src/lib/format.ts`: formatAge for source freshness
- `apps/web/src/app/api/ov/[...path]/route.ts`: proxy allow-list includes v1/assistant
- `apps/web/src/lib/site.ts`: app nav entry /app/assistant labelled OddVex AI
- `apps/web/src/app/app/page.tsx`: dashboard button linking to /app/assistant
- `apps/web/src/app/(marketing)/ai/page.tsx`: marketing page with CTA to /app/assistant
- `apps/web/src/app/(marketing)/pricing/page.tsx`: lists OddVex AI as free; mentions future higher assistant limits

**Mobile (`apps/mobile`)**

- `apps/mobile/src/screens/assistant.tsx`: AssistantScreen, AssistantAnswer, examplePrompts, sourcesText, suggestionRoute, ASSISTANT_INTRO
- `apps/mobile/src/app/(tabs)/(games)/assistant.tsx`: route file rendering AssistantScreen
- `apps/mobile/src/app/(tabs)/(games)/_layout.tsx`: Stack.Screen name assistant, title OddVex AI
- `apps/mobile/src/api/client.ts`: askAssistant(message), auth optional
- `apps/mobile/src/api/types.ts`: AssistantReply alias
- `apps/mobile/src/utils/routes.ts`: appRoute: maps web /app/... hrefs to mobile screens (shared with notifications)
- `apps/mobile/src/utils/format.ts`: formatAge
- `apps/mobile/src/screens/games.tsx`: Ask a question button pushes /assistant
- `apps/mobile/src/screens/settings.tsx`: Ask OddVex AI button pushes /assistant

**Entry points**

- POST /v1/assistant/query - body {message}, optional bearer token, per-IP rate limit
- Web: /app/assistant (page), calls go through the /api/ov/v1/assistant/query proxy route
- Web marketing: /ai links to /app/assistant
- Mobile: /assistant screen in the Games tab stack, opened from Games and Settings
- Scripts: none specific (services/api/scripts/export_openapi.py regenerates the schema the types come from)

**Tests**

- `services/api/tests/test_api_assistant.py`: every intent, parity with odds and props endpoints, auth handling, validation, no-invented-numbers check, pluggable Explainer
- `services/api/tests/test_platform.py`: assistant rate limit bucket is separate from auth (around lines 171-182)
- `services/api/tests/test_replay_build_and_api.py`: test_assistant_says_replay_not_synthetic (disclaimer and help text in replay mode)
- `services/api/tests/test_security.py`: /v1/assistant in public prefixes; hostile-string post to the endpoint
- `services/api/tests/test_migrations_seed_openapi.py`: operation id assistant_query pinned for POST /v1/assistant/query
- `apps/mobile/src/screens/assistant.test.tsx`: suggestionRoute, sourcesText, examplePrompts, AssistantAnswer, AssistantScreen incl. 429 message
- `apps/mobile/src/api/client.test.ts`: askAssistant sends the token only when one exists
- `apps/mobile/src/utils/routes.test.ts`: appRoute mapping
- `apps/web/e2e/app.spec.ts`: assistant answers from data, cites sources, declines unknowable question (line 110); page in route sweep
- `apps/web/e2e/a11y.spec.ts`: /app/assistant in the accessibility route list

**Data model**

none: computed on request. No assistant tables or migrations; no conversation, question or answer is persisted. The only DB read is the bet_summary intent selecting from bets (Bet) for the authenticated users row (User), in services/api/src/oddvex_api/db/models.py. All other intents read the in-memory Board/provider and the quant library.

**Flags and plan checks today**

No feature flag and no plan check. The endpoint is public with optional auth (an invalid token gets 401; no token is anonymous); only the bet_summary intent needs a logged-in user and otherwise answers "not_authenticated". The only limit is the per-IP "assistant" rate-limit bucket (rate_limit_assistant_per_minute, default 20, off when rate_limit_enabled is false). The pricing page lists OddVex AI under Free and says a future Premium would have "higher assistant limits", but nothing implements a per-plan limit. Mobile README notes the assistant predates flags and never asks for one.

**Backlog items that will touch it**

- **P0.2**: ToolResult facts and AssistantSourceOut (label, as_of, data_mode) are the assistant's ad hoc provenance and would need to carry method id, version and inputs for the numbers it quotes.
- **P0.3**: The pricing page promises higher assistant limits for Premium, so the router's flat per-IP rate_limit("assistant") is where a per-plan limit from the entitlement resolver would go.
- **P0.4**: Templates hard-code American plus decimal prices and unit-less stakes in explainer.py, so the profile's odds format and unit size must be passed into the explainer.
- **P0.6**: TemplateExplainer strings, DISCLAIMER and the duplicated web/mobile chat copy are user-facing strings the copy guard will scan, and compare_odds/line_movement/player_trend surface current markets so must call the suppression hook first.
- **F01**: Check My Bet's leg-to-market matching needs the same team, player and market-word matching plus American-price regex that engine.py already has, so those helpers should be extracted and shared.
- **F07**: Tap to Explain can reuse the Explainer protocol and the explain_ev/explain_no_vig templates with formula, inputs and sources, rather than writing a second explanation layer.
- **F11**: Quiet Mode must stop the compare_odds, line_movement and player_trend intents (and their example prompts on web and mobile) from showing current markets.
- **F13**: Plain-English market search can reuse engine.py's _find_team, _find_players, _MARKET_WORDS and the ambiguous_player choose-one response, which today live privately inside the Assistant class.
- **F16**: compare_odds picks the best price across all books on the board, so it needs the state and books-held filter to avoid quoting a book the user cannot use.

**What a builder would get wrong by assuming**

1) Branded "OddVex AI" in web and mobile, but there is no model: it is regexes and string templates, and tests assert answers contain only numbers the tools produced. 2) Fully stateless: no conversation history is sent or stored; each request is a single message, and chat turns live only in component state on each client. 3) Starting hint paths are off: web lives under apps/web/src/app/app/assistant and apps/web/src/components/app (note the src/ prefix); the mobile route file is apps/mobile/src/app/(tabs)/(games)/assistant.tsx. 4) Suggestion hrefs are web routes (/app/...) hard-coded in the API; mobile translates them with appRoute in utils/routes.ts and silently drops any it cannot map, so a new web route needs a mobile mapping. 5) Chat logic, example-prompt seeding, the sources line and the 429 message are duplicated between assistant-chat.tsx/page.tsx (web) and screens/assistant.tsx (mobile). 6) Entity and market matching (_find_team, _find_players, _MARKET_WORDS) is private to the Assistant class, not a shared search module; a last name matching several players returns ambiguous_player. 7) Routing is first-match-wins in a fixed order: bet-summary, EV, no-vig, then any player name, then team/movement; a message with a player name always becomes player_trend, and line_movement only ever uses the moneyline. 8) bet_summary loads all of the user's bets and calls summarize() per request; source as_of for it is wall-clock now, while other sources use board.now. 9) Rate limiting is per IP, not per user or plan, and disabled when rate_limit_enabled is false. 10) tests/test_security.py line 536 posts {"query": ...} instead of {"message": ...}, so that hostile-string check always gets 422 and never exercises the engine. 11) The disclaimer switches on provider.data_mode (synthetic vs replay) and states all data is synthetic; a live provider would need a third wording.

## 9. Community features (built, switched off)

A complete opt-in community (handle-only profiles, single-leg picks with a server-snapshotted best price, likes, comments, follows, blocks, reports, admin moderation, leaderboard) is built across API, web and mobile and is off behind two DB-stored flags, `community` and `community_leaderboard`. Picks are stored in seven `community_*` tables, graded lazily on community reads (or by scripts/grade_picks.py) with quant.grade_leg, and every record/leaderboard number is computed on request by quant.record.pick_record at a flat 1-unit stake. Web gates via proxy + requireFlag + API 404; mobile gates via CommunityGate and asks the API for nothing while off.

**API (`services/api`)**

- `services/api/src/oddvex_api/community/service.py`: all domain logic: visibility, build_pick, grading, records, leaderboard, moderation, export
- `services/api/src/oddvex_api/community/router.py`: 23 member routes under /v1/community, flag dependency, rate limits
- `services/api/src/oddvex_api/community/admin_router.py`: 3 moderation routes under /v1/admin/community (admin role)
- `services/api/src/oddvex_api/community/schemas.py`: Pydantic in/out models and text length limits
- `services/api/src/oddvex_api/community/content_rules.py`: pure banned-phrase/link/contact filter for user text
- `services/api/src/oddvex_api/community/guidelines.py`: guidelines text, version, record and leaderboard caveats
- `services/api/src/oddvex_api/community/seed.py`: fictional demo profiles, picks, comments (demo_bettor)
- `services/api/src/oddvex_api/quant/record.py`: pick_record, flat-stake ROI, Wilson interval, SMALL_SAMPLE=30
- `services/api/src/oddvex_api/quant/grading.py`: grade_leg shared with tracker auto-settlement
- `services/api/src/oddvex_api/db/models.py`: CommunityProfile/Pick/Comment/Follow/Like/Block/Report (lines ~422-560)
- `services/api/alembic/versions/0005_community_and_search_keys.py`: creates the seven community tables
- `services/api/src/oddvex_api/flags/catalog.py`: community and community_leaderboard specs, both default False
- `services/api/src/oddvex_api/main.py`: mounts both routers, community limiters and grade throttle on app.state
- `services/api/src/oddvex_api/config.py`: community_*_per_day/hour limits, community_grade_min_seconds
- `services/api/src/oddvex_api/notifications/templates.py`: pick_graded, pick_comment, follow templates and /app/community hrefs
- `services/api/src/oddvex_api/notifications/schemas.py`: community notification kinds and preferences
- `services/api/src/oddvex_api/account/router.py`: /v1/me/export includes community via service.export_out
- `services/api/src/oddvex_api/account/schemas.py`: export schema embeds CommunityExportOut
- `services/api/src/oddvex_api/seed.py`: with_community turns both flags on then seeds
- `services/api/src/oddvex_api/api/admin.py`: flag toggle docs, shared account suspension used by moderation
- `services/api/scripts/grade_picks.py`: batch grader for a future cron
- `services/api/scripts/seed_demo.py`: --with-community option

**Web (`apps/web`)**

- `apps/web/src/app/app/community/page.tsx`: feed (following/everyone) or first-visit guidelines + profile form
- `apps/web/src/app/app/community/picks/[id]/page.tsx`: pick detail with comments
- `apps/web/src/app/app/community/profiles/[handle]/page.tsx`: profile, record, picks
- `apps/web/src/app/app/community/leaderboard/page.tsx`: leaderboard, needs second flag
- `apps/web/src/app/app/community/settings/page.tsx`: edit own profile, blocks
- `apps/web/src/app/app/community/guidelines/page.tsx`: guidelines from API
- `apps/web/src/app/app/admin/community/page.tsx`: moderation queue and overview
- `apps/web/src/components/app/community/actions.tsx`: report, follow, block, delete pick, comments (client)
- `apps/web/src/components/app/community/chrome.tsx`: header, SignedOut, Guidelines, RecordPanel, intervalText
- `apps/web/src/components/app/community/pick-card.tsx`: PickCard, LikeButton, paginated PickList
- `apps/web/src/components/app/community/profile-form.tsx`: create/edit profile
- `apps/web/src/components/app/community/share-pick.tsx`: share-a-pick form on game page
- `apps/web/src/components/app/community/text-area.tsx`: counted plain-text area
- `apps/web/src/lib/community.ts`: server-only communityContext (requireFlag), getMyProfile, hrefs
- `apps/web/src/lib/community-copy.ts`: types, limits, error copy, status labels, report reasons
- `apps/web/src/lib/site.ts`: nav entry and flagged route table for the proxy
- `apps/web/src/proxy.ts`: real 404 for flagged paths while flag off
- `apps/web/src/lib/admin-actions.ts`: resolve report and admin comment removal server actions
- `apps/web/src/lib/admin.ts`: review warning for community* flags
- `apps/web/src/app/app/games/[id]/page.tsx`: Share a pick panel when flag on and game upcoming
- `apps/web/src/app/api/ov/[...path]/route.ts`: browser proxy allowlist includes community
- `apps/web/src/components/app/alerts-panels.tsx`: drops community notification links while flag off
- `apps/web/src/components/app/notification-settings.tsx`: community notification switches when flag on
- `apps/web/src/components/app/admin-controls.tsx`: Community admin tab when flag on
- `apps/web/src/app/app/admin/layout.tsx`: passes community flag to AdminTabs
- `apps/web/src/app/app/settings/page.tsx`: deletion copy and prefs mention community when on
- `apps/web/src/components/app/nav.tsx`: community nav icon
- `apps/web/src/app/(marketing)/features/page.tsx`: lists Community as built, not live

**Mobile (`apps/mobile`)**

- `apps/mobile/src/screens/community-feed.tsx`: feed screen
- `apps/mobile/src/screens/community-pick.tsx`: pick detail, comments, like, report, delete
- `apps/mobile/src/screens/community-profile.tsx`: profile by handle, record, follow/block
- `apps/mobile/src/screens/community-profile-edit.tsx`: own profile edit
- `apps/mobile/src/screens/community-leaderboard.tsx`: leaderboard, second flag
- `apps/mobile/src/screens/community-guidelines.tsx`: guidelines, no sign-in
- `apps/mobile/src/app/(tabs)/(games)/community/index.tsx`: route for feed
- `apps/mobile/src/app/(tabs)/(games)/community/picks/[id].tsx`: route for pick
- `apps/mobile/src/app/(tabs)/(games)/community/profiles/[handle].tsx`: route for profile
- `apps/mobile/src/app/(tabs)/(games)/community/profile.tsx`: route for own profile
- `apps/mobile/src/app/(tabs)/(games)/community/leaderboard.tsx`: route for leaderboard
- `apps/mobile/src/app/(tabs)/(games)/community/guidelines.tsx`: route for guidelines
- `apps/mobile/src/app/(tabs)/(games)/_layout.tsx`: registers the six community stack screens
- `apps/mobile/src/components/community-gate.tsx`: flag and sign-in gate for every screen
- `apps/mobile/src/components/community-entry.tsx`: entry card on Games screen
- `apps/mobile/src/components/community-record.tsx`: record display
- `apps/mobile/src/components/community-copy.ts`: limits, error copy, labels (separate from web)
- `apps/mobile/src/components/pick-card.tsx`: pick card
- `apps/mobile/src/components/share-pick.tsx`: share a pick from game detail
- `apps/mobile/src/components/profile-form.tsx`: community profile form (generic name)
- `apps/mobile/src/components/guidelines.tsx`: community guidelines block (generic name)
- `apps/mobile/src/components/report-form.tsx`: community report form (generic name)
- `apps/mobile/src/hooks/use-community.ts`: useMyProfile
- `apps/mobile/src/api/client.ts`: community client functions (line ~534 onward)
- `apps/mobile/src/api/types.ts`: community type aliases
- `apps/mobile/src/utils/routes.ts`: maps /app/community/... hrefs to mobile routes
- `apps/mobile/src/providers/flags.tsx`: FlagKey includes both community flags
- `apps/mobile/src/providers/session.tsx`: 'community' change topic for reloads
- `apps/mobile/src/screens/games.tsx`: shows CommunityEntry when flag on
- `apps/mobile/src/screens/game-detail.tsx`: renders SharePick
- `apps/mobile/src/components/notification-settings.tsx`: community switches when flag on
- `apps/mobile/src/test/community.tsx`: test helper

**Entry points**

- GET /v1/community/guidelines
- PUT /v1/community/profile
- GET /v1/community/profile
- GET /v1/community/profiles/{handle}
- POST /v1/community/picks
- GET /v1/community/picks
- GET /v1/community/feed
- GET /v1/community/picks/{pick_id}
- DELETE /v1/community/picks/{pick_id}
- PUT /v1/community/picks/{pick_id}/like
- DELETE /v1/community/picks/{pick_id}/like
- POST /v1/community/picks/{pick_id}/comments
- GET /v1/community/picks/{pick_id}/comments
- DELETE /v1/community/comments/{comment_id}
- POST /v1/community/follows/{handle}
- DELETE /v1/community/follows/{handle}
- GET /v1/community/following
- GET /v1/community/followers
- PUT /v1/community/blocks/{handle}
- DELETE /v1/community/blocks/{handle}
- GET /v1/community/blocks
- POST /v1/community/reports
- GET /v1/community/leaderboard (also needs community_leaderboard)
- GET /v1/admin/community/overview
- GET /v1/admin/community/reports
- POST /v1/admin/community/reports/{report_id}/resolve
- GET /v1/me/export (includes community block)
- Web: /app/community
- Web: /app/community/picks/[id]
- Web: /app/community/profiles/[handle]
- Web: /app/community/leaderboard
- Web: /app/community/settings
- Web: /app/community/guidelines
- Web: /app/admin/community
- Web: /app/games/[id] (Share a pick panel)
- Mobile route: /community (feed)
- Mobile route: /community/picks/[id]
- Mobile route: /community/profiles/[handle]
- Mobile route: /community/profile
- Mobile route: /community/leaderboard
- Mobile route: /community/guidelines
- Mobile: Games screen CommunityEntry and game detail SharePick
- Script: services/api/scripts/grade_picks.py [--dry-run]
- Script: services/api/scripts/seed_demo.py --with-community

**Tests**

- `services/api/tests/test_api_community.py`: member routes: profiles, picks, feed, likes, comments, follows, blocks, grading, leaderboard
- `services/api/tests/test_api_community_moderation.py`: reports, admin queue, resolve actions
- `services/api/tests/test_community_content_rules.py`: each content rule, true positive and near miss
- `services/api/tests/community_support.py`: shared helpers for the community tests
- `services/api/tests/quant/test_record.py`: pick_record, flat-stake ROI, interval
- `services/api/tests/quant/test_grading.py`: grade_leg
- `services/api/tests/test_api_flags_entitlements.py`: flag behaviour incl. community references
- `services/api/tests/test_api_account.py`: export/deletion incl. community data
- `services/api/tests/test_notification_copy.py`: community notification templates
- `services/api/tests/test_migrations_seed_openapi.py`: migration 0005, seed, openapi
- `services/api/tests/test_security.py, test_api_review_followups.py, test_api_admin_manage.py`: reference community (not opened in detail)
- `apps/web/e2e/community.spec.ts`: full flow flag off/on, profile, pick, follow, like, comment, report, block, leaderboard
- `apps/web/e2e/admin.spec.ts`: community flags stay off, review warning
- `apps/web/e2e/a11y.spec.ts`: turns community on for a11y pass
- `apps/web/src/lib/community-copy.test.ts`: copy helpers, banned phrases
- `apps/web/src/lib/site.test.ts`: flagged route table
- `apps/mobile/src/screens/community-feed.test.tsx`: feed screen
- `apps/mobile/src/screens/community-pick.test.tsx`: pick screen
- `apps/mobile/src/screens/community-profile.test.tsx`: profile screen
- `apps/mobile/src/screens/community-leaderboard.test.tsx`: leaderboard screen
- `apps/mobile/src/components/share-pick.test.tsx`: share pick
- `apps/mobile/src/components/community-copy.test.ts`: copy, banned phrases and decoration
- `apps/mobile/src/components/profile-form.test.tsx`: profile form
- `apps/mobile/src/utils/routes.test.ts`: href to route mapping
- `apps/mobile/src/providers/flags.test.tsx, components/notification-list.test.tsx, components/notification-settings.test.tsx, screens/settings.test.tsx`: flag-dependent community bits
- Note: no test was run in this read-only mapping; no test file found for scripts/grade_picks.py by name

**Data model**

Migration 0005_community_and_search_keys.py (also adds unrelated users.search_key, bets.sportsbook_key). Tables: community_profiles (PK user_id, unique handle, bio, is_public, moderation_status); community_picks (id, user_id, event_id, league, event_label, selection, event_start_time, market, outcome_key, line, price_decimal, sportsbook_key/name, analysis, posted_at, status pending/graded/void, result, graded_at, home_score, away_score, moderation_status; unique user_id+event_id+market); community_comments (pick_id, user_id, body, moderation_status); community_follows (follower_id, followed_id); community_likes (pick_id, user_id); community_blocks (blocker_id, blocked_id); community_reports (reporter, target_type/id, target_user_id, reason, details, status, resolution fields). All FK to users with ON DELETE CASCADE. Also writes audit entries and in-app notifications; flag state lives in the flags tables. Records and leaderboard are not stored: computed on request.

**Flags and plan checks today**

Flags `community` and `community_leaderboard` (flags/catalog.py, both default False, toggled per database by an admin; admin UI shows a legal + responsible-gambling review warning and the constitution requires Founder approval). API: require_flag("community") on both routers gives 404 feature_disabled; leaderboard route adds require_flag("community_leaderboard"). Web: proxy.ts + lib/site.ts flagged routes + requireFlag in communityContext; nav, admin tab, share-pick panel, notification switches all conditional. Mobile: CommunityGate, useFlag in games.tsx and notification-settings. No plan or entitlement checks anywhere: every signed-in user is equal. Other gates: sign-in for all routes except guidelines; posting, commenting and following need a public, unmoderated profile (403 profile_required); admin role for /v1/admin/community; in-process rate limits (20 picks/day, 30 comments/h, 10 reports/h, 60 follows/h).

**Backlog items that will touch it**

- **P0.2**: Record and leaderboard numbers carry only a free-text FLAT_STAKE_METHOD string and are recomputed per request; provenance would add method id/version/inputs/as-of to CommunityRecordOut and LeaderboardOut.
- **P0.3**: Community has no plan checks today; if F38 creator pages or posting become plan-gated, the entitlement dependency is added beside require_flag on the community routers.
- **P0.6**: The copy guard must cover community-copy.ts (web and mobile), guidelines.py and notification templates, replacing the per-app banned-phrase tests, and the suppression hook must be called before the notify calls in grade_due_picks and the comment/follow routes.
- **F07**: The record panels (web chrome.tsx RecordPanel, mobile community-record.tsx) and pick prices are displayed numbers that would need the explain affordance, fed by the method/caveat fields the API already returns.
- **F11**: Quiet Mode has to hide the feed, share-pick panels and leaderboard (current prices on upcoming events) and stop the pick_graded, pick_comment and follow notifications created in community/service.py and router.py.
- **F19**: Directly reuses quant/record.py (pick_record, Wilson interval, SMALL_SAMPLE, sample_note wording) that the community record is built on, applied to the user's own bets.
- **F38**: Reuses community_profiles (handle, visibility, moderation, blocks, reports), record_out/RecordPanel and the profile pages, but must swap the record source from community_picks to synced bets and add a signed-out public route, which does not exist today.

**What a builder would get wrong by assuming**

1) "Verified" (VERIFIED_NOTE) means a pick timestamped before the game and auto-graded; picks are not bets: no stake, no link to the bets or sync tables. F38 wants records "only from synced bets", so the existing record source cannot be reused as is. 2) Nothing is public: every route except guidelines needs sign-in, and the web pages live under /app. 3) Records and the leaderboard are computed on every request and never stored; the leaderboard runs one query per eligible user. Moderator-hidden picks still count in the record; void picks do not. 4) No background worker: grading runs lazily when someone reads the feed, picks or leaderboard, throttled by an in-process EvaluationThrottle (15 s default); scripts/grade_picks.py exists but nothing schedules it, and it runs even with the flag off. Rate limiters are also in process memory, so neither survives multiple workers. 5) The client never sends a price: build_pick takes Board.best_price and snapshots price, book, labels into the row; one pick per user per event per market; single-leg only; no deletion after start. 6) Leaderboard ranks by Wilson lower bound, not ROI, minimum 30 graded picks, windows 30d/90d/all. 7) Logic/copy duplicated: text limits and handle rules live in schemas.py, web lib/community-copy.ts and mobile components/community-copy.ts; error-message mapping is written separately per app with different export names; banned-phrase checks are separate tests per app plus content_rules.py for user text. 8) Misleading names: mobile profile-form.tsx, guidelines.tsx and report-form.tsx are community-only despite generic names; mobile "community/profile" equals web "/app/community/settings"; mobile community is a stack inside the Games tab, not a tab; mobile has no moderation UI. 9) Flags are per-database rows, not env config; seed_demo.py --with-community turns both on for everyone using that database. 10) Community reaches outside its folder: account export/deletion, notification kinds and preferences, admin suspension, the web /api/ov allowlist regex. 11) Other users are identified by handle only by design (no user id, email, name or plan in any schema); a creator page that needs plan or tracker data breaks that stated rule.

## 10. Admin tools, feature flags, staking-limit reminders

Admin tools are a role-gated API router (/v1/admin/*, role synced from the ODDVEX_ADMIN_EMAILS allowlist on every token use) with a web-only console at /app/admin (overview, users, flags, audit, outbox, community moderation); every change and most reads write to the append-only audit_log table. Feature flags are six global on/off switches defined in code (flags/catalog.py) with optional overrides in the feature_flags table, served publicly at GET /v1/flags and enforced by require_flag on routes, by the web proxy plus pages, and by a mobile FlagsProvider. Entitlements are a two-plan in-code catalog (free, premium) that gates nothing today, and the weekly staking reminder is a per-user threshold in stake_reminders that creates one in-app notification when a manual bet or sync import takes the UTC-week total across it.

**API (`services/api`)**

- `services/api/src/oddvex_api/api/admin.py`: all /v1/admin routes, audit_admin_read, suspend_user, Plan literal
- `services/api/src/oddvex_api/flags/catalog.py`: KNOWN_FLAGS: six FlagSpecs and defaults
- `services/api/src/oddvex_api/flags/service.py`: is_enabled, flag_states, set_flag, require_flag dependency
- `services/api/src/oddvex_api/flags/router.py`: public GET /v1/flags
- `services/api/src/oddvex_api/entitlements/catalog.py`: CATALOG feature -> plan -> Entitlement; PLANS free/premium
- `services/api/src/oddvex_api/entitlements/service.py`: entitlement, check_entitlement, require_entitlement (unused on routes)
- `services/api/src/oddvex_api/entitlements/router.py`: GET /v1/me/entitlements
- `services/api/src/oddvex_api/deps.py`: write_audit, sync_admin_role, require_admin/AdminDep
- `services/api/src/oddvex_api/notifications/service.py`: week_start, staked_this_week, stake_reminder_out, set_stake_threshold, check_stake_reminder
- `services/api/src/oddvex_api/notifications/router.py`: GET/PUT /v1/me/stake-reminder
- `services/api/src/oddvex_api/notifications/schemas.py`: StakeReminderUpdate, StakeReminderOut, stake_reminder kind
- `services/api/src/oddvex_api/notifications/templates.py`: stake_reminder draft, dedupe key per week
- `services/api/src/oddvex_api/bets/router.py`: calls check_stake_reminder after bet create; tracker_analytics flag
- `services/api/src/oddvex_api/sync/router.py`: calls check_stake_reminder after import
- `services/api/src/oddvex_api/account/router.py`: export includes stake_reminder
- `services/api/src/oddvex_api/community/admin_router.py`: /v1/admin/community moderation, behind community flag
- `services/api/src/oddvex_api/db/models.py`: StakeReminder, FeatureFlag, AuditLog, User.role/plan/status
- `services/api/src/oddvex_api/config.py`: admin_emails setting, admin_email_set
- `services/api/src/oddvex_api/main.py`: mounts admin, flags, entitlements routers under /v1
- `services/api/src/oddvex_api/seed.py`: seed_demo_admin, only when allowlisted
- `services/api/src/oddvex_api/api/data.py`: value_screen flag on the value route
- `services/api/src/oddvex_api/auth/router.py`: email_flows flag on verify/reset routes
- `services/api/alembic/versions/0001_initial_schema.py`: audit_log, users.role
- `services/api/alembic/versions/0003_alerts_notifications_stake_reminder.py`: stake_reminders table
- `services/api/alembic/versions/0004_flags_plans_admin_email.py`: feature_flags, users.plan, users.status, email_outbox

**Web (`apps/web`)**

- `apps/web/src/lib/admin.ts`: requireAdmin, adminGet, flagWarning copy
- `apps/web/src/lib/admin-actions.ts`: server actions: user suspend/unsuspend/plan, flag set, report resolve, comment delete
- `apps/web/src/lib/flags.ts`: getFlags (cached per render), flagOn, requireFlag
- `apps/web/src/lib/site.ts`: APP_NAV flag field, FLAGGED_PATHS, flagsForPath
- `apps/web/src/proxy.ts`: real 404 for non-admins on /app/admin and for flagged paths; own /v1/flags fetch
- `apps/web/src/components/app/admin-controls.tsx`: AdminTabs, UserActions, FlagToggle, ReportQueue, ReportActions
- `apps/web/src/app/app/admin/layout.tsx`: requireAdmin, header, tabs
- `apps/web/src/app/app/admin/page.tsx`: overview
- `apps/web/src/app/app/admin/users/page.tsx`: user search, suspend, plan
- `apps/web/src/app/app/admin/flags/page.tsx`: flag list and toggles
- `apps/web/src/app/app/admin/audit/page.tsx`: audit log with cursor and filters
- `apps/web/src/app/app/admin/outbox/page.tsx`: email outbox
- `apps/web/src/app/app/admin/community/page.tsx`: report queue, needs community flag
- `apps/web/src/app/api/ov/[...path]/route.ts`: browser bridge; deliberately excludes /v1/admin
- `apps/web/src/components/app/nav.tsx`: Admin link for admins; hides flagged nav items
- `apps/web/src/app/app/layout.tsx`: loads flags for the shell
- `apps/web/src/components/app/notification-settings.tsx`: StakeReminderForm, StakeReminderNotice
- `apps/web/src/app/app/settings/page.tsx`: reminder form, plan and preview line from entitlements
- `apps/web/src/app/app/tracker/page.tsx`: StakeReminderNotice; tracker_analytics link
- `apps/web/src/app/app/value/page.tsx`: requireFlag value_screen
- `apps/web/src/app/app/tracker/analytics/page.tsx`: requireFlag tracker_analytics

**Mobile (`apps/mobile`)**

- `apps/mobile/src/providers/flags.tsx`: FlagsProvider, useFlag, useFlags, FlagKey union (five keys)
- `apps/mobile/src/app/_layout.tsx`: mounts FlagsProvider inside the session provider
- `apps/mobile/src/api/client.ts`: getFlags, getEntitlements, getStakeReminder, setStakeReminder
- `apps/mobile/src/api/types.ts`: Flags, StakeReminder, Entitlements aliases
- `apps/mobile/src/hooks/use-notifications.ts`: useStakeReminder, refetches on bet revision
- `apps/mobile/src/components/notification-settings.tsx`: StakeReminderForm, StakeReminderNotice
- `apps/mobile/src/components/account-forms.tsx`: plan preview line from entitlements; email_flows flag
- `apps/mobile/src/screens/settings.tsx`: settings screen hosting reminder form and plan
- `apps/mobile/src/app/(tabs)/(settings)/settings.tsx`: route file for the settings screen
- `apps/mobile/src/screens/tracker.tsx`: StakeReminderNotice; tracker_analytics flag
- `apps/mobile/src/components/states.tsx`: reloads flags on a feature_disabled state
- `apps/mobile/src/components/community-gate.tsx`: community flag gate
- `apps/mobile/src/utils/routes.ts`: appRoute; /app/admin maps to null (no admin in the app)
- `apps/mobile/src/test/flags.tsx`: test helper providing a FlagsContext value

**Entry points**

- GET /v1/admin/overview
- GET /v1/admin/users
- POST /v1/admin/users/{user_id}/suspend
- POST /v1/admin/users/{user_id}/unsuspend
- PUT /v1/admin/users/{user_id}/plan
- GET /v1/admin/flags
- PUT /v1/admin/flags/{key}
- GET /v1/admin/audit
- GET /v1/admin/email-outbox
- GET /v1/admin/community/overview
- GET /v1/admin/community/reports
- POST /v1/admin/community/reports/{report_id}/resolve
- GET /v1/flags (public)
- GET /v1/me/entitlements
- GET /v1/me/stake-reminder
- PUT /v1/me/stake-reminder
- POST /v1/bets and the sync import route in sync/router.py - side effect: check_stake_reminder
- Web: /app/admin, /app/admin/users, /app/admin/flags, /app/admin/audit, /app/admin/outbox, /app/admin/community
- Web: /app/settings (reminder form, plan line), /app/tracker (reminder notice)
- Mobile: (tabs)/(settings)/settings screen; (tabs)/(tracker)/tracker screen notice; no admin screens
- Script: services/api/scripts/seed_demo.py - creates admin@oddvex.test only when ODDVEX_ADMIN_EMAILS lists it
- Env: ODDVEX_ADMIN_EMAILS (placeholder in infrastructure/hostinger/ops.sh; set in apps/web/e2e/start-api.sh)

**Tests**

- `services/api/tests/test_api_admin.py`: admin role required, token role claim not trusted, promotion on login
- `services/api/tests/test_api_admin_manage.py`: 401/403 on every admin route, users list, suspend, plan, flags, audit cursor, outbox
- `services/api/tests/test_api_flags_entitlements.py`: flag defaults, overrides, require_flag, entitlement resolution, no billing route
- `services/api/tests/test_api_notifications.py`: stake reminder validation, UTC week total, one reminder per week, sync import, export
- `services/api/tests/test_notification_copy.py`: stake reminder wording
- `services/api/tests/test_api_review_followups.py`: admin reads audited, role granted only after email confirmed, admin search
- `services/api/tests/test_security.py`: role/plan/status cannot be self-set, hostile admin search, moderation admin-only
- `services/api/tests/test_api_auth.py`: admin role comes from configuration, auth events audited
- `services/api/tests/test_email_flows.py`: email_flows flag off queues nothing
- `services/api/tests/test_api_community_moderation.py`: admin community report queue and resolve
- `services/api/tests/test_migrations_seed_openapi.py`: stake_reminders and other tables, operation ids, seed reminder
- `apps/web/e2e/admin.spec.ts`: 404 for non-admins, tabs, suspend/plan flow, audit paging, flag toggle hides feature
- `apps/web/e2e/app.spec.ts`: mentions the staking reminder in app flows
- `apps/web/e2e/helpers.ts`: adminToken, adminSignIn, flag setter helper (support, not a test)
- `apps/web/src/lib/site.test.ts`: flagsForPath
- `apps/mobile/src/providers/flags.test.tsx`: flagOn, provider load, reload and failure behaviour
- `apps/mobile/src/components/notification-settings.test.tsx`: StakeReminderForm and StakeReminderNotice
- `apps/mobile/src/screens/settings.test.tsx`: reminder section, plan and preview line, email_flows
- `apps/mobile/src/screens/tracker.test.tsx`: exceeded reminder notice
- `apps/mobile/src/api/client.test.ts`: stake reminder PUT bodies, /v1/flags, entitlements auth
- `apps/mobile/src/utils/routes.test.ts`: /app/admin has no mobile route

**Data model**

feature_flags (key PK, description, enabled, updated_at; migration 0004; a row is an override only, no row means the in-code default). audit_log (id, created_at, user_id not a FK, action, entity_type, entity_id, ip, request_id, details JSON; migration 0001; append-only). stake_reminders (user_id PK/FK, weekly_stake_threshold nullable, last_reminded_week, updated_at; migration 0003). users.role (0001), users.plan and users.status (0004). Admin outbox reads email_outbox (0004). Entitlements have no table: computed on request from entitlements/catalog.py plus users.plan and the premium_gating flag. staked_this_week and exceeded are computed on request from bets, not stored.

**Flags and plan checks today**

Known flags (flags/catalog.py): community (off), community_leaderboard (off), value_screen (on), tracker_analytics (on), email_flows (on; off in production), premium_gating (off). Admin routes are gated by role only (AdminDep; role follows ODDVEX_ADMIN_EMAILS and, while email_flows is on, a verified email); /v1/admin/community additionally needs the community flag. The stake reminder and /v1/me/entitlements need only a signed-in user, no flag or plan. Plan checks: none enforced. require_entitlement is used on no route, premium_gating is off, and the catalog gives free and premium identical entitlements (alerts.max_active, value_screen, tracker_analytics, odds_history_hours 48), so /v1/me/entitlements reports preview=true. A plan changes only through PUT /v1/admin/users/{id}/plan.

**Backlog items that will touch it**

- **P0.3**: Replaces the two-plan catalog and resolver in entitlements/ (and the Plan literal duplicated in api/admin.py, the admin plan route and the web plan selector) with free, premium, pro, pass and b2b resolution.
- **P0.4**: Changes the web and mobile settings screens that host the staking reminder form and the plan/preview line, and should absorb the plan state now read separately from /v1/me/entitlements.
- **P0.6**: The suppression hook must be called on the check_stake_reminder to notify path, and the copy guard overlaps the existing stake-reminder wording test in test_notification_copy.py.
- **F05**: Adds the tax_estimate flag (default off) to flags/catalog.py and a one-time unlock entitlement that the current per-plan catalog cannot express.
- **F11**: Must decide whether the staking reminder notification is stopped during a break, since it is sent through the same notify call as alerts from bets/router.py and sync/router.py.
- **F20**: Adds a second flag for in-play checks to KNOWN_FLAGS and a one-free-check allowance that is the first real use of an entitlement limit.
- **F23**: Reuses week_start and staked_this_week from notifications/service.py for the weekly budget, and should extend or replace the stake_reminders threshold rather than add a second weekly total.
- **F24**: Needs dated pass and pause entitlements where today there is one users.plan string set only by the admin plan route, so entitlements/service.py and admin_set_user_plan change.
- **F26**: Adds a stage 2 flag to flags/catalog.py that an admin enables from /app/admin/flags, with a flagWarning entry for the scorecard precondition.
- **F30**: Adds a flag whose off state must remove the link from the response, using is_enabled in a serializer rather than require_flag on a route.
- **F39**: Reuses write_audit and the audit_log table for the required log of every access to a shared report.
- **F40**: First of the Phase 4 items built behind a flag: adds a FlagSpec, a web FLAGGED_PATHS entry and a mobile FlagKey member (the same pattern applies to F41 to F43).
- **F42**: Needs a per-server b2b entitlement check, which the user-plan-only check_entitlement cannot do today.
- **F44**: Done-when says the report is visible in admin, so it adds a route to api/admin.py and a tab and page under apps/web/src/app/app/admin.

**What a builder would get wrong by assuming**

1) "Staking limit" is misleading: it is a reminder only (stake_reminders, "A reminder, never a limit"); nothing blocks a bet, and it is unrelated to F25's per-book limit log. 2) staked_this_week and exceeded are computed on request from bets.placed_at in a Monday-to-Sunday UTC week, void bets excluded; only the threshold and last_reminded_week are stored. The reminder fires only on an upward crossing during a bet create or sync import (not on bet edits or threshold changes), once per week. 3) Entitlements are not stored and gate nothing: require_entitlement is on no route, both plans are identical, and with premium_gating off everyone gets the premium entry. Plans are a two-value Literal declared separately in api/admin.py, entitlements/catalog.py and entitlements/router.py, and validated again in web admin-actions.ts. 4) The entitlement keys value_screen and tracker_analytics share names with feature flags but are separate mechanisms. 5) Flags are global, not per user or per plan; a feature_flags row is only an override and rows for keys missing from KNOWN_FLAGS are ignored. There is no flags cache: each check is a query. 6) Adding a flag means touching several lists by hand: flags/catalog.py, web lib/site.ts (APP_NAV, FLAGGED_PATHS), web lib/admin.ts flagWarning, and the mobile FlagKey union (which omits premium_gating). The web reads /v1/flags in two places (lib/flags.ts and proxy.ts). Web and mobile both treat unknown or unloaded flags as off. 7) There is no admin UI on mobile and no apps/admin; the web browser bridge /api/ov deliberately excludes /v1/admin, so admin calls must be server components or server actions. 8) The admin role is not stored authority: it is re-derived from ODDVEX_ADMIN_EMAILS on every token use, so setting users.role in the database does not last. 9) GET /v1/admin/flags and GET /v1/admin/audit are not audited as admin.read, unlike overview, users, outbox and community reports. 10) audit_log.user_id is not a foreign key and write_audit does not commit; the caller commits. 11) StakeReminderForm and StakeReminderNotice are implemented twice (web and mobile) with separate copy; the web form takes server-fetched data while the mobile one fetches by userId.

## 11. Shared foundation: accounts, sessions and per-user settings

Accounts are email + password (argon2id) with a 21+ attestation; the API issues a single 60-minute HS256 JWT per login (no refresh token, no per-device sessions) and revokes by bumping users.token_version, so logout and password change sign out every device. Web keeps the token in an HttpOnly cookie (ov_session) and talks to the API from server components, server actions and the /api/ov bridge; mobile keeps token + user snapshot in expo-secure-store and sends the bearer header itself. Only three per-user settings are stored server-side and therefore sync (notification kind switches, weekly staking reminder, admin-set plan); odds format and theme are device-local on each client and do not sync, and there is no profile/preferences table at all.

**API (`services/api`)**

- `services/api/src/oddvex_api/auth/router.py`: register, login, logout, /me, delete, password change, email verify, password reset
- `services/api/src/oddvex_api/deps.py`: bearer auth, CurrentUserDep/OptionalUserDep/DataRightsUserDep/AdminDep, write_audit, sync_admin_role
- `services/api/src/oddvex_api/auth/security.py`: argon2 hashing with concurrency limiter, JWT create/decode
- `services/api/src/oddvex_api/auth/schemas.py`: RegisterRequest, UserOut (plan, email_verified), TokenResponse
- `services/api/src/oddvex_api/db/models.py`: User, NotificationPreference, StakeReminder, EmailToken, EmailOutbox, FeatureFlag, AuditLog
- `services/api/src/oddvex_api/account/router.py`: GET /v1/me/export, assembles every user-owned table
- `services/api/src/oddvex_api/account/schemas.py`: AccountExportOut (format_version 1)
- `services/api/src/oddvex_api/notifications/router.py`: /me/notification-preferences and /me/stake-reminder GET/PUT
- `services/api/src/oddvex_api/notifications/service.py`: preferences_out, update_preferences, stake reminder logic
- `services/api/src/oddvex_api/notifications/schemas.py`: NotificationKind list (10 kinds)
- `services/api/src/oddvex_api/entitlements/catalog.py`: free/premium catalog, 4 feature keys, all identical
- `services/api/src/oddvex_api/entitlements/service.py`: entitlement, check_entitlement, require_entitlement (unused on routes)
- `services/api/src/oddvex_api/entitlements/router.py`: GET /v1/me/entitlements
- `services/api/src/oddvex_api/flags/catalog.py`: six known global flags and defaults
- `services/api/src/oddvex_api/flags/service.py`: is_enabled, require_flag, set_flag
- `services/api/src/oddvex_api/flags/router.py`: public GET /v1/flags
- `services/api/src/oddvex_api/api/admin.py`: suspend/unsuspend, PUT users/{id}/plan, flag overrides
- `services/api/src/oddvex_api/mailer/service.py`: single-use hashed email tokens, outbox emails (nothing sent)
- `services/api/src/oddvex_api/mailer/router.py`: dev-only GET /v1/dev/email-outbox/latest
- `services/api/src/oddvex_api/ratelimit.py`: per-IP auth bucket, per-email login throttle, account action limits (in memory)
- `services/api/src/oddvex_api/config.py`: jwt_secret, jwt_ttl_minutes, admin_emails, hash and rate limits
- `services/api/src/oddvex_api/main.py`: router registration under /v1
- `services/api/src/oddvex_api/seed.py`: demo user and demo admin
- `services/api/alembic/versions/0001_initial_schema.py`: users table
- `services/api/alembic/versions/0002_watchlist_structured_legs_password.py`: users.token_version, password_changed_at
- `services/api/alembic/versions/0003_alerts_notifications_stake_reminder.py`: notification_preferences, stake_reminders
- `services/api/alembic/versions/0004_flags_plans_admin_email.py`: users.plan/status/last_login_at/email_verified_at, feature_flags, email_tokens, email_outbox

**Web (`apps/web`)**

- `apps/web/src/lib/session.ts`: currentUser, requireUser, setSession/clearSession, oddsFormat() cookie reader, safeNext
- `apps/web/src/lib/auth-actions.ts`: server actions: login, signup, logout, reset, verify, delete, change password
- `apps/web/src/lib/api.ts`: server-side api() attaching the cookie token; ApiError
- `apps/web/src/lib/config.ts`: SESSION_COOKIE = ov_session, API_URL, servedOverHttps
- `apps/web/src/lib/client-api.ts`: browser calls via /api/ov bridge
- `apps/web/src/app/api/ov/[...path]/route.ts`: same-origin bridge, path allowlist, clears cookie on suspension
- `apps/web/src/app/api/session/ended/route.ts`: clears cookie when API rejects token
- `apps/web/src/proxy.ts`: CSP, request id, 404 for non-admin and flagged-off pages
- `apps/web/src/lib/flags.ts`: getFlags, flagOn, requireFlag (server)
- `apps/web/src/app/app/settings/page.tsx`: settings page: display, account, plan, notifications, reminder, password, sessions, export, delete
- `apps/web/src/app/app/layout.tsx`: loads user + ov_odds cookie, mounts OddsFormatProvider, header toggles
- `apps/web/src/components/app/odds-format.tsx`: OddsFormatProvider, Price, OddsFormatToggle; writes ov_odds cookie
- `apps/web/src/lib/format.ts`: OddsFormat type (american | decimal), formatPrice
- `apps/web/src/components/ui/theme-toggle.tsx`: theme in localStorage ov-theme
- `apps/web/src/lib/theme-script.ts`: pre-paint theme script (CSP-hashed)
- `apps/web/src/components/app/auto-refresh.tsx`: auto-refresh on/off in localStorage
- `apps/web/src/components/app/account-forms.tsx`: ChangePasswordForm, ExportDataButton
- `apps/web/src/components/app/delete-account.tsx`: DeleteAccountForm (type DELETE)
- `apps/web/src/components/app/auth-forms.tsx`: login, signup, forgot/reset, verify, resend forms
- `apps/web/src/components/app/notification-settings.tsx`: NotificationPreferences, StakeReminderForm
- `apps/web/src/app/(auth)/login/page.tsx`: login page
- `apps/web/src/app/(auth)/signup/page.tsx`: signup page
- `apps/web/src/app/(auth)/forgot-password/page.tsx`: request reset
- `apps/web/src/app/(auth)/reset-password/page.tsx`: set new password from token
- `apps/web/src/app/(auth)/verify-email/page.tsx`: confirm email from token
- `apps/web/src/app/(auth)/layout.tsx`: auth pages shell

**Mobile (`apps/mobile`)**

- `apps/mobile/src/session/store.ts`: token + expiry + user in expo-secure-store key oddvex.session
- `apps/mobile/src/providers/session.tsx`: SessionProvider: logIn, createAccount, logOut, changePassword, deleteAccount, revision counters
- `apps/mobile/src/providers/odds-format.tsx`: odds format in AsyncStorage key oddvex.odds-format
- `apps/mobile/src/providers/flags.tsx`: GET /v1/flags on launch, foreground and sign-in
- `apps/mobile/src/api/client.ts`: bearer token holder, unauthorized handler, all auth/account/settings calls
- `apps/mobile/src/api/types.ts`: User, Plan, Entitlements types
- `apps/mobile/src/screens/settings.tsx`: settings screen: account, odds format, notifications, reminder, password, delete
- `apps/mobile/src/screens/auth.tsx`: LoginScreen, SignupScreen, validateSignup
- `apps/mobile/src/components/account-forms.tsx`: EmailVerificationStatus, EntitlementsLine, ChangePasswordForm, DeleteAccountForm
- `apps/mobile/src/components/notification-settings.tsx`: notification switches and stake reminder form
- `apps/mobile/src/app/_layout.tsx`: provider order and modal auth routes
- `apps/mobile/src/app/(tabs)/(settings)/settings.tsx`: settings route
- `apps/mobile/src/app/login.tsx`: login route
- `apps/mobile/src/app/signup.tsx`: signup route
- `apps/mobile/src/app/forgot-password.tsx`: reset request route
- `apps/mobile/src/app/reset-password.tsx`: deep-link reset route
- `apps/mobile/src/app/verify-email.tsx`: deep-link verify route
- `apps/mobile/src/hooks/use-theme.ts`: theme follows system colour scheme only
- `apps/mobile/src/utils/format.ts`: OddsFormat type and formatPrice (copy of web's)
- `apps/mobile/src/test/session.tsx`: session test helper

**Entry points**

- POST /v1/auth/register
- POST /v1/auth/login
- POST /v1/auth/logout - revokes every token of the account
- GET /v1/me
- DELETE /v1/me
- POST /v1/me/password
- GET /v1/me/export
- GET /v1/me/entitlements
- GET /v1/me/notification-preferences
- PUT /v1/me/notification-preferences
- GET /v1/me/stake-reminder
- PUT /v1/me/stake-reminder
- POST /v1/auth/verify-email/request (flag email_flows)
- POST /v1/auth/verify-email/confirm (flag email_flows)
- POST /v1/auth/password-reset/request (flag email_flows)
- POST /v1/auth/password-reset/confirm (flag email_flows)
- GET /v1/flags - public
- PUT /v1/admin/users/{user_id}/plan - only way a plan changes
- PUT /v1/admin/users/{user_id}/suspend and /unsuspend (methods as in api/admin.py)
- PUT /v1/admin/flags/{key}
- GET /v1/dev/email-outbox/latest - non-production only
- Web: /login, /signup, /forgot-password, /reset-password, /verify-email, /app/settings
- Web: /api/ov/[...path] bridge, /api/session/ended
- Mobile screens: /login, /signup, /forgot-password, /verify-email, /reset-password (modals), Settings tab; deep links oddvex://verify-email and oddvex://reset-password
- Script: services/api/scripts/seed_demo.py - demo user and admin

**Tests**

- `services/api/tests/test_api_auth.py`: register, login, logout, /me, delete
- `services/api/tests/test_api_account.py`: export contents, password change and token revocation
- `services/api/tests/test_email_flows.py`: verification and password reset tokens, outbox
- `services/api/tests/test_security.py`: JWT rejection cases, IDOR sweep, mass assignment of role/plan/status, login throttle
- `services/api/tests/test_password_hash_limit.py`: argon2 concurrency limiter and 429 shedding
- `services/api/tests/test_api_flags_entitlements.py`: flag defaults/overrides, entitlement resolution, no billing route
- `services/api/tests/test_api_notifications.py`: notification preferences and stake reminder
- `services/api/tests/test_api_admin_manage.py`: suspend, plan set, flag overrides
- `services/api/tests/test_migrations_seed_openapi.py`: migrations, seed, openapi.json in step
- `apps/web/e2e/app.spec.ts`: signup 21+, login errors, forgot password, change password, export, delete account, cookie HttpOnly, odds format toggle persists
- `apps/web/e2e/security.spec.ts`: CSP while switching theme and odds format
- `apps/web/src/lib/format.test.ts`: formatPrice and display helpers
- `apps/mobile/src/session/store.test.ts`: secure-store save/load/expiry
- `apps/mobile/src/providers/session.test.tsx`: session lifecycle, 401 handling, suspension
- `apps/mobile/src/providers/odds-format.test.tsx`: AsyncStorage persistence
- `apps/mobile/src/providers/flags.test.tsx`: flag loading and fallbacks
- `apps/mobile/src/screens/settings.test.tsx`: settings screen
- `apps/mobile/src/screens/auth.test.tsx`: login and signup screens
- `apps/mobile/src/components/account-forms.test.tsx`: password change, delete, verification status
- `apps/mobile/src/components/notification-settings.test.tsx`: preferences and reminder forms
- `apps/mobile/src/api/client.test.ts`: token attach and unauthorized handler

**Data model**

users (email, password_hash, display_name, role, is_active, age_confirmed_at, created_at, token_version, password_changed_at, plan free|premium, status active|suspended, last_login_at, email_verified_at, search_key); notification_preferences (user_id PK, in_app_disabled JSON list; no row = all on); stake_reminders (user_id PK, weekly_stake_threshold, last_reminded_week); email_tokens (hashed, single-use, purpose verify_email|password_reset); email_outbox; feature_flags (global overrides); audit_log (user_id not a FK, survives deletion). Migrations 0001 to 0004 in services/api/alembic/versions. There is no sessions table, no refresh-token table and no profile/preferences table. Settings today: notification kind switches - database, syncs; weekly staking reminder threshold - database, syncs; plan - database, admin-set, syncs; display name - database, set at signup only, no update route; odds format - web cookie ov_odds (1 year, non-HttpOnly) and mobile AsyncStorage oddvex.odds-format, does not sync; theme - web localStorage ov-theme, mobile follows the system with no setting, does not sync; auto-refresh on/off - web localStorage only. State, books held, unit size, display mode and quiet state do not exist anywhere.

**Flags and plan checks today**

Flag email_flows (on outside production, off in production) gates the four verify-email and password-reset routes with 404 feature_disabled, and decides whether an ODDVEX_ADMIN_EMAILS address needs a confirmed email before getting the admin role. Flag premium_gating (off) switches entitlement enforcement; while off GET /v1/me/entitlements returns preview=true and everyone gets the premium entitlement. The catalog has four keys (alerts.max_active, value_screen, tracker_analytics, odds_history_hours) with identical free and premium values, and require_entitlement is attached to no route, so nothing is plan-gated today. Plans are only free|premium, set only by PUT /v1/admin/users/{id}/plan; no billing or purchase route (a test asserts this). Admin role comes solely from the ODDVEX_ADMIN_EMAILS allowlist, re-synced on every token use. Suspended accounts are rejected everywhere except GET /v1/me/export and DELETE /v1/me. Turning premium_gating on, pricing and billing are Founder approval gates.

**Backlog items that will touch it**

- **P0.3**: Extends entitlements/catalog.py and service.py (Plan literal, users.plan, UserOut.plan, EntitlementsOut, admin plan route) from free|premium to pro, pass and b2b keys, and adds a non-JWT key auth path beside deps._authenticate.
- **P0.4**: Needs a new per-user settings table, migration and /v1/me route, and must replace the web ov_odds cookie and mobile AsyncStorage odds-format providers with a server-synced value on both settings screens.
- **P0.6**: The copy guard will scan the auth and settings strings in auth-forms, settings pages and mailer templates, and the suppression hook needs the user's quiet and plan state read through deps/profile.
- **F05**: Records pack export should reuse the account export route's DataRightsUserDep and audit pattern, and must be added to AccountExportOut and the delete cascade.
- **F06**: Dollar View is a display toggle that belongs in the same odds-format providers and Price component on web and mobile and in the synced profile settings.
- **F08**: Clear Mode is a display-mode setting that must join theme and odds format in both settings screens and move the web theme out of localStorage into the profile.
- **F11**: Quiet Mode adds a per-user quiet state and a control on both settings screens next to the existing notification preferences and staking reminder.
- **F14**: Import-first onboarding changes what happens after signupAction and mobile createAccount, and writes the proposed state, books and unit size into profile settings.
- **F16**: State and books-held filters read the user's state and books from profile settings, which do not exist on the user model yet.
- **F23**: Plan Mode stores weekly budget settings per user alongside stake_reminders and reuses that table's weekly-total pattern and settings forms.
- **F24**: Season pass and pause add a term-limited plan and reduced entitlement to users.plan, the entitlements catalog and the plan line on both settings screens.
- **F25**: Per-book stake limits are user-owned records that must be added to the user delete cascade and AccountExportOut.
- **F31**: Workspaces opened on another device rely on server-stored per-user state and the same login on web and mobile, and must join the export and delete cascade.
- **F39**: Expiring, revocable read-only share links need a second token type; the hashed single-use token pattern in mailer/service.py and write_audit access logging are the things to reuse.
- **F41**: Sheets functions need a long-lived per-user API key, which the current single 60-minute JWT in deps._authenticate cannot provide.
- **F42**: A Discord bot needs b2b key authentication and account linking that deps.py and the entitlements service do not have today.

**What a builder would get wrong by assuming**

1. Odds format looks like an account setting but is device-local on both clients (web cookie ov_odds, mobile AsyncStorage) and only supports american|decimal; implied probability is not an option anywhere. 2. "Log out" is always "log out everywhere": there are no per-device sessions or refresh tokens, only users.token_version; a mobile login silently expires after 60 minutes (jwt_ttl_minutes) with no renewal. 3. The JWT carries a role claim but the server ignores it and reads the role from the database. 4. Mobile caches a User snapshot in SecureStore, so plan or email_verified can be stale until GET /v1/me returns. 5. Entitlements exist but gate nothing: the catalog is identical for both plans, premium_gating is off, and require_entitlement is on no route; while gating is off everyone resolves as premium. 6. Feature flags are global, not per user. 7. display_name has no update route; there is no PATCH /v1/me at all. 8. Mobile has no data export button (web only) and no theme setting; web has no deep-link equivalent problem but mobile's delete-account copy omits community data that web mentions. 9. OddsFormat type and formatPrice are duplicated in apps/web/src/lib/format.ts and apps/mobile/src/utils/format.ts, as are the signup and password validation rules (web server actions vs mobile validateSignup/validatePasswordChange). 10. The account export and delete are hand-assembled: any new user-owned table must be added to AccountExportOut and given an ON DELETE CASCADE relationship on User or it will be missed. 11. The web /api/ov bridge has a path allowlist; a new top-level /v1 prefix is unreachable from client components until added there (anything under /v1/me already passes). 12. Email flows write to email_outbox and send nothing; email_flows defaults off in production. 13. Rate limits and login throttles are in process memory, so they reset on restart and are per process. 14. Web settings label "Saved in this browser" is accurate and must change when P0.4 lands; the privacy page also documents the ov_odds cookie. 15. I did not open the bodies of the mobile forgot-password, reset-password and verify-email route files or run any tests; their existence is verified by listing only.

## 12. Shared foundation: data providers, fixtures and the data model

All sports data (leagues, books, teams, players, events, odds, line history, game logs, prop offers) comes from one in-process SportsDataProvider (synthetic by default, or a time-shifted NFL 2024 replay) chosen at startup by ODDVEX_DATA_PROVIDER, held on app.state.provider, wrapped per request by Board (best price, consensus, staleness, value rows) with a process-local TTL cache, and served under /v1. Nothing from the provider is persisted: the database (21 tables, Alembic 0001-0005) holds only user-side data, with provider ids stored as plain strings. data/fixtures holds synthetic vendor-wire-format JSON that only tests/test_provider_contract.py reads, to pin providers/normalize.py, an adapter seam no runtime code calls yet.

**API (`services/api`)**

- `services/api/src/oddvex_api/providers/base.py`: SportsDataProvider Protocol (15 methods) and frozen pydantic records with provider/provider_id/fetched_at
- `services/api/src/oddvex_api/providers/synthetic.py`: SyntheticProvider: pure function of (seed, clock); also defines _BOOKS, _Book, price helpers
- `services/api/src/oddvex_api/providers/replay.py`: ReplayProvider and load_replay_dataset; imports private _BOOKS/_Book from synthetic.py
- `services/api/src/oddvex_api/providers/normalize.py`: vendor wire format to canonical models, ProviderContractError; used only by tests
- `services/api/src/oddvex_api/providers/__init__.py`: re-exports contract and both providers
- `services/api/src/oddvex_api/main.py`: build_provider(settings, clock), create_app(settings, provider=...), create_all outside production, auto seed
- `services/api/src/oddvex_api/deps.py`: ProviderDep, BoardDep, CacheDep, DbDep, NowDep (clock is provider.now())
- `services/api/src/oddvex_api/board.py`: Board: read models over the provider, best price, consensus line, staleness, value rows, line_history, SYNTHETIC_NOTICE
- `services/api/src/oddvex_api/cache.py`: Cache Protocol, InMemoryTTLCache, cached()
- `services/api/src/oddvex_api/api/data.py`: health, meta, leagues, sportsbooks, events, odds, line-history, players, props, value routes
- `services/api/src/oddvex_api/db/models.py`: all 21 ORM tables; docstring sketches a future odds_snapshots key
- `services/api/src/oddvex_api/db/base.py`: Base with naming convention, UTCDateTime (rejects naive datetimes), new_id, utcnow
- `services/api/src/oddvex_api/db/session.py`: make_engine (SQLite FK pragma, psycopg URL rewrite), make_session_factory
- `services/api/src/oddvex_api/db/__init__.py`: model re-exports; new models must be added here
- `services/api/alembic/env.py`: Alembic environment
- `services/api/alembic/versions/0001_initial_schema.py`: users, bets, bet_legs, sync_connections, sync_import_runs, audit_log
- `services/api/alembic/versions/0002_watchlist_structured_legs_password.py`: watchlist_items, bet_legs.outcome_key, bets.settled_by
- `services/api/alembic/versions/0003_alerts_notifications_stake_reminder.py`: alert_rules, notifications, notification_preferences, stake_reminders
- `services/api/alembic/versions/0004_flags_plans_admin_email.py`: feature_flags, email_tokens, email_outbox, users.plan/status
- `services/api/alembic/versions/0005_community_and_search_keys.py`: community_* tables, users.search_key, bets.sportsbook_key
- `services/api/src/oddvex_api/seed.py`: seed_demo: demo user, 40 bets, gradeable bets and alert rules from provider events
- `services/api/src/oddvex_api/community/seed.py`: seed_demo_community; reads provider.get_line_history for pick prices
- `services/api/src/oddvex_api/config.py`: data_provider, replay_data_path, replay_shift_days, synthetic_seed, stale_*_seconds; replay refused in production
- `services/api/src/oddvex_api/sync/base.py`: SyncProvider Protocol: the second provider pattern (bet import)
- `services/api/src/oddvex_api/sync/registry.py`: SyncRegistry and default_registry: keyed-registry pattern
- `services/api/src/oddvex_api/sync/mock.py`: MockSyncProvider
- `services/api/scripts/build_replay_data.py`: nflverse CSV and Parquet to data/external/replay/nfl_2024.json
- `services/api/scripts/seed_demo.py`: CLI wrapper for seed_demo
- `services/api/scripts/evaluate_alerts.py`: cron-style alert evaluation with build_provider
- `services/api/scripts/grade_picks.py`: cron-style community pick grading
- `services/api/scripts/export_openapi.py`: writes services/api/openapi.json; --check for CI
- `data/fixtures/README.md`: rules for synthetic fixtures
- `data/fixtures/events.sample.json`: three vendor-format events
- `data/fixtures/odds_snapshots.sample.json`: five vendor-format quotes
- `data/fixtures/player_game_log.sample.json`: one player's stat lines
- `data/fixtures/invalid_payloads.sample.json`: payloads normalize must reject
- `data/external/README.md`: replay preview rules, sources, licences; raw files git-ignored
- `data/external/LICENSES.md`: licence links
- `docs/architecture/ADR-0002-data-and-freshness.md`: entities served from provider, not persisted; PostgreSQL only

**Web (`apps/web`)**

- `apps/web/src/app/app/layout.tsx`: fetches /v1/meta; synthetic and replay banners
- `apps/web/src/app/app/games/page.tsx`: events board
- `apps/web/src/app/app/games/[id]/page.tsx`: event detail, odds and /v1/events/{id}/line-history
- `apps/web/src/app/app/odds/page.tsx`: odds comparison
- `apps/web/src/app/app/props/page.tsx`: props board
- `apps/web/src/app/app/props/[playerId]/page.tsx`: player props
- `apps/web/src/app/app/value/page.tsx`: value screen with data_mode caveats
- `apps/web/src/lib/leagues.ts`: getLeagues from /v1/leagues; hardcoded MARKETS list
- `apps/web/src/lib/api.ts`: server fetch helper
- `apps/web/src/lib/types.ts`: type aliases over packages/types
- `apps/web/e2e/start-api.sh`: alembic upgrade head, seed_demo.py --with-community, starts API for Playwright

**Mobile (`apps/mobile`)**

- `apps/mobile/src/providers/meta.tsx`: loads /v1/meta once; isSynthetic, isReplay
- `apps/mobile/src/components/synthetic-badge.tsx`: header badge for synthetic or replay
- `apps/mobile/src/api/client.ts`: typed fetch functions incl. getMeta
- `apps/mobile/src/screens/games.tsx`: events list
- `apps/mobile/src/screens/game-detail.tsx`: event odds; no line-history call
- `apps/mobile/src/screens/settings.tsx`: shows data mode and provider name
- `apps/mobile/src/test/fixtures.ts`: hand-written TS response fixtures, separate from data/fixtures
- `apps/mobile/src/app/(tabs)/(games)/index.tsx`: games route
- `apps/mobile/src/app/(tabs)/(games)/event/[id].tsx`: event route

**Entry points**

- GET /health
- GET /v1/meta
- GET /v1/leagues
- GET /v1/sportsbooks
- GET /v1/events
- GET /v1/events/{event_id}
- GET /v1/events/{event_id}/odds
- GET /v1/events/{event_id}/line-history
- GET /v1/players
- GET /v1/players/{player_id}
- GET /v1/players/{player_id}/props
- GET /v1/props
- GET /v1/value
- Web: /app/games, /app/games/[id], /app/odds, /app/props, /app/props/[playerId], /app/value
- Mobile: (tabs)/(games)/index, (tabs)/(games)/event/[id], (tabs)/(props)/props, (tabs)/(props)/player/[id], (tabs)/(tools)/value, (tabs)/(settings)/settings
- Script: services/api/scripts/build_replay_data.py --schedule --stats --season --out
- Script: services/api/scripts/seed_demo.py [--with-community] [--allow-production]
- Script: services/api/scripts/evaluate_alerts.py [--dry-run]
- Script: services/api/scripts/grade_picks.py [--dry-run]
- Script: services/api/scripts/export_openapi.py [--check]
- CLI: alembic upgrade head (from services/api)
- Env: ODDVEX_DATA_PROVIDER=synthetic|replay, ODDVEX_REPLAY_DATA_PATH, ODDVEX_REPLAY_SHIFT_DAYS, ODDVEX_SYNTHETIC_SEED, ODDVEX_AUTO_SEED_DEMO

**Tests**

- `services/api/tests/test_provider_contract.py`: data/fixtures through normalize.py; every fixture must carry a SYNTHETIC _note; invalid payloads rejected
- `services/api/tests/test_provider_synthetic.py`: protocol conformance, provenance, determinism, fictional names, odds, 48h line history, props
- `services/api/tests/test_provider_replay.py`: protocol conformance, week shift, closing line, no early results, dataset loading errors
- `services/api/tests/test_replay_build_and_api.py`: build_replay_data functions, replay refused in production, meta and board routes in replay mode
- `services/api/tests/test_board.py`: best price, consensus, staleness via a ScriptedProvider subclass
- `services/api/tests/test_api_data.py`: all data routes incl. line-history
- `services/api/tests/test_api_value.py`: value screen route
- `services/api/tests/test_migrations_seed_openapi.py`: upgrade head matches models, per-revision upgrade and downgrade with data, seed idempotence, openapi.json current
- `services/api/tests/test_platform.py`: settings, psycopg URL rewrite, TTL cache
- `services/api/tests/conftest.py`: FROZEN_NOW, provider fixture, make_app(provider=...), optional ODDVEX_TEST_DATABASE_URL (Postgres in CI)
- `services/api/tests/fakes.py`: ControlledProvider: movable clock, set_odds, finish, hide
- `services/api/tests/replay_support.py`: fictional replay dataset
- `apps/mobile/src/components/synthetic-badge.test.tsx`: data-mode badge
- `apps/mobile/src/api/client.test.ts`: API client incl. meta

**Data model**

Stored (21 tables, migrations 0001-0005): users, bets, bet_legs, sync_connections, sync_import_runs, watchlist_items, alert_rules, notifications, notification_preferences, stake_reminders, feature_flags, email_tokens, email_outbox, audit_log, community_profiles, community_picks, community_comments, community_follows, community_likes, community_blocks, community_reports. Computed on request and never stored: leagues, sportsbooks, teams, players, events, scores, odds, line history, game logs, prop offers, consensus, best price, value rows. No price or line history is persisted: get_line_history regenerates about 48 hourly points from seed and clock on each call. The only stored prices are point-in-time copies on user rows: bet_legs.odds_decimal, closing_odds_decimal and closing_opposite_odds_decimal (typed by the user or supplied by the sync import, never captured from the provider), community_picks.price_decimal with sportsbook_key (best price at posting), alert_rules.baseline_line and threshold_decimal. Provider ids (event_id, team_id, ref_id) are plain strings, deliberately not foreign keys. Conventions for new tables: String(32) uuid hex ids via new_id, UTCDateTime columns, MONEY Numeric(14,2), ODDS Numeric(16,6), JSON columns, export from db/__init__.py, next migration is 0006 with a matching upgrade/downgrade test.

**Flags and plan checks today**

Provider choice is configuration, not a flag: ODDVEX_DATA_PROVIDER (replay refused when ODDVEX_ENV=production). Only GET /v1/value is flag-gated (require_flag("value_screen"), default on, 404 when off); every other data route is public with no auth and no plan check. The entitlement catalog has odds_history_hours (48 for both free and premium) but nothing reads it: line-history is not gated and the 48-hour window is a HISTORY_HOURS constant inside each provider. premium_gating is off by default and both plans have identical limits.

**Backlog items that will touch it**

- **P0.1**: Adds the first persisted market data: an append-only odds_snapshots table (models.py docstring already names the key and provenance columns), migration 0006 and a capture job that reads provider.get_odds, plus an as-of read path.
- **P0.2**: Reuses the ProviderRecord provenance fields (provider, provider_id, fetched_at) and Board's consensus and best-price code as the inputs to record with each method id and version.
- **P0.4**: Adds a profile settings table and migration in db/models.py; books held must reference provider sportsbook keys from list_sportsbooks as plain strings.
- **P0.5**: Adds new Protocols and synthetic implementations beside providers/base.py and synthetic.py, new data/fixtures files, normalize functions and contract tests in the test_provider_contract.py pattern, wired through main.py and deps.py.
- **F01**: Matches parsed legs to provider events and markets and reuses Board.best_price and consensus over get_odds, filtered to the user's books.
- **F03**: Needs the best available price at placement time, which only the P0.1 archive can supply; today bet_legs holds only the user's own price and a user-entered closing price.
- **F09**: Reuses Board's per-book quote rows and last_updated staleness to show consensus inputs and leave-one-out values.
- **F10**: Reuses get_player_game_log (40 synthetic games) for season baselines; GameLogEntry has no overtime marker, so the contract needs a field.
- **F12**: Adds persisted, time-stamped signal outputs and closing prices as new tables; nothing of the kind is stored today.
- **F13**: Searches provider list_players, list_teams and list_events; market keys are limited to the Literal sets in base.py and each league's prop_markets.
- **F16**: Consumes the new state market catalog provider and filters Board output by the user's books and state.
- **F17**: Adds the lineup and news provider and attaches timestamped markers to the LineSeries returned by get_line_history.
- **F18**: Adds the live box score provider; today Event carries only a score and period_text, and replay has no in-play data at all.
- **F20**: Reuses current get_odds quotes and Board no-vig consensus to value an open bet_legs row.
- **F22**: Stores a private snapshot of provider quotes and rules as a new table, reusing the snapshot row shape from P0.1.
- **F26**: Reuses get_odds per leg for no-vig leg prices; stage 2 needs same-game correlation inputs the provider contract does not expose.
- **F27**: Consumes the new house rules provider keyed by the provider's sportsbook keys.
- **F28**: Reuses the three-way soccer moneyline from get_odds (league.has_draw) as input.
- **F29**: Needs markets at least 24 hours old, so it reads the P0.1 archive or the provider's closed-market quotes for final events.
- **F30**: Joins bet_legs to the P0.1 archive by event_id, market and sportsbook key to find the best book the user does not hold.
- **F32**: Reuses get_prop_offers and get_player_game_log to fit distributions; PropOffer carries one line per book, no alternates.
- **F33**: Extends GameLogEntry and the lineup provider with pre-game context; the current log has only opponent, home/away and stats.
- **F34**: Reads the P0.1 archive as of a time T; ReplayProvider's clock injection and never-reveal-early rule are the pattern to reuse, not its simulated prices.
- **F35**: Reuses the house rules provider and final scores from get_event for the evidence record.
- **F37**: Walk-forward testing needs archived closing lines from P0.1; the replay dataset has one consensus closing line per NFL game only.
- **F40**: Adds the venue legal status and exchange contract providers from P0.5 with their fixtures.
- **F43**: Charts a past market event from the P0.1 archive with provenance fields as the visible sources.
- **F44**: Reports gaps and delays from the P0.1 archive using fetched_at, last_updated and ProviderHealth.

**What a builder would get wrong by assuming**

1. Line history is not history: both providers recompute the 48-hour series from (seed, clock) on every call, and nothing is written anywhere. An archive cannot be backfilled from it in any meaningful way.
2. OddsSnapshot in providers/base.py is a pydantic record of a current quote, not a table. No odds_snapshots table exists; it appears only in the db/models.py docstring.
3. providers/normalize.py and data/fixtures are not on any runtime path. Neither provider calls normalize; only tests/test_provider_contract.py does. The "fixture provider" the brief mentions does not exist yet: the existing pattern is fixtures plus normalize functions plus contract tests, with SyntheticProvider generating data in code.
4. To match the existing pattern for a new provider: a runtime_checkable Protocol with name, data_mode, now() and health(); frozen ProviderRecord subclasses; a seeded, clock-injected synthetic implementation; a build_* function in main.py that stores it on app.state and accepts an override in create_app; a Dep alias in deps.py; fixture JSON whose top-level _note contains "SYNTHETIC" (the test globs every *.json in data/fixtures and fails otherwise); strict normalize functions that raise ProviderContractError; and a protocol isinstance test. sync/base.py plus sync/registry.py is the alternative keyed-registry pattern.
5. replay.py imports private names (_BOOKS, _Book, _american_from_implied, _half_line) from synthetic.py, so the fictional book list lives in one private tuple; seed.py has its own separate _BOOKS tuple of display names.
6. The application clock is provider.now() (NowDep), not wall time. Tests freeze it at 2026-03-14 19:30 UTC; any capture job must take its timestamps from the provider.
7. Cache is process-local and per worker; Board caches value and props rows there. There is no background worker: alerts and pick grading run lazily on read or through the two scripts.
8. bet_legs.closing_odds_decimal is user or sync supplied, never captured from the provider, so CLV today rests on self-reported closing prices.
9. The odds_history_hours entitlement exists in the catalog but is read by nothing.
10. Market keys are closed Literal sets (moneyline, spread, total) in base.py and in API schemas; props are a separate PropOffer shape with one over/under line per book. First-half, alternate-line and same-game markets need contract changes, not only new data.
11. Outside production, tables are created with Base.metadata.create_all at startup, so a missing migration goes unnoticed locally; test_migrations_seed_openapi.py compares upgrade head with the models and is what catches it. CI also runs the suite on PostgreSQL 16.
12. data/external is git-ignored except README.md, LICENSES.md and .gitignore; the files present locally (including replay/nfl_2024.json) carry real names and are approved for internal preview only (decision D-015).
13. The mobile app does not call the line-history route; only the web game page does. Mobile test fixtures are hand-written TypeScript unrelated to data/fixtures.
14. Not run: no tests or builds were executed for this map, per the task rules; everything above is from reading the files.

## 13. Shared foundation: CI, tests and quality gates

CI is one workflow (/home/user/OddVex/.github/workflows/ci.yml) with nine jobs: API lint+pytest+OpenAPI drift, the same pytest suite on PostgreSQL 16, web lint/typecheck/vitest/build plus generated-types drift, mobile lint/typecheck/Jest/Expo bundle, Playwright e2e (real API on SQLite + production web build, includes axe a11y), Docker smoke test, dependency audit and gitleaks. There is no single copy guard today: banned-phrase checks exist as seven-plus separate lists spread over pytest (notification, email, value, analytics, community copy), mobile Jest (source-file scan of community files plus rendered-screen scans) and Playwright (rendered page text), each with a different phrase list. Feature flags are tested at three levels: API catalog/dependency/route tests, mobile provider tests with a WithFlags wrapper, and Playwright specs that flip flags through the admin API on a shared server. I read the files and ran no tests or builds (the task forbids it).

**API (`services/api`)**

- `services/api/tests/conftest.py`: fixtures: make_settings, make_app, client, admin_client; helpers register, auth_headers, admin_headers, verify_email, set_flag; ODDVEX_TEST_DATABASE_URL switches the suite to Postgres
- `services/api/tests/test_notification_copy.py`: BANNED_PHRASES and BANNED_WORDS; scans every notification template and a rendered sample; imported by four other test files
- `services/api/tests/test_api_flags_entitlements.py`: flag defaults (hard-coded DEFAULTS dict), require_flag, flagged routes 404, entitlement resolution with a monkeypatched catalog
- `services/api/tests/test_migrations_seed_openapi.py`: per-revision upgrade/downgrade tests, models-match-migrations, seed tests, EXPECTED_OPERATIONS (hand-kept map of every route to its operation id), committed openapi.json check
- `services/api/scripts/export_openapi.py`: deterministic openapi.json writer; --check mode; fixed settings env=development
- `services/api/openapi.json`: committed schema, source for packages/types
- `services/api/pyproject.toml`: pytest, ruff and mypy config (mypy configured but not run in CI)
- `services/api/tests/test_security.py`: token, IDOR and owner-scoped-route sweeps with hand-kept route lists
- `services/api/tests/test_platform.py`: error envelope, headers, CORS, rate limits, settings, body limit
- `services/api/tests/test_email_flows.py`: email template copy scan (BANNED_PHRASES plus urgent, immediately, act now, winner)
- `services/api/tests/test_api_value.py`: test_no_banned_phrase_anywhere_on_the_value_screen (response and schema text)
- `services/api/tests/test_api_review_followups.py`: BANNED_STREAK_COPY scan of analytics strings
- `services/api/tests/test_api_community.py`: guidelines, feed and leaderboard copy scans using BANNED_PHRASES
- `services/api/tests/test_api_notifications.py`: delivered notification copy scan using BANNED_PHRASES
- `services/api/tests/test_community_content_rules.py`: tests the runtime filter on user-written text (not OddVex's own copy)
- `services/api/tests/fakes.py`: ControlledProvider and quote builders for deterministic markets
- `services/api/tests/community_support.py`: community test helpers (enable flags, member, post_pick)
- `services/api/tests/replay_support.py`: replay dataset builder for provider tests
- `services/api/tests/quant/`: nine unit and hypothesis test files for odds math
- `services/api/src/oddvex_api/flags/catalog.py`: KNOWN_FLAGS: the six flags and defaults
- `services/api/src/oddvex_api/flags/service.py`: is_enabled, flag_states, set_flag, require_flag dependency (404 feature_disabled)
- `services/api/src/oddvex_api/flags/router.py`: GET /v1/flags
- `services/api/src/oddvex_api/entitlements/catalog.py`: CATALOG: plans free and premium, all features equal today
- `services/api/src/oddvex_api/notifications/service.py`: notify(): the one in-app delivery function, six call sites; natural place for a suppression call
- `services/api/src/oddvex_api/notifications/templates.py`: TEMPLATES: every notification string
- `services/api/src/oddvex_api/notifications/channels.py`: NotificationChannel protocol; only InAppChannel exists
- `services/api/src/oddvex_api/mailer/templates.py`: every email string
- `services/api/src/oddvex_api/mailer/service.py`: the two sender.send call sites (verification, password reset)
- `services/api/src/oddvex_api/community/content_rules.py`: regex rules for user text; contains banned words as patterns and in its own rejection message

**Web (`apps/web`)**

- `apps/web/package.json`: scripts: lint (eslint), typecheck, test (vitest run), test:e2e (playwright), build (next build + scripts/csp-hashes.mjs)
- `apps/web/vitest.config.ts`: includes only src/**/*.test.ts, node environment: no component rendering
- `apps/web/playwright.config.ts`: one worker, desktop and Pixel 7 projects, starts API on 8210 and web on 3210
- `apps/web/e2e/start-api.sh`: throwaway SQLite, alembic upgrade, seed_demo.py --with-community, clears community flag overrides, rate limit off
- `apps/web/e2e/start-web.sh`: serves the standalone production build
- `apps/web/e2e/fixtures.ts`: test fixture that fails any test on a CSP violation
- `apps/web/e2e/helpers.ts`: signUp, logIn, adminToken, adminSignIn, setFlag, openMoreOnPhone, sidewaysOverflow
- `apps/web/e2e/a11y.spec.ts`: axe WCAG 2.2 A/AA on a STATIC path list plus signed-in, admin and data screens, both themes
- `apps/web/e2e/community.spec.ts`: flag off/on journey; BANNED list and expectNoBannedCopy on rendered text
- `apps/web/e2e/value-analytics.spec.ts`: BANNED and CELEBRATORY regex lists on rendered value and analytics pages
- `apps/web/e2e/marketing.spec.ts`: two inline banned lists for home and features/methodology
- `apps/web/e2e/admin.spec.ts`: flag toggle hides and restores a feature
- `apps/web/e2e/app.spec.ts`: main journeys; design-system screenshot baseline
- `apps/web/e2e/security.spec.ts`: CSP, request id, 404 status
- `apps/web/src/lib/community-copy.test.ts`: checks three fixed strings against an inline banned list
- `apps/web/src/lib/flags.ts`: getFlags, flagOn, requireFlag (notFound when off); string keys
- `apps/web/src/lib/csp.test.ts, format.test.ts, request-meta.test.ts, site.test.ts`: the other vitest unit tests
- `apps/web/eslint.config.mjs`: eslint-config-next only; no custom rules
- `apps/web/src/lib/posts.ts, apps/web/src/lib/site.ts`: blog and site metadata strings outside JSX

**Mobile (`apps/mobile`)**

- `apps/mobile/package.json`: scripts lint (expo lint), typecheck, test (jest), export:check; Jest config inline (jest-expo preset, @/ alias)
- `apps/mobile/jest.setup.js`: mocks AsyncStorage, expo-secure-store, expo-router, safe area
- `apps/mobile/src/test/banned-copy.ts`: BANNED_COPY: nine regexes, the only shared banned list in the JS apps
- `apps/mobile/src/test/strings.ts`: screenStrings(): visible text plus accessibility labels, hints and placeholders of the rendered tree
- `apps/mobile/src/components/community-copy.test.ts`: reads community source files from disk and scans them; closest existing thing to a static copy guard
- `apps/mobile/src/test/flags.tsx`: fakeFlags and WithFlags wrapper; all flags off without it
- `apps/mobile/src/providers/flags.tsx`: FlagsProvider, useFlag; FlagKey is a hand-kept union of five keys
- `apps/mobile/src/providers/flags.test.tsx`: provider load, failure, foreground and sign-in reload
- `apps/mobile/src/test/api.ts`: installFetch, serveRoutes, jsonResponse, errorResponse
- `apps/mobile/src/test/fixtures.ts`: API fixtures incl. flagsAllOn and flagsCommunityOn
- `apps/mobile/src/test/session.tsx, apps/mobile/src/test/community.tsx`: session and community wrappers
- `apps/mobile/src/screens/value.test.tsx, community-feed.test.tsx, community-leaderboard.test.tsx, community-pick.test.tsx, community-profile.test.tsx, apps/mobile/src/components/share-pick.test.tsx`: use BANNED_COPY with screenStrings on rendered screens
- `apps/mobile/src/api/types.ts`: aliases over @oddvex/types (dev dependency, type-only)
- `apps/mobile/eslint.config.js`: eslint-config-expo only
- `apps/mobile/app.json`: store-facing name and permission strings

**Entry points**

- CI: .github/workflows/ci.yml jobs api, api-postgres, web, mobile, e2e, docker, audit, secrets (on pull_request and push to main)
- Script: services/api/scripts/export_openapi.py [--check]
- Script: pnpm types:generate (packages/types: openapi-typescript ../../services/api/openapi.json -o src/api.d.ts)
- Script: cd services/api && pytest -q; ruff check .; ruff format --check .
- Script: pnpm --filter @oddvex/web lint | typecheck | test | build | test:e2e
- Script: pnpm --filter @oddvex/mobile lint | typecheck | test | export:check
- Script: apps/web/e2e/start-api.sh and start-web.sh (started by Playwright)
- GET /v1/flags - public flag states
- PUT /v1/admin/flags/{key} - admin override, used by API tests and Playwright setFlag
- GET /v1/me/entitlements - plan preview
- GET /v1/dev/email-outbox/latest - test-only outbox read used by conftest and e2e helpers
- GET /openapi.json - served schema, checked by the operation-id test
- Web URL /app/admin/flags - flag console exercised by admin.spec.ts and a11y.spec.ts
- Web URL /design - visual baseline and a11y target

**Tests**

- `services/api/tests/test_notification_copy.py`: every notification template and rendered draft: banned phrases, banned words, no ! or %, sentence case
- `services/api/tests/test_api_flags_entitlements.py`: flag defaults, DB override, require_flag 404, flagged routes, entitlements, no billing route
- `services/api/tests/test_migrations_seed_openapi.py`: migrations up/down per revision, seed, operation ids, committed openapi.json current
- `services/api/tests/test_email_flows.py`: email copy scan and flows
- `services/api/tests/test_api_value.py`: value screen copy scan
- `services/api/tests/test_api_review_followups.py`: analytics streak copy scan
- `services/api/tests/test_community_content_rules.py`: runtime filter for user text
- `apps/web/src/lib/community-copy.test.ts`: three fixed community strings vs banned list
- `apps/web/e2e/a11y.spec.ts`: axe WCAG A/AA, both themes
- `apps/web/e2e/community.spec.ts`: flags off/on, rendered banned-copy scan
- `apps/web/e2e/value-analytics.spec.ts`: rendered banned and celebratory scan
- `apps/web/e2e/marketing.spec.ts`: home and features never promise outcomes
- `apps/web/e2e/admin.spec.ts`: flag toggle end to end
- `apps/mobile/src/components/community-copy.test.ts`: source scan of community files with BANNED_COPY, plus a self-test that the scan catches each phrase
- `apps/mobile/src/providers/flags.test.tsx`: flag provider behaviour
- `apps/mobile/src/screens/value.test.tsx`: rendered value screen vs BANNED_COPY

**Data model**

CI and tests own no tables. Flag tests use feature_flags (key, description, enabled, updated_at; migration services/api/alembic/versions/0004_flags_plans_admin_email.py); notification copy tests exercise notifications and notification_preferences; email tests use email_outbox and email_tokens. Migrations 0001 to 0005 exist, each with its own upgrade/downgrade test. API tests create a SQLite file per test (tmp_path) or wipe the database named by ODDVEX_TEST_DATABASE_URL before every test; e2e uses a throwaway SQLite file migrated with alembic and seeded.

**Flags and plan checks today**

Six flags in services/api/src/oddvex_api/flags/catalog.py: community (off), community_leaderboard (off), value_screen (on), tracker_analytics (on), email_flows (on, off in production), premium_gating (off). Entitlement catalog has plans free and premium only, with identical allowances, so gating changes nothing. The CI and test tooling itself is not gated. Tests pin the flag set: DEFAULTS in test_api_flags_entitlements.py, flagsAllOn in apps/mobile/src/test/fixtures.ts, FlagKey union in apps/mobile/src/providers/flags.tsx; e2e starts with in-code defaults and flips flags through PUT /v1/admin/flags/{key}.

**Backlog items that will touch it**

- **P0.1**: Adds a migration, so it needs a new per-revision upgrade/downgrade test in test_migrations_seed_openapi.py and must pass the api-postgres job.
- **P0.3**: Rewrites the entitlement tests in test_api_flags_entitlements.py (plans are free and premium only today) and regenerates openapi.json and packages/types.
- **P0.4**: New profile routes and columns must be added to EXPECTED_OPERATIONS, the owner-scoped route sweeps in test_security.py, a migration test, and the generated types.
- **P0.5**: Synthetic provider fixtures extend the test doubles in services/api/tests/fakes.py and the provider contract tests that every later item runs on.
- **P0.6**: Adds the copy-guard CI check (new step or job in ci.yml) and should replace the scattered lists by reusing apps/mobile/src/test/banned-copy.ts, the source-scan in community-copy.test.ts and BANNED_PHRASES in test_notification_copy.py; the suppression hook goes in front of notifications.service.notify and mailer sender.send.
- **F07**: Explanation text for every number is new user-facing copy served by the API, which the copy guard must scan alongside notification and email templates.
- **F08**: Clear Mode extends apps/web/e2e/a11y.spec.ts (axe run per display mode, keyboard paths) and the mobile screenStrings helper for accessibility labels.
- **F11**: Quiet Mode is the first caller of the suppression hook and needs the cross-channel 'receives nothing' test that P0.6 defines.
- **F12**: Public scorecard pages must be added to the a11y STATIC path list and the marketing/public rendered-copy checks.
- **F23**: Plan Mode triggers suppression and reuses the same every-channel suppression test harness.
- **F41**: A new client surface outside apps/ needs its own CI job and would consume packages/types or openapi.json.
- **F42**: A Discord bot is a new notification-like channel that must call the suppression hook and have its reply strings in the copy guard.

**What a builder would get wrong by assuming**

1. There is no single banned list. At least eight exist with different contents: test_notification_copy.py BANNED_PHRASES (substring, includes bare "lock"), test_api_value.py extras, test_email_flows.py extras, BANNED_STREAK_COPY, apps/mobile/src/test/banned-copy.ts (regex), web community-copy.test.ts, and three inline lists in e2e specs. The P0.6 list (lock, guaranteed, can't lose, risk-free, sure thing, win either way) matches none of them; "win either way" appears nowhere.
2. A naive source scan for the P0.6 phrases fails today on legitimate copy: marketing pages say "No locks, no guaranteed picks", "nothing on it is a guarantee", "call anything a lock or describe any bet as risk-free" (apps/web/src/app/(marketing)/page.tsx, about, terms, responsible-gambling, components/marketing/chrome.tsx); "Stake and odds are locked once a bet is settled" in web bet-actions.tsx and mobile bet-card.tsx; "Nothing in OddVex is locked until you do" in settings and verify-email; RULES_REMINDER "No guarantees"; API content_rules.py message "No outcome is guaranteed" and guidelines.py. The guard needs word-boundary rules and an allowlist or negation handling. Identifiers also hit: pick_locked, guaranteed_outcome, threading.Lock (the mobile scan already strips snake_case tokens for this reason).
3. "User-facing strings" differs per app. API: notifications/templates.py TEMPLATES, mailer/templates.py, community/guidelines.py, ApiError messages, assistant engine/explainer text, analytics notes, and OpenAPI descriptions; web renders many API messages verbatim, so API strings are user-facing. Web: JSX text and attributes (aria-label, title, placeholder, alt) in src/app and src/components, plus lib/community-copy.ts, lib/posts.ts, lib/site.ts and metadata. Mobile: Txt children, accessibilityLabel/Hint, placeholder, Stack titles, components/community-copy.ts, app.json. User-written community text is filtered at runtime by content_rules.py and is not part of a static guard.
4. Where the check fits: simplest is one test per app run by the existing jobs (pytest in api, vitest in web, jest in mobile), since "CI fails on a seeded banned phrase" then needs no workflow change. Web vitest only picks up src/**/*.test.ts in a node environment, so a web guard must be a file scan, not a render. A separate repo-level script would need a new ci.yml step; the root /home/user/OddVex/tests directory exists but is empty and nothing runs it.
5. Playwright copy checks only cover pages a spec visits and only in the e2e job; they are not a guard for new screens.
6. Hand-kept lists break on any new route or flag: EXPECTED_OPERATIONS and the route sweeps in test_security.py, DEFAULTS in the flag test, mobile FlagKey union and flagsAllOn (which, despite the name, has community false and omits community_leaderboard).
7. Flags are global and e2e shares one API process with workers: 1; specs that turn a flag on must turn it off again. A default-off flag for a new item means its e2e spec has to flip it via setFlag.
8. Types drift is checked twice and in order: the api job diffs openapi.json after export, the web job diffs packages/types after generate. Changing a response model without both steps fails CI. export_openapi.py builds the app with env=development, so routes registered only in other environments would not appear.
9. mypy is configured in pyproject.toml but no CI job runs it. The api-postgres job reruns the whole suite; one alerts test runs only there (skipif not postgres).
10. Only the in-app channel exists and mail goes to an outbox table; "every channel" for the suppression test currently means notify() and the two mailer sends.

