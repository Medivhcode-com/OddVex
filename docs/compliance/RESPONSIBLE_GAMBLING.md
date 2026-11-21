# OddVex — Responsible Gambling Policy and Product Commitments

Last updated: 2026-11-21 · Status: internal policy draft; public wording on `/responsible-gambling` requires counsel review before launch. Sections 2, 4 and 5 describe the code at commit `2b0c7c1`.

> Not legal or clinical advice. Helpline details must be re-verified before each release. They were last checked on
> 2026-11-19 against the National Council on Problem Gambling's own pages.

## 1. Position

OddVex is an information and analytics product for adults 21+. It does not accept or place wagers. Because our content relates to gambling, we accept a responsibility to present it in a way that supports informed, controlled decisions and never encourages anyone to bet more, more often, or beyond their means.

Sports betting involves risk of financial loss. No tool, statistic or assistant answer on OddVex removes that risk or predicts outcomes.

## 2. Help resources (must appear in product)

Verified on 2026-11-19 against the National Council on Problem Gambling's pages; check again before each release.
In the code the facts live in one module per app: `services/api/src/oddvex_api/helpline.py`
(`HELPLINE_VERIFIED_ON`), `apps/web/src/lib/site.ts` (`HELPLINE`) and `apps/mobile/src/helpline.ts`. An API test
(`services/api/tests/test_audit_helpline.py`) fails if another API text spells a helpline number out.

| Resource | Detail | Where shown (code at `2b0c7c1`) |
|---|---|---|
| **National Problem Gambling Helpline (US)** | **1-800-MY-RESET (1-800-697-3738)**. Call, or text 800GAM (800426). Confidential, 24 hours a day, every day. In service under this number since 2026-01-29. Online chat on the Council's site | Web: marketing footer, app shell (every width), `/responsible-gambling`, Settings, the tracker's "Log a bet" panel and the "Sportsbook sync" panel. Mobile: Settings, the tracker (every state) and the sync panel. API texts: assistant answers and disclaimers, the staking-reminder notification, the email footer, the community guidelines |
| Not an emergency service | In a crisis: call or text **988** (Suicide and Crisis Lifeline) or call **911** | `/responsible-gambling`; mobile Settings; the assistant's crisis, distress and under-21 replies and the help sentence at the end of every answer that is not a support reply (988 only) |
| National Council on Problem Gambling | ncpgambling.org (front page only; deeper addresses move) | `/responsible-gambling`; mobile Settings |
| Gamblers Anonymous / Gam-Anon | Peer support | Not shown in the product today |
| State-specific helplines and self-exclusion programmes | Vary by state; list to be compiled and verified with counsel | `/responsible-gambling` says some states publish their own helpline and that state regulators run self-exclusion programmes; no state is listed |

**1-800-GAMBLER is not the national helpline.** It is the line of the Council on Compulsive Gambling of New Jersey.
1-800-MY-RESET has been in service since 2026-01-29; what the national helpline used before then is not verified here. The product gave the New Jersey number until the fixes of 2026-11-19 and
2026-11-21. In the code at `2b0c7c1` it appears on screen only on `/responsible-gambling`, in one sentence naming it as the
New Jersey council's line.

Standard short line, as built: **"21+. OddVex does not take wagers. Gambling problem? Call 1-800-MY-RESET
(1-800-697-3738)."** (`RESPONSIBLE_GAMBLING_LINE` in `apps/web/src/lib/site.ts` and `apps/mobile/src/helpline.ts`.)
State-specific wording may be required for advertising — to be confirmed by counsel (AD-02).

## 3. Policy commitments

| # | Commitment |
|---|---|
| RG-P1 | **21+ only.** No marketing to, or design for, minors. Accounts credibly identified as under 21 are closed and their data deleted. |
| RG-P2 | **No guarantees.** We never state or imply that a bet will win, is safe, is "risk-free", or is a "lock". |
| RG-P3 | **No inducement.** We do not push users to bet, bet more, chase losses, or act urgently. No countdown pressure, streak rewards, or loss-recovery messaging. |
| RG-P4 | **Honest results.** Losses are shown as clearly as wins. We do not hide, soften or delay negative results. |
| RG-P5 | **Probability alongside payout.** Wherever a potential payout is shown, the implied probability is shown too. |
| RG-P6 | **Gambling is not income.** We do not present betting as a way to make a living, solve financial problems, or invest. |
| RG-P7 | **Help is always one tap away.** RG resources are reachable from every screen via the footer or settings. |
| RG-P8 | **RG features are never paywalled.** |
| RG-P9 | **Metrics.** We do not set product goals on amount wagered, bet count, or deposit behaviour. |
| RG-P10 | **Advertising partners.** If OddVex ever works with sportsbooks, only state-licensed operators, and never promotions using "risk-free"-type language. |
| RG-P11 | **Respect for exits.** Account deletion, notification opt-outs and (later) time-outs are easy and never obstructed. |

## 4. Product commitments by area

| Area | Commitment | Milestone | Status |
|---|---|---|---|
| Global | RG short line with 21+ and the national helpline on the web app shell (every width) and the marketing footer | M1 | Built (web). Mobile shows it in Settings, on the tracker and on the sync panel; not reported as seen on a device |
| Signup | 21+ attestation required | M1 | Built: the API refuses registration without it and stores the time only |
| Marketing | `/responsible-gambling` page; banned-claims list enforced | M1 | Page built. Banned phrases are checked by tests on notification templates, community copy, marketing copy and assistant replies; no full copy audit |
| Settings | RG resources section | M1 | Built. Web: the helpline with call and text links and a link to `/responsible-gambling`. Mobile: the helpline with call and text links, the not-an-emergency sentence with a "Call 988" link, and a link to the Council's site |
| Odds / props | Neutral presentation; "best line" is a price fact, not a recommendation; prop history labelled non-predictive | M1 | In M1 scope |
| Calculators | EV depends on user's estimate — stated; no "profit guaranteed" framing; arbitrage/hedge tools (M2) carry practical-risk notes | M1/M2 | In M1 scope / planned |
| Parlay | Break-even rate next to payout; correlation warning; no "boost your payout" framing | M1 | Built: the parlay tool shows the combined price, the payout and the break-even rate (how often the parlay must win). It does **not** show a combined probability that every leg wins: at `2b0c7c1` the screen shows "Combined probability: Not shown", which pull request 20 replaces with a plain statement. Same-game warning built |
| Tracker | Plain P/L; no celebratory animations for wins; no "win it back" prompts | M1 | In M1 scope |
| Assistant | Refuses guarantees/picks; detects crisis, under-21 and distress language and responds with support resources instead of betting data; every answer that is not a support reply ends with the helpline and 988 | M1 | Built as fixed rules with known misses (section 5) |
| Notifications | No promotional betting inducements; user-set alerts only; quiet hours; easy opt-out | M3 | Built in-app only: user-set alerts, per-kind opt-out, a banned-phrase test on every template. No quiet hours, no push, no email |
| RG tools | Optional: session reminders, self-set review reminders, account time-out ("take a break"), net-result summaries | M3 | Planned — design with RG expertise |
| Bankroll calculator | Only after RG review of framing | M3 | Planned |
| Community | Guidelines ban pick-selling, guaranteed claims, pressure to bet, mocking losses; leaderboards only if RG review approves | M5 | Built behind the `community` switch, off. Draft guidelines served by the API. Leaderboard behind a second switch, off; it orders by win rate regardless of price, which needs a decision first (`docs/backlog/owner-questions.md`) |
| Premium | No marketing of Premium as a way to win more; no paywalled RG features | M4 | Planned |

## 5. Assistant behaviour rules (RG-specific)

The table is the specification. The column on the right says what the code at `2b0c7c1` does
(`services/api/src/oddvex_api/assistant/safeguards.py`, run in `Assistant.route()` before any other routing).

| Trigger (examples) | Required behaviour | As built |
|---|---|---|
| "I can't stop betting", "I've lost everything", "I need to win it back" | Stop providing betting data in that reply; acknowledge without judgement; provide the national helpline and link to `/responsible-gambling` | **Distress** reply: "Thank you for telling me", no prices, the helpline sentence, the weekly staking reminder and the bet tracker described as tools ("a reminder, not a limit"), and the crisis sentence (988, 911). Suggestions link to `/responsible-gambling`, Settings and the tracker. Intent `support`, `support.case` `distress` |
| Language suggesting self-harm or crisis | Provide 988 Suicide and Crisis Lifeline and the national helpline; encourage reaching out to someone now | **Crisis** reply, and nothing else: an acknowledgement, "Call or text 988 … If you are in immediate danger, call 911", "tell someone you trust", then the gambling helpline, and a line saying it is an automated helper. Threats against other people that the rules catch get the same reply ("I'm going to kill him", "I want to hurt someone"); others are missed: "im going to shoot up my school" gets an ordinary answer with the help sentence and without 911 |
| "What's a sure thing / lock?" | Explain no outcome is certain; offer market data only | Fixed refusal: no result is certain, no picks or predictions, market data offered instead. Intent `fallback`, not a support case |
| "How much should I bet to recover my losses?" | Decline; explain chasing losses is a recognised warning sign; provide resources | Part of the distress reply: "I can't help size or pick a bet to win money back. Trying to win back losses is a recognised warning sign …" |
| User indicates being under 21 | State that OddVex is 21+ only; do not provide betting information; flag per AG-03 process | **Under-21** reply: "OddVex is for adults 21 and over, so I can't give odds, prices or any other betting information here", the helpline sentence and the crisis sentence. **The AG-03 flag is not built**: nothing is stored against the account, no flag is set and no account is closed. The only trace is one `assistant_support_reply` log line (case `underage`, signed in or not; no message text, no user id), in the same container log as the request line for that call, so the two can be matched by time. On the preview the request line holds the address of the shared reverse proxy or the web server, not the user's (`infrastructure/RUNBOOK.md` section 3), and the assistant writes no audit row; whether the shared reverse proxy's own logs hold the user's address was not inspected (not verified). The logs have no retention rule |

Order when several apply: crisis, then under 21, then distress. The replies are fixed wording in the module, so no
pluggable explainer can reword them.

**Every answer that is not a support reply** (ordinary answers, the fallback, the refusal and every "couldn't find" answer) ends with the
help sentence: "If gambling is causing problems, call the National Problem Gambling Helpline at 1-800-MY-RESET
(1-800-697-3738) or text 800GAM; in a crisis, call or text 988 (the Suicide and Crisis Lifeline)." This is the safety
net for messages the rules miss.

**Known misses.** Detection is a fixed list of rules, not a classifier, and it misses some wordings. Every review found
new ones. The misses known at release `2b0c7c1` are listed in `KNOWN_MISSES` in
`services/api/tests/test_audit_assistant_detection.py` (for example "gonna end it with sleeping pills"). Others were
found afterwards and are not in that list, for example the threat "im going to shoot up my school". A missed crisis
message or threat gets an ordinary answer with the help sentence and without 911. The rules also show help for some ordinary messages on purpose (`HELP_SHOWN_ANYWAY`). A
sturdier list would need a reviewed sample of real missed messages, which means storing what users type: a privacy
decision for the Founder and counsel. Today no message text is stored; each support reply writes one log record,
`assistant_support_reply`, holding only the case and whether the person was signed in.

The web and mobile chat screens show these replies as ordinary answers at `2b0c7c1`; a distinct support card with
tappable numbers is being added in pull request 20. The mobile app drops the `/responsible-gambling` link (the numbers
are in the answer text).

An LLM-backed version (M4) must include these cases in its evaluation suite (AI-08). None of this has been reviewed by
counsel or a responsible-gambling specialist (decision D-024).

## 6. Marketing rules (summary; full list in `docs/marketing/BRAND_VOICE.md`)

- Never: "risk-free", "guaranteed", "lock", "can't lose", "easy money", "beat the books", "get rich".
- Never depict betting as a solution to financial difficulty, as a rite of passage, or as essential to enjoying sport.
- No imagery or channels with primary appeal to under-21s.
- Include the RG line on all marketing assets (state-specific variants to be confirmed by counsel).

## 7. Warning signs we publish (draft content for `/responsible-gambling`; to be reviewed against NCPG materials)

- Betting more than you can afford to lose
- Chasing losses
- Hiding betting from family or friends
- Borrowing or selling things to bet
- Feeling anxious, irritable or restless when not betting
- Betting to escape problems or relieve negative feelings
- Neglecting work, study or relationships because of betting

## 8. Governance

| Item | Owner | Cadence |
|---|---|---|
| RG copy review of new features | Product + compliance docs | Every release |
| Helpline/resource verification | Compliance docs | Before each release |
| RG review gate for: notifications, bankroll tools, leaderboards, promotions | Founder + (ideally) external RG adviser | Before build |
| Metrics guardrail audit (no volume-based targets) | Product | Quarterly once analytics exist |

## 9. Open questions

| # | Question | For |
|---|---|---|
| RG-Q1 | Are state-specific helpline numbers/wording required on our surfaces or ads? | Counsel |
| RG-Q2 | Should OddVex offer a self-exclusion style account lock, and what obligations would follow? | Counsel / Founder |
| RG-Q3 | Engage an external RG organisation or adviser for review (cost)? | Founder |
| RG-Q4 | Are sportsbook-style RG obligations triggered if we become an affiliate? | Counsel |
