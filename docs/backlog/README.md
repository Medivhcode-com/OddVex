# Feature backlog: how to work on it

The Founder supplied a 50-idea backlog on 2026-11-19: 6 foundations and 44 build items (six overlapping pairs of ideas
were merged). A later session resumes from this folder and from Linear.

- `BUILD_PROMPT.md`: the Founder's prompt, verbatim. Its process (steps 1 to 5), its six hard rules, the stop list and
  the definition of done apply to every item.
- `feature-backlog.md`: the scope of every item and its "Done when" lines. The source of truth for scope.
- `orientation.md`: where each already-built feature lives in the code, and which items will touch it.
- `owner-questions.md`: questions only the Founder can answer.
- `../features/<item>.md`: one document per finished item.

## Rules that are easy to forget

1. One item at a time, in ID order. The repository is green before the next item starts.
2. One pull request into `main` per item. This repository's build session works on a single branch, so each item is a
   new pull request from that branch after the previous one has merged.
3. Every item sits behind its own feature flag, default off, and is gated by the entitlement in its Tier.
4. Every "Done when" line becomes a test that fails first.
5. Everything runs on synthetic fixtures. Connecting a real provider is an owner decision.
6. An item that needs anything on the stop list is not built past its interface: log the question and move on.

## Progress

Status values: Not started, In progress, Merged, Blocked (with the owner question).

| Item | Name | Phase | Needs | Ticket | Status | Pull request |
|---|---|---|---|---|---|---|
| P0.1 | Snapshot archive | 0 | — | [MED-72](https://linear.app/medivh-code-team/issue/MED-72/p01-snapshot-archive) | Not started | — |
| P0.2 | Calculation provenance | 0 | — | [MED-73](https://linear.app/medivh-code-team/issue/MED-73/p02-calculation-provenance) | Not started | — |
| P0.3 | Entitlements | 0 | — | [MED-74](https://linear.app/medivh-code-team/issue/MED-74/p03-entitlements) | Not started | — |
| P0.4 | Profile settings | 0 | — | [MED-75](https://linear.app/medivh-code-team/issue/MED-75/p04-profile-settings) | Not started | — |
| P0.5 | Provider interfaces with synthetic fixtures | 0 | — | [MED-76](https://linear.app/medivh-code-team/issue/MED-76/p05-provider-interfaces-with-synthetic-fixtures) | Not started | — |
| P0.6 | Copy guard and suppression hook | 0 | — | [MED-77](https://linear.app/medivh-code-team/issue/MED-77/p06-copy-guard-and-suppression-hook) | Not started | — |
| F01 | Check My Bet | 1 | P0.1, P0.2 | [MED-80](https://linear.app/medivh-code-team/issue/MED-80/f01-check-my-bet) | Not started | — |
| F02 | Sync & Settlement Inbox | 1 | — | [MED-78](https://linear.app/medivh-code-team/issue/MED-78/f02-sync-and-settlement-inbox) | Not started | — |
| F03 | Leak Report | 1 | P0.1, F02 | [MED-81](https://linear.app/medivh-code-team/issue/MED-81/f03-leak-report) | Not started | — |
| F04 | Today | 1 | — | [MED-79](https://linear.app/medivh-code-team/issue/MED-79/f04-today) | Not started | — |
| F05 | Records Pack & Tax Center | 1 | — | [MED-82](https://linear.app/medivh-code-team/issue/MED-82/f05-records-pack-and-tax-center) | Not started | — |
| F06 | Dollar View | 1 | — | [MED-83](https://linear.app/medivh-code-team/issue/MED-83/f06-dollar-view) | Not started | — |
| F07 | Tap to Explain | 1 | P0.2 | [MED-84](https://linear.app/medivh-code-team/issue/MED-84/f07-tap-to-explain) | Not started | — |
| F08 | Clear Mode | 1 | — | [MED-85](https://linear.app/medivh-code-team/issue/MED-85/f08-clear-mode) | Not started | — |
| F09 | Consensus Stress Test | 1 | — | [MED-86](https://linear.app/medivh-code-team/issue/MED-86/f09-consensus-stress-test) | Not started | — |
| F10 | Trend Stress Test | 1 | — | [MED-87](https://linear.app/medivh-code-team/issue/MED-87/f10-trend-stress-test) | Not started | — |
| F11 | Quiet Mode | 1 | — | [MED-88](https://linear.app/medivh-code-team/issue/MED-88/f11-quiet-mode) | Not started | — |
| F12 | Open Scorecards | 1 | — | [MED-89](https://linear.app/medivh-code-team/issue/MED-89/f12-open-scorecards) | Not started | — |
| F13 | Plain-English Market Search | 1 | — | [MED-90](https://linear.app/medivh-code-team/issue/MED-90/f13-plain-english-market-search) | Not started | — |
| F14 | Import-First Setup | 1 | — | [MED-91](https://linear.app/medivh-code-team/issue/MED-91/f14-import-first-setup) | Not started | — |
| F15 | Bet Tags & Source Scorecard | 1 | — | [MED-92](https://linear.app/medivh-code-team/issue/MED-92/f15-bet-tags-and-source-scorecard) | Not started | — |
| F16 | State & Coverage | 2 | P0.4, P0.5 | [MED-93](https://linear.app/medivh-code-team/issue/MED-93/f16-state-and-coverage) | Not started | — |
| F17 | Lineup Check & Line Move Notes | 2 | — | [MED-94](https://linear.app/medivh-code-team/issue/MED-94/f17-lineup-check-and-line-move-notes) | Not started | — |
| F18 | Sweat Screen | 2 | — | [MED-95](https://linear.app/medivh-code-team/issue/MED-95/f18-sweat-screen) | Not started | — |
| F19 | Luck or Skill | 2 | — | [MED-96](https://linear.app/medivh-code-team/issue/MED-96/f19-luck-or-skill) | Not started | — |
| F20 | Cash-Out Checker | 2 | — | [MED-97](https://linear.app/medivh-code-team/issue/MED-97/f20-cash-out-checker) | Not started | — |
| F21 | Worst-Case Map | 2 | — | [MED-98](https://linear.app/medivh-code-team/issue/MED-98/f21-worst-case-map) | Not started | — |
| F22 | Research Receipts | 2 | P0.1 | [MED-99](https://linear.app/medivh-code-team/issue/MED-99/f22-research-receipts) | Not started | — |
| F23 | Plan Mode | 2 | F11 | [MED-100](https://linear.app/medivh-code-team/issue/MED-100/f23-plan-mode) | Not started | — |
| F24 | Season Pass & Pause | 2 | — | [MED-101](https://linear.app/medivh-code-team/issue/MED-101/f24-season-pass-and-pause) | Not started | — |
| F25 | Limit Log | 2 | — | [MED-102](https://linear.app/medivh-code-team/issue/MED-102/f25-limit-log) | Not started | — |
| F26 | SGP True Cost | 2 | — | [MED-103](https://linear.app/medivh-code-team/issue/MED-103/f26-sgp-true-cost) | Not started | — |
| F27 | Same Bet? | 2 | P0.5 | [MED-104](https://linear.app/medivh-code-team/issue/MED-104/f27-same-bet) | Not started | — |
| F28 | Soccer Market Translator | 2 | F27 | [MED-105](https://linear.app/medivh-code-team/issue/MED-105/f28-soccer-market-translator) | Not started | — |
| F29 | Price Sense Trainer | 2 | F07 | [MED-106](https://linear.app/medivh-code-team/issue/MED-106/f29-price-sense-trainer) | Not started | — |
| F30 | Book Gap Report | 2 | F03 | [MED-107](https://linear.app/medivh-code-team/issue/MED-107/f30-book-gap-report) | Not started | — |
| F31 | Research Workspaces | 3 | — | [MED-108](https://linear.app/medivh-code-team/issue/MED-108/f31-research-workspaces) | Not started | — |
| F32 | Alt-Line Pricer | 3 | — | [MED-109](https://linear.app/medivh-code-team/issue/MED-109/f32-alt-line-pricer) | Not started | — |
| F33 | Context Cohorts | 3 | — | [MED-110](https://linear.app/medivh-code-team/issue/MED-110/f33-context-cohorts) | Not started | — |
| F34 | Historical Replay | 3 | P0.1 | [MED-111](https://linear.app/medivh-code-team/issue/MED-111/f34-historical-replay) | Not started | — |
| F35 | Settlement Evidence Packs | 3 | F02, F27 | [MED-112](https://linear.app/medivh-code-team/issue/MED-112/f35-settlement-evidence-packs) | Not started | — |
| F36 | Bettor Rights Desk | 3 | F25, F35 | [MED-113](https://linear.app/medivh-code-team/issue/MED-113/f36-bettor-rights-desk) | Not started | — |
| F37 | Model Sandbox | 3 | — | [MED-114](https://linear.app/medivh-code-team/issue/MED-114/f37-model-sandbox) | Not started | — |
| F38 | Verified Creator Pages | 3 | — | [MED-115](https://linear.app/medivh-code-team/issue/MED-115/f38-verified-creator-pages) | Not started | — |
| F39 | Tax Pro Connect | 3 | F05 | [MED-116](https://linear.app/medivh-code-team/issue/MED-116/f39-tax-pro-connect) | Not started | — |
| F40 | Event-Contract Translator | 4 | — | [MED-117](https://linear.app/medivh-code-team/issue/MED-117/f40-event-contract-translator) | Not started | — |
| F41 | OddVex for Sheets | 4 | — | [MED-118](https://linear.app/medivh-code-team/issue/MED-118/f41-oddvex-for-sheets) | Not started | — |
| F42 | OddVex for Discord | 4 | F01 | [MED-119](https://linear.app/medivh-code-team/issue/MED-119/f42-oddvex-for-discord) | Not started | — |
| F43 | Publisher Explainer Cards | 4 | — | [MED-120](https://linear.app/medivh-code-team/issue/MED-120/f43-publisher-explainer-cards) | Not started | — |
| F44 | Market Data Quality Monitor | 4 | — | [MED-121](https://linear.app/medivh-code-team/issue/MED-121/f44-market-data-quality-monitor) | Not started | — |
