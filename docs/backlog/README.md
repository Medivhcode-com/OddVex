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
| P0.1 | Snapshot archive | 0 | — | not created | Not started | — |
| P0.2 | Calculation provenance | 0 | — | not created | Not started | — |
| P0.3 | Entitlements | 0 | — | not created | Not started | — |
| P0.4 | Profile settings | 0 | — | not created | Not started | — |
| P0.5 | Provider interfaces with synthetic fixtures | 0 | — | not created | Not started | — |
| P0.6 | Copy guard and suppression hook | 0 | — | not created | Not started | — |
| F01 | Check My Bet | 1 | P0.1, P0.2 | not created | Not started | — |
| F02 | Sync & Settlement Inbox | 1 | — | not created | Not started | — |
| F03 | Leak Report | 1 | P0.1, F02 | not created | Not started | — |
| F04 | Today | 1 | — | not created | Not started | — |
| F05 | Records Pack & Tax Center | 1 | — | not created | Not started | — |
| F06 | Dollar View | 1 | — | not created | Not started | — |
| F07 | Tap to Explain | 1 | P0.2 | not created | Not started | — |
| F08 | Clear Mode | 1 | — | not created | Not started | — |
| F09 | Consensus Stress Test | 1 | — | not created | Not started | — |
| F10 | Trend Stress Test | 1 | — | not created | Not started | — |
| F11 | Quiet Mode | 1 | — | not created | Not started | — |
| F12 | Open Scorecards | 1 | — | not created | Not started | — |
| F13 | Plain-English Market Search | 1 | — | not created | Not started | — |
| F14 | Import-First Setup | 1 | — | not created | Not started | — |
| F15 | Bet Tags & Source Scorecard | 1 | — | not created | Not started | — |
| F16 | State & Coverage | 2 | P0.4, P0.5 | not created | Not started | — |
| F17 | Lineup Check & Line Move Notes | 2 | — | not created | Not started | — |
| F18 | Sweat Screen | 2 | — | not created | Not started | — |
| F19 | Luck or Skill | 2 | — | not created | Not started | — |
| F20 | Cash-Out Checker | 2 | — | not created | Not started | — |
| F21 | Worst-Case Map | 2 | — | not created | Not started | — |
| F22 | Research Receipts | 2 | P0.1 | not created | Not started | — |
| F23 | Plan Mode | 2 | F11 | not created | Not started | — |
| F24 | Season Pass & Pause | 2 | — | not created | Not started | — |
| F25 | Limit Log | 2 | — | not created | Not started | — |
| F26 | SGP True Cost | 2 | — | not created | Not started | — |
| F27 | Same Bet? | 2 | P0.5 | not created | Not started | — |
| F28 | Soccer Market Translator | 2 | F27 | not created | Not started | — |
| F29 | Price Sense Trainer | 2 | F07 | not created | Not started | — |
| F30 | Book Gap Report | 2 | F03 | not created | Not started | — |
| F31 | Research Workspaces | 3 | — | not created | Not started | — |
| F32 | Alt-Line Pricer | 3 | — | not created | Not started | — |
| F33 | Context Cohorts | 3 | — | not created | Not started | — |
| F34 | Historical Replay | 3 | P0.1 | not created | Not started | — |
| F35 | Settlement Evidence Packs | 3 | F02, F27 | not created | Not started | — |
| F36 | Bettor Rights Desk | 3 | F25, F35 | not created | Not started | — |
| F37 | Model Sandbox | 3 | — | not created | Not started | — |
| F38 | Verified Creator Pages | 3 | — | not created | Not started | — |
| F39 | Tax Pro Connect | 3 | F05 | not created | Not started | — |
| F40 | Event-Contract Translator | 4 | — | not created | Not started | — |
| F41 | OddVex for Sheets | 4 | — | not created | Not started | — |
| F42 | OddVex for Discord | 4 | F01 | not created | Not started | — |
| F43 | Publisher Explainer Cards | 4 | — | not created | Not started | — |
| F44 | Market Data Quality Monitor | 4 | — | not created | Not started | — |
