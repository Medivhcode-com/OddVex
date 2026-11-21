# OddVex — User Journeys

Last updated: 2026-11-21 (assistant edge cases checked against the code at commit `2b0c7c1`) · Screens reference [SCREEN_MAP.md](./SCREEN_MAP.md) · Events reference `docs/marketing/ANALYTICS_EVENT_TAXONOMY.md`

Notes:
- Personas: P1 Curious Fan (Casey), P2 Recreational Bettor (Riley), P3 Serious Bettor (Sam).
- All M1 journeys run on **synthetic data with fictional teams, players and sportsbooks**. Example names below are fictional.
- "Success metrics" are **definitions to measure**, not targets or results. No baselines exist yet.
- OddVex never places a bet in any journey.

| # | Journey | Persona | Milestone |
|---|---|---|---|
| J1 | First visit → signup with 21+ attestation | P1/P2 | M1 |
| J2 | Compare a line | P2/P3 | M1 |
| J3 | Research a player prop | P2 | M1 |
| J4 | Compute EV | P3 | M1 |
| J5 | Log and settle a bet | P2 | M1 |
| J6 | Review performance | P2/P3 | M1 |
| J7 | Connect a sportsbook (mock) | P2 | M1 |
| J8 | Ask OddVex AI | P1/P2 | M1 |
| J9 | Build a parlay with correlation warning | P1/P2 | M1 (warning: verify) |
| J10 | Delete account and data | any | M2 (verify whether pulled into M1) |

---

## J1 — First visit → signup with 21+ attestation

**Goal:** understand what OddVex is and create an account. **Entry:** `/` or a feature page.

| Step | User action | System response |
|---|---|---|
| 1 | Lands on `/` | Hero with tagline, "OddVex does not accept or place wagers", illustrative (fictional) UI, RG footer |
| 2 | Reads `/features` or a feature page | Features labelled "available" vs. "planned" |
| 3 | Clicks "Get started" | `/signup` |
| 4 | Enters email + password | Inline validation; password requirements shown up front |
| 5 | Ticks "I confirm I am 21 or older" and accepts Terms/Privacy | Submit enabled only when both are ticked |
| 6 | Submits | Account created; attestation + document versions + timestamp stored; session started; redirect to `/app` |
| 7 | Sees dashboard | Demo-data banner; quick actions; empty tracker state |

**Failure / edge states**

| Case | Behaviour |
|---|---|
| Attestation not ticked | Submission blocked with explicit message; no account created |
| User states they are under 21 (if asked directly in future DOB flow) | Block; neutral message; no retry loop that coaches a different answer (design with counsel) |
| Email already registered | Generic response that does not confirm account existence |
| Weak password | Inline requirement feedback |
| Rate limit hit | "Too many attempts, try again later" |
| Network/API error | Form preserved (except password), retry |
| No email verification in M1 | Acknowledged gap; AUTH-04 in M2 before real users |

**Success metrics:** visit → signup-start rate; signup-start → signup-complete rate; attestation-block rate; share of new users completing one research action in first session (activation).

---

## J2 — Compare a line

**Goal:** find the best price for a market. **Entry:** `/app/odds` or a game detail.

| Step | User action | System response |
|---|---|---|
| 1 | Opens Odds | Grid loads with default sport and main markets; "as of" shown |
| 2 | Filters league and market (e.g. spread) | Grid updates; filter state reflected in URL |
| 3 | Scans a game row | Best price per outcome highlighted with icon + label |
| 4 | Toggles odds format | All prices convert consistently |
| 5 | Checks no-vig row | Fair probability and hold % for that market |
| 6 | Optional: "Open in calculator" / "Add to parlay" | Prefilled tool or leg added |

**Failure / edge states:** stale price (dimmed, excluded from best line); market not offered at a book ("—"); all books stale ("No current prices — last updated {time}"); filters yield nothing (clear-filters action); tie for best price (all tied highlighted); line differs across books (e.g. −3.5 vs −3) — grid shows both line and price so "best" is not misread on price alone.

**Success metrics:** share of sessions with an odds comparison interaction; time to first best-line view; filter usage; stale-data exposure rate (data-quality metric).

---

## J3 — Research a player prop

**Goal:** see how a player has performed against a prop line. **Entry:** `/app/props` or game detail.

| Step | User action | System response |
|---|---|---|
| 1 | Opens Props; searches a player | Matching prop rows with line, best prices, recent hit rate n/N |
| 2 | Opens player detail | Chart of last-N results vs. current line; game log table |
| 3 | Switches market (e.g. points → rebounds) | Chart, hit rate and prices update |
| 4 | Compares prices across books | Best over/under price highlighted |
| 5 | Reads note | "Historical results, not a prediction" with sample size |
| 6 | Optional: add to parlay | Leg added |

**Failure / edge states:** limited sample (no rate shown, "limited sample"); no history ("No game history available"); prop removed by sportsbook ("No longer offered" with last-seen time); unknown player ID (not found); stale stats badge.

**Success metrics:** prop detail views per researching user; market-switch rate; share of prop views followed by price comparison; "methodology" link click-through.

---

## J4 — Compute EV

**Goal:** calculate expected value from the user's own probability estimate. **Entry:** `/app/tools`.

| Step | User action | System response |
|---|---|---|
| 1 | Opens Tools → EV | Inputs: odds, stake, user's estimated win probability |
| 2 | Enters odds (e.g. +120) | Implied probability shown live (45.45 %) |
| 3 | Enters own probability and stake | EV in currency and % of stake; break-even probability |
| 4 | Opens "How this is calculated" | Formula + link to `/methodology` |
| 5 | Optional: uses no-vig tool first | Fair probability from a two-way market to inform the estimate |

Formula shown: `EV = p × profit_if_win − (1 − p) × stake`.

**Failure / edge states:** invalid American odds (between −100 and +100); probability outside 0–100; blank fields (no result, no NaN); very large stake (validate, no overflow); explicit note that EV depends entirely on the user's estimate and is not a forecast.

**Success metrics:** calculator completion rate (valid result produced); calculators used per researching user; repeat use within 7 days.

---

## J5 — Log and settle a bet

**Goal:** record a bet placed elsewhere and settle it. **Entry:** `/app/tracker`.

| Step | User action | System response |
|---|---|---|
| 1 | Clicks "Log a bet" | Dialog: sportsbook, sport, market, selection, odds, stake, date |
| 2 | Fills and saves | Bet appears as Pending; potential payout computed; summary "pending" count updates |
| 3 | Later: opens bet → "Settle" | Options: win / loss / push / void / cash-out (amount) |
| 4 | Chooses outcome | Bet marked settled; P/L, ROI and record update |
| 5 | Optional: adds closing odds | CLV computed for that bet |

**Failure / edge states:** save fails (toast + retry; form retained); duplicate submission (idempotent); edit after settlement (recalculate; edited marker); settle mistake (re-open/unsettle); cash-out amount missing; future-dated or impossible dates validated; deleting a bet asks for confirmation.

**Success metrics:** share of users logging ≥ 1 bet; share of logged bets that get settled; time from log to settle; edit/unsettle rate (usability signal).

---

## J6 — Review performance

**Goal:** understand actual results honestly. **Entry:** `/app/tracker` or dashboard snapshot.

| Step | User action | System response |
|---|---|---|
| 1 | Opens Tracker | Tiles: net P/L, ROI, record, pending — settled bets only |
| 2 | Changes date range | Tiles, chart and breakdowns update |
| 3 | Views breakdown by sport/book/market | Table with count, stake, P/L, ROI per group |
| 4 | Views results-over-time chart | Cumulative net result with table alternative |
| 5 | Reviews CLV where available | Average CLV with number of bets it's based on |

**Failure / edge states:** no settled bets ("Settle a bet to see results"); tiny sample (show n; avoid implying significance); negative results shown plainly, same visual weight as positive; mixed synced/manual bets (source filter).

**Success metrics:** weekly tracker review rate among users with ≥ 1 bet; breakdown usage. **RG guardrail:** never optimise for stake volume; watch for patterns to inform TRKR-10.

---

## J7 — Connect a sportsbook (mock)

**Goal:** import bets automatically. In M1 this is a **demo** using the mock adapter. **Entry:** Tracker → "Connect sportsbook".

| Step | User action | System response |
|---|---|---|
| 1 | Clicks "Connect sportsbook" | Consent screen: what is imported, what is not; "Demo connection — no real sportsbook is contacted" |
| 2 | Chooses a fictional sportsbook | Mock link flow (no credential fields) |
| 3 | Confirms | Connection created; status "Connected (demo)"; import starts |
| 4 | Waits | Synthetic bets imported; marked "Synced (demo)"; last-synced time shown |
| 5 | Reviews tracker | Summaries include synced bets; duplicates with manual entries flagged for merge |
| 6 | Optional: disconnects | Connection removed; imports stop; (M2) choice to keep or delete synced bets |

**Failure / edge states:** simulated sync failure (error banner + retry); partial import (count shown); duplicate detection uncertain (ask the user, don't auto-merge); user cancels at consent (nothing stored).

**Real vendor (M3) differences:** vendor-hosted authentication; OddVex receives tokens only; expired connection → re-link; vendor outage state; consent copy reviewed by counsel.

**Success metrics:** connect-start → connect-complete rate; sync error rate; duplicate-prompt rate; disconnect rate.

---

## J8 — Ask OddVex AI

**Goal:** get an answer grounded in verified data. **Entry:** `/app/assistant`.

| Step | User action | System response |
|---|---|---|
| 1 | Opens Assistant | Intro, AI disclosure ("automated assistant; rule-based in this version; demo data"), suggested prompts |
| 2 | Asks "What's the best price on the Harbor City moneyline?" (fictional team) | Router maps to odds tool; answer lists best price, sportsbook, "as of", link to `/app/odds` |
| 3 | Asks "What does −110 imply?" | Calculator tool: 52.38 % with formula link |
| 4 | Asks "How am I doing this month?" | Tracker tool: user's own settled-bet summary |
| 5 | Asks "Who will win tonight?" | No prediction: shows market prices/implied probabilities and states OddVex does not predict outcomes |

**Failure / edge states**

| Case | Behaviour |
|---|---|
| Unsupported question | "I can't answer that yet" + supported examples; **no guess** |
| Tool returns no data | "I don't have data for that" |
| Stale source data | Answer carries stale chip and time |
| Ambiguous entity | Clarifying question with options |
| Request for guaranteed pick / "lock" | Refusal with explanation; offers data instead. As built: a fixed reply saying no result is certain |
| User expresses distress or loss of control about gambling | Supportive response with the National Problem Gambling Helpline, 1-800-MY-RESET (1-800-697-3738), and a link to `/responsible-gambling`; no betting data. As built: a fixed distress reply (helpline, staking reminder, tracker, 988 and 911) |
| User mentions self-harm or crisis, or threatens someone | As built: a fixed crisis reply with 988 and 911 first, then the gambling helpline, and nothing else |
| User says they are under 21 | As built: "OddVex is for adults 21 and over", no betting information, the helpline and the crisis line. Nothing is recorded (the AG-03 flag is not built) |
| Any other answer | As built: ends with the helpline and 988, because the rules above are a fixed list and miss some wordings (`KNOWN_MISSES` in `services/api/tests/test_audit_assistant_detection.py`) |
| Attempt to get other users' data or override rules | Refuse; only requesting user's data is ever read |

**Success metrics:** share of questions answered from a tool (vs. unsupported); unsupported-intent log (drives roadmap); helpfulness rating (M2); grounding test pass rate in CI (must be 100 %).

---

## J9 — Build a parlay with correlation warning

**Goal:** understand combined price, probability and correlation risk. **Entry:** `/app/parlay` or "Add to parlay".

| Step | User action | System response |
|---|---|---|
| 1 | Adds leg 1 (team moneyline) | Leg listed with odds and implied probability |
| 2 | Adds leg 2 (player prop from the **same game**) | Combined odds, payout for entered stake, combined implied probability (independence assumed) |
| 3 | — | **Correlation warning:** "These legs are from the same game and may be correlated. The combined figures assume independent legs and may not reflect true probability. Sportsbooks may price or restrict this combination differently." |
| 4 | Adds leg 3 from another game | Totals update; warning remains for the related pair |
| 5 | Reviews per-leg breakdown | Each leg's contribution; combined probability shown next to payout |
| 6 | Optional: "Send to tracker" | Prefilled multi-leg bet (pending) after the user confirms they placed it elsewhere |

**Failure / edge states:** single leg ("add at least two"); contradictory legs (e.g. both sides of the same market) → flagged as conflicting; duplicate leg blocked; leg price went stale ("price may have changed"); leg's game started/finished → flagged; max leg count reached (limit set by engineering).

**Success metrics:** parlay builds with ≥ 2 legs; share of builds showing a correlation warning; warning "learn more" click-through; send-to-tracker rate.

---

## J10 — Delete account and data

**Goal:** permanently delete the account and associated data. **Milestone:** M2 (AUTH-06) — required before any real user; confirm whether pulled into M1. **Entry:** `/app/settings` (and in-app on mobile).

| Step | User action | System response |
|---|---|---|
| 1 | Settings → "Delete account" | Explains what is deleted (profile, bets, sync connections and synced data, assistant history, preferences), what may be retained and why (see PRIVACY_AND_DATA), and that it is irreversible |
| 2 | Optional: "Export my data" first | Download of user's data (machine-readable) |
| 3 | Confirms by re-entering password | Re-authentication check |
| 4 | Final confirm | Sessions revoked; sync connections revoked at vendor; deletion job queued; confirmation shown |
| 5 | — | Data removed from primary stores within the committed window; purged from backups per backup rotation; (M4+) note that store-billed subscriptions must be cancelled in the store |

**Failure / edge states:** wrong password (blocked; rate-limited); deletion job failure (retried, alert to operators, user not told "done" until done); active subscription (clear guidance; M4); vendor revoke fails (retry queue; logged); user changes mind after final confirm (no undo unless a grace period is adopted — decision for Founder/counsel).

**Success metrics:** deletion completion time (request → primary-store purge); deletion job failure rate; support contacts about deletion. No retention-style "win-back" friction is permitted in this flow.
