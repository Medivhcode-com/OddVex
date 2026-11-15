# OddVex — Responsible Gambling Policy and Product Commitments

Last updated: 2026-11-15 · Status: internal policy draft; public wording on `/responsible-gambling` requires counsel review before launch.

> Not legal or clinical advice. Helpline details must be re-verified before each release.

## 1. Position

OddVex is an information and analytics product for adults 21+. It does not accept or place wagers. Because our content relates to gambling, we accept a responsibility to present it in a way that supports informed, controlled decisions and never encourages anyone to bet more, more often, or beyond their means.

Sports betting involves risk of financial loss. No tool, statistic or assistant answer on OddVex removes that risk or predicts outcomes.

## 2. Help resources (must appear in product)

| Resource | Detail | Where shown |
|---|---|---|
| **National Problem Gambling Helpline (US)** | **1-800-GAMBLER** (call; text/chat options to be verified before launch) | Global footer (web, marketing), mobile settings, `/responsible-gambling`, assistant distress responses, sync and tracker screens' help links |
| National Council on Problem Gambling | ncpgambling.org | `/responsible-gambling` |
| Gamblers Anonymous / Gam-Anon | Peer support | `/responsible-gambling` |
| State-specific helplines and self-exclusion programmes | Vary by state; list to be compiled and verified with counsel | `/responsible-gambling` (M2) |
| Crisis support | 988 Suicide & Crisis Lifeline (call or text 988) | `/responsible-gambling`; assistant responses to crisis language |

Standard footer line: **"21+. OddVex does not accept wagers. Gambling problem? Call 1-800-GAMBLER."**
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
| Global | RG footer with 21+ and 1-800-GAMBLER on web app, marketing site | M1 | In M1 scope |
| Signup | 21+ attestation required | M1 | M1 — verify |
| Marketing | `/responsible-gambling` page; banned-claims list enforced | M1 | In M1 scope |
| Settings | RG resources section | M1 | M1 — verify |
| Odds / props | Neutral presentation; "best line" is a price fact, not a recommendation; prop history labelled non-predictive | M1 | In M1 scope |
| Calculators | EV depends on user's estimate — stated; no "profit guaranteed" framing; arbitrage/hedge tools (M2) carry practical-risk notes | M1/M2 | In M1 scope / planned |
| Parlay | Combined probability next to payout; correlation warning; no "boost your payout" framing | M1 | In M1 scope (warning: verify) |
| Tracker | Plain P/L; no celebratory animations for wins; no "win it back" prompts | M1 | In M1 scope |
| Assistant | Refuses guarantees/picks; detects distress language and responds with support resources instead of betting data | M1 | In M1 scope (rule-based keyword detection; limits acknowledged) |
| Notifications | No promotional betting inducements; user-set alerts only; quiet hours; easy opt-out | M3 | Planned |
| RG tools | Optional: session reminders, self-set review reminders, account time-out ("take a break"), net-result summaries | M3 | Planned — design with RG expertise |
| Bankroll calculator | Only after RG review of framing | M3 | Planned |
| Community | Guidelines ban pick-selling, guaranteed claims, pressure to bet, mocking losses; leaderboards only if RG review approves | M5 | Planned |
| Premium | No marketing of Premium as a way to win more; no paywalled RG features | M4 | Planned |

## 5. Assistant behaviour rules (RG-specific)

| Trigger (examples) | Required behaviour |
|---|---|
| "I can't stop betting", "I've lost everything", "I need to win it back" | Stop providing betting data in that reply; acknowledge without judgement; provide 1-800-GAMBLER and link to `/responsible-gambling` |
| Language suggesting self-harm or crisis | Provide 988 Suicide & Crisis Lifeline and 1-800-GAMBLER; encourage reaching out to someone now |
| "What's a sure thing / lock?" | Explain no outcome is certain; offer market data only |
| "How much should I bet to recover my losses?" | Decline; explain chasing losses is a recognised warning sign; provide resources |
| User indicates being under 21 | State that OddVex is 21+ only; do not provide betting information; flag per AG-03 process |

Rule-based detection in M1 will miss cases; this is a known limitation. LLM-backed version (M4) must include these cases in its evaluation suite (AI-08).

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
