# OddVex — Analytics Event Taxonomy

Last updated: 2026-11-21 · Status: **specification / proposal.** No analytics vendor is selected and no analytics SDK is installed in the web or mobile app (code at commit `2b0c7c1`): **none of the events below is emitted today.** Implementation is planned for M2 (PLAT-04); vendor choice and any paid plan require Founder approval. No baselines or targets exist — none are stated here.

## 1. Principles

1. **Measure research value, not betting volume.** We never set goals on amount wagered, number of bets, or stake size.
2. **Privacy by design.** No PII in events; no free text; no exact money amounts.
3. **One taxonomy across web, iOS, Android and server.**
4. **Events describe what happened**, in past tense, at the moment it is confirmed (server-side for critical events).
5. **Consent-aware.** Marketing-site analytics follow the consent approach approved by counsel (PR-06).

## 2. Conventions

| Item | Rule |
|---|---|
| Event name | `snake_case`, `object_action` in past tense: `bet_logged`, `odds_filter_changed` |
| Property name | `snake_case`; booleans prefixed `is_`/`has_`; counts suffixed `_count`; enums lowercase strings |
| IDs | Internal opaque IDs only (`user_id`, `game_id`, `market_id`); never email |
| Timestamps | UTC ISO-8601, set by collector |
| Money | **Buckets only** (`stake_bucket`), never exact values |
| Versioning | `schema_version` on every event; breaking changes create a new event name or version |
| Source of truth | Server emits: signup, login, bet lifecycle, sync, deletion, subscription. Client emits: views and UI interactions |

### Prohibited in any event

Email, name, IP address (beyond vendor-side coarse geo), password/tokens, exact stake/payout/P&L, bet notes, assistant message text or free-text search queries, sportsbook account identifiers, precise location.

## 3. Global properties (sent with every event)

| Property | Type | Example / values |
|---|---|---|
| `platform` | enum | `web`, `ios`, `android`, `server` |
| `surface` | enum | `marketing`, `app`, `admin` |
| `app_version` | string | `1.0.0` |
| `schema_version` | int | `1` |
| `session_id` | string | opaque |
| `anonymous_id` | string | pre-login device/browser ID (consent-dependent) |
| `user_id` | string \| null | opaque internal ID after login |
| `is_authenticated` | bool | |
| `plan` | enum | `free`, `premium` (M4+; `free` until then) |
| `data_mode` | enum | `synthetic`, `live` — **lets us exclude demo-data usage from real metrics** |
| `route` | string | route pattern, e.g. `/app/games/[id]` (never raw URLs with IDs or queries) |
| `locale`, `timezone` | string | `en-US`, `America/New_York` |
| `state_region` | string \| null | only if state capture is approved (PD-Q3) |

User properties (profile-level): `signup_date`, `plan`, `odds_format_pref`, `has_logged_bet`, `has_sync_connection`, `platforms_used`.

## 4. Event catalogue

MS = milestone when the underlying feature exists. Events for planned features are reserved names.

### 4.1 Marketing site

| Event | Trigger | Key properties | MS |
|---|---|---|---|
| `page_viewed` | Any marketing page view | `page_type` (home, feature, pricing, blog_post, legal, help, methodology, rg, download), `referrer_domain`, `utm_source`, `utm_medium`, `utm_campaign` | M1 |
| `cta_clicked` | Primary/secondary CTA click | `cta_id`, `cta_location`, `destination` | M1 |
| `waitlist_joined` | Waitlist form confirmed (server) | `source_page_type` | M2 |
| `blog_post_read` | ≥ 50 % scroll or 30 s engaged | `post_slug`, `pillar` | M1 |
| `help_article_viewed` | Help article open | `article_slug`, `category` | M1 |
| `rg_resource_clicked` | Click on helpline/RG link (any surface) | `resource` (helpline, ncpg, rg_page), `location` | M1 |
| `store_badge_clicked` | Click on store badge | `store` (ios, android) | M6 |

### 4.2 Auth and account

| Event | Trigger | Key properties | MS |
|---|---|---|---|
| `signup_started` | Signup form first interaction | `entry_point`, `landing_page_type` | M1 |
| `signup_age_attestation_blocked` | Submit attempted without 21+ confirmation | — | M1 |
| `signup_completed` | Account created (server) | `method` (email) | M1 |
| `signup_failed` | Server/validation failure | `reason` (validation, rate_limited, server_error) | M1 |
| `login_completed` | Successful login (server) | `method` | M1 |
| `login_failed` | Failed login (server; aggregated, no identifiers) | `reason` (invalid_credentials, rate_limited) | M1 |
| `logout_completed` | Logout | — | M1 |
| `email_verified` | Verification confirmed | — | M2 |
| `password_reset_completed` | Reset done | — | M2 |
| `settings_updated` | Preference saved | `setting` (odds_format, timezone, notifications), `value` (enum only) | M1 |
| `data_export_requested` | Export requested (server) | — | M2 |
| `account_deletion_requested` | Deletion confirmed (server) | `account_age_bucket` | M2 |
| `account_deletion_completed` | Primary-store purge done (server; no user_id — tombstone) | `duration_bucket` | M2 |

### 4.3 Home, games and scores

| Event | Trigger | Key properties | MS |
|---|---|---|---|
| `dashboard_viewed` | `/app` rendered | `modules_loaded_count`, `has_error_module` | M1 |
| `dashboard_module_clicked` | Click-through from a module | `module` (games, best_lines, tracker, quick_actions) | M1 |
| `games_list_viewed` | Games list rendered | `sport`, `league`, `date_offset_days`, `result_count` | M1 |
| `games_filter_changed` | Filter change | `filter` (sport, league, date, status), `value` | M1 |
| `game_viewed` | Game detail rendered | `game_id`, `sport`, `league`, `game_status`, `entry_point` | M1 |
| `favorite_toggled` | Favorite added/removed | `entity_type` (team, league, player), `is_favorite` | M2 |

### 4.4 Odds comparison

| Event | Trigger | Key properties | MS |
|---|---|---|---|
| `odds_comparison_viewed` | Grid rendered | `sport`, `league`, `market_type`, `sportsbook_count`, `has_stale_data` | M1 |
| `odds_filter_changed` | Filter change | `filter` (sport, league, market, sportsbook), `value` | M1 |
| `odds_format_changed` | Format toggle | `from`, `to` (american, decimal, probability) | M1 |
| `odds_cell_inspected` | Hover/tap detail on a price | `market_type`, `is_best_line`, `is_stale` | M1 |
| `best_line_viewed` | Best-line highlight in viewport ≥ 1 s (once per market per session) | `market_type`, `league` | M1 |
| `odds_sent_to_calculator` | "Open in calculator" | `calculator` | M1 |
| `line_movement_viewed` | Movement chart opened | `market_type`, `range` | M2 |
| `sportsbook_link_clicked` | Outbound link | `sportsbook_id`, `is_affiliate`, `location` | M3 (if approved) |

### 4.5 Prop analyzer

| Event | Trigger | Key properties | MS |
|---|---|---|---|
| `props_list_viewed` | List rendered | `sport`, `league`, `result_count` | M1 |
| `props_filter_changed` | Filter change | `filter` (game, market, player), `value` (enum/ID; no free text) | M1 |
| `prop_player_viewed` | Player detail rendered | `player_id`, `league`, `market`, `sample_size`, `is_limited_sample` | M1 |
| `prop_market_changed` | Market switched | `from_market`, `to_market` | M1 |
| `prop_sample_window_changed` | Last-N window changed | `window` (5, 10, 20, season) | M1 |
| `methodology_link_clicked` | Any "how this is calculated" click | `location` | M1 |

### 4.6 Calculators

| Event | Trigger | Key properties | MS |
|---|---|---|---|
| `calculator_viewed` | Calculator opened | `calculator` (implied_probability, no_vig, ev, clv, parlay) , `entry_point` | M1 |
| `calculator_computed` | Valid result produced (debounced; once per distinct input set) | `calculator`, `is_prefilled`, `leg_count` (parlay only) | M1 |
| `calculator_input_error` | Validation error shown | `calculator`, `error_type` | M1 |

No input values are sent.

### 4.7 Parlay research

| Event | Trigger | Key properties | MS |
|---|---|---|---|
| `parlay_leg_added` | Leg added | `leg_type` (moneyline, spread, total, prop), `leg_count`, `entry_point` | M1 |
| `parlay_leg_removed` | Leg removed | `leg_count` | M1 |
| `parlay_computed` | ≥ 2 legs, totals shown | `leg_count`, `is_same_game`, `has_stale_leg` | M1 |
| `parlay_correlation_warning_shown` | Warning displayed | `warning_type` (same_game, same_player, conflicting), `leg_count` | M1 (verify) |
| `parlay_correlation_learn_more_clicked` | Warning help opened | — | M1 (verify) |
| `parlay_sent_to_tracker` | Hand-off confirmed | `leg_count` | M1 (verify) |

### 4.8 Bet tracker

| Event | Trigger | Key properties | MS |
|---|---|---|---|
| `tracker_viewed` | Tracker rendered | `bet_count_bucket`, `has_pending` | M1 |
| `bet_log_started` | Add-bet dialog opened | `entry_point` | M1 |
| `bet_logged` | Bet saved (server) | `source` (manual, sync, parlay_builder), `bet_type` (single, parlay), `market_type`, `sport`, `leg_count`, `stake_bucket` | M1 |
| `bet_settled` | Settlement saved (server) | `source`, `settle_method` (manual, auto), `bet_type`, `days_to_settle_bucket` — **no result or amount** | M1 |
| `bet_edited` / `bet_deleted` | Change saved (server) | `was_settled` | M1 |
| `tracker_range_changed` | Date range changed | `range` | M1 |
| `tracker_breakdown_viewed` | Breakdown tab opened | `dimension` (sport, sportsbook, market) | M1 |
| `tracker_exported` | CSV export | `row_count_bucket` | M2 |

`stake_bucket` values (proposal): `lt_10`, `10_49`, `50_199`, `200_plus` — used only for data-quality/UX analysis and RG research, never as a growth target. Bet outcome (win/loss) is deliberately **not** sent to analytics.

### 4.9 Sportsbook sync

| Event | Trigger | Key properties | MS |
|---|---|---|---|
| `sync_connect_started` | Consent screen opened | `provider_type` (mock, vendor) | M1 |
| `sync_consent_accepted` | Consent confirmed | `provider_type` | M1 |
| `sync_connect_completed` | Connection created (server) | `provider_type` | M1 |
| `sync_connect_failed` | Failure/cancel | `provider_type`, `reason` (user_cancelled, vendor_error, timeout) | M1 |
| `sync_run_completed` | Import finished (server) | `provider_type`, `imported_count_bucket`, `duplicate_count_bucket` | M1 |
| `sync_run_failed` | Import failed (server) | `provider_type`, `reason` | M1 |
| `sync_disconnected` | Disconnect (server) | `provider_type`, `is_data_deleted` | M1 |

No sportsbook name for real vendors unless counsel approves (could reveal where a user holds accounts); `mock` provider is exempt.

### 4.10 OddVex AI

| Event | Trigger | Key properties | MS |
|---|---|---|---|
| `assistant_opened` | Assistant view rendered | `entry_point` | M1 |
| `assistant_prompt_suggested_clicked` | Suggested prompt used | `prompt_id` | M1 |
| `assistant_message_sent` | User message submitted | `input_length_bucket`, `is_suggested` — **no text** | M1 |
| `assistant_response_delivered` | Answer returned (server) | `engine` (rules_v0, llm), `intent` (odds_lookup, best_line, prop_stats, calculator, tracker_summary, concept_explainer, unsupported, refusal, rg_support), `tool_count`, `is_grounded`, `has_stale_source`, `latency_bucket` | M1 |
| `assistant_unsupported` | No intent matched (server) | `nearest_intent` (enum or `none`) | M1 |
| `assistant_refusal` | Guarantee/pick/under-age refusal (server) | `refusal_type` | M1 |
| `assistant_rg_response_shown` | Crisis, under-21 or distress reply given (server) — **without `user_id`** | `case` (crisis, underage, distress) | M1 (proposed). **Not emitted.** What exists instead is a server log record, `assistant_support_reply`, written for each support reply with `case` and `signed_in` only (no message text, no user id; `services/api/src/oddvex_api/assistant/engine.py`) |
| `assistant_link_clicked` | Deep link in answer clicked | `destination` | M1 |
| `assistant_feedback_submitted` | Thumbs/report | `rating` (up, down), `reason` (enum) | M2 |

### 4.11 Data quality (server/system)

| Event | Trigger | Key properties | MS |
|---|---|---|---|
| `stale_data_shown` | A stale badge rendered to a user (sampled) | `data_type` (odds, score, stats), `age_bucket`, `route` | M1 |
| `data_error_shown` | Error state rendered | `data_type`, `route`, `error_class` | M1 |
| `feed_freshness_breached` | Feed exceeds stale threshold (server) | `feed`, `age_bucket` | M2 |

### 4.12 Reserved for later milestones

| Area | Events | MS |
|---|---|---|
| Alerts & notifications | `alert_created`, `alert_triggered`, `alert_deleted`, `push_permission_prompted`, `push_permission_result`, `notification_opened` | M3 |
| Premium | `paywall_viewed`, `checkout_started`, `subscription_started`, `subscription_renewed`, `subscription_cancel_started`, `subscription_cancelled`, `subscription_restored` (server-authoritative) | M4 |
| Community | `post_created`, `comment_created`, `content_reported`, `user_blocked`, `user_followed` | M5 |
| Mobile lifecycle | `app_opened`, `app_backgrounded`, `screen_viewed` (`screen_name`) | M1 (when analytics ships) |

## 5. Funnels

| # | Funnel | Steps |
|---|---|---|
| F1 | Acquisition → signup | `page_viewed` → `cta_clicked` → `signup_started` → `signup_completed` |
| F2 | Activation (first session) | `signup_completed` → first **research action** (see §6) within 24 h |
| F3 | Line shopping | `odds_comparison_viewed` → `odds_filter_changed` or `odds_cell_inspected` → `best_line_viewed` → (optional) `odds_sent_to_calculator` |
| F4 | Prop research | `props_list_viewed` → `prop_player_viewed` → `prop_market_changed` or `prop_sample_window_changed` |
| F5 | Tracker adoption | `tracker_viewed` → `bet_log_started` → `bet_logged` → `bet_settled` → `tracker_breakdown_viewed` |
| F6 | Sync | `sync_connect_started` → `sync_consent_accepted` → `sync_connect_completed` → `sync_run_completed` |
| F7 | Assistant | `assistant_opened` → `assistant_message_sent` → `assistant_response_delivered` (`is_grounded=true`, `intent≠unsupported`) → `assistant_link_clicked` |
| F8 | Parlay understanding | `parlay_leg_added` (×2) → `parlay_computed` → `parlay_correlation_warning_shown` → `parlay_correlation_learn_more_clicked` |
| F9 | Premium (M4) | `paywall_viewed` → `checkout_started` → `subscription_started` |
| F10 | Deletion (health check, not optimised for drop-off) | `account_deletion_requested` → `account_deletion_completed` |

## 6. North-star metric (proposal)

**Weekly Researching Users (WRU)** — the number of distinct authenticated users who complete **at least one research action** in a calendar week, with `data_mode = live`.

Research actions (qualifying events):

| Action | Qualifying event |
|---|---|
| Compared a line | `best_line_viewed` or `odds_cell_inspected` |
| Researched a prop | `prop_player_viewed` |
| Ran a calculation | `calculator_computed` |
| Analysed a parlay | `parlay_computed` |
| Recorded or reviewed results | `bet_logged`, `bet_settled`, or `tracker_breakdown_viewed` |
| Got a grounded answer | `assistant_response_delivered` with `is_grounded = true` and a supported intent |

Why this metric:
- Reflects the product's purpose (understanding the market and one's own record), not gambling volume.
- Works across all three personas, including users who never bet.
- Is not inflated by passive page views.

Until real data exists (`data_mode = synthetic`), WRU is tracked only as an instrumentation check, not as a business metric.

### Supporting metrics

| Type | Metric | Definition |
|---|---|---|
| Input | Activation rate | Share of new signups with ≥ 1 research action within 24 h |
| Input | Research breadth | Mean number of distinct research-action types per WRU per week |
| Input | Week-4 retention | Share of activated users who are WRU in their 4th week |
| Input | Tracker adoption | Share of WRU with ≥ 1 `bet_logged` in trailing 28 days |
| Quality | Stale exposure rate | `stale_data_shown` sessions ÷ data-viewing sessions |
| Quality | Assistant coverage | 1 − (`assistant_unsupported` ÷ `assistant_message_sent`) |
| Quality | Assistant grounding | Share of responses with `is_grounded = true` (must be 100 %; also enforced by tests) |
| Quality | Error exposure rate | `data_error_shown` sessions ÷ sessions |
| Business (M4) | Free → Premium conversion | Server-authoritative subscription events |

### Guardrails (must not be optimised; monitored for harm)

| Guardrail | Rule |
|---|---|
| Betting volume | No KPI, experiment success metric, or notification strategy may target stake size, bet count or frequency |
| RG signals | `rg_resource_clicked` and `assistant_rg_response_shown` (neither is emitted today; the server log record `assistant_support_reply` is the only signal that exists) are monitored in aggregate only; never used for targeting or marketing |
| Experiments | A/B tests may not vary RG messaging visibility downward, nor test urgency/pressure tactics |
| Deletion / cancellation | Completion rates are tracked to ensure flows work, never to add friction |

## 7. Governance

| Item | Rule |
|---|---|
| Tracking plan owner | Product |
| Adding an event | PR updating this document + typed event definition in the shared package; privacy review for any new property |
| Typed client | One shared, typed `track()` wrapper for web and mobile; unknown events/properties rejected in CI |
| QA | Events verified in staging before release; `data_mode` filter verified |
| Retention | ≤ 14 months (proposal; see PRIVACY_AND_DATA) |
| Deletion | User-linked events de-identified on account deletion |
| Access | Least privilege; no raw export to third parties |

## 8. Open questions

| # | Question | For |
|---|---|---|
| AN-Q1 | Analytics vendor (self-hosted vs. SaaS), cost and data location | Founder (G-02) |
| AN-Q2 | Consent model for marketing-site analytics; is authenticated-app analytics "necessary"/first-party under applicable laws? | Counsel (PR-06) |
| AN-Q3 | Is `stake_bucket` acceptable to collect at all, or should it be dropped? | Founder + counsel |
| AN-Q4 | Capture `state_region`? | Founder + counsel (PD-Q3) |
| AN-Q5 | Confirm WRU as north-star | Founder |
