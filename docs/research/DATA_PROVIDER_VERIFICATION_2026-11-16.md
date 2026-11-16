# Data-provider verification — 2026-11-16

Supplement to DATA_PROVIDER_EVALUATION.md; original figures are not automatically current. Official pricing, full licence terms and documentation were opened directly. No trial, paid plan or data connection was activated in this work.

## Procurement recommendation

Provisional choice: The Odds API 5M-credit plan at USD 119 per month for a bounded odds MVP. Written clarification of OddVex's paid comparison/analytics use and a confirmed spending/payment route remain required before purchase. This plan does not establish complete player game-log or injury coverage.

| Vendor | Current official pricing | Relevant licence finding |
| --- | --- | --- |
| The Odds API | Free 500 credits/month; 20K USD 30; 100K USD 59; 5M USD 119; 15M USD 249 monthly | Commercial UI display, derived analytics and indefinite storage are permitted subject to the restriction that data is not the primary product sold. Standalone raw-data resale/API/feed/download redistribution is prohibited. |
| SportsGameOdds | Rookie USD 149 monthly or USD 99/month annually; Pro USD 499 monthly or USD 299/month annually | An end-user application must add independent material value; raw redistribution is prohibited. Terms generally require deletion of vendor data within 30 days after termination. |
| SportsDataIO | Commercial pricing is quoted for the selected feeds, leagues and use case | Discovery Lab is personal/noncommercial. A production commercial agreement, attribution and retention rights must be agreed for OddVex's actual use. Unsupported third-party USD 5K estimates are not verified prices. |

Official sources: https://the-odds-api.com/ ; https://the-odds-api.com/terms-and-conditions.html ; https://sportsgameodds.com/pricing ; https://sportsgameodds.com/terms ; https://sportsdata.io/help/data-rights-and-licensing-questions .

## Corrections to the earlier evaluation

The Odds API does provide scores/results for covered sports, including recent completed games. It publishes refresh intervals: featured markets update every 60 seconds pregame and 40 seconds in play; props update every 60 seconds. These are published provider intervals, not a measured OddVex SLA. Player game logs and injuries were not established in the V4 documentation.

Sources: https://the-odds-api.com/liveapi/guides/v4/ ; https://the-odds-api.com/sports-odds-data/update-intervals.html .

## Illustrative capacity, not approved launch scope

Assume one shared ingestion schedule, five-minute polling, 30 days, one US region, three leagues, at most 20 active prop events and eight prop markets per event. Cache data centrally; do not poll separately for every user.

| Workload assumption | Monthly credits |
| --- | ---: |
| Three leagues × three featured markets | 77,760 |
| At most20 events × eight prop markets | 1,382,400 |
| Three leagues' scores, including completed games | 51,840 |
| Base total | 1,512,000 |
| Optional history/retry reserve | 250,000 |
| Planned ceiling | 1,762,000 |

Ordinary odds credit cost depends on markets × regions; event props are charged by returned unique markets × regions. Historical requests have a 10× multiplier; scores requests with completed games cost two credits. This example exceeds the 100K plan. Enforce event/market caps and alert before the plan quota is exhausted.

## Prepared licence question — unsent

> May OddVex display your odds in a paid web, iOS and Android sports research product with odds comparison, independent analytics, tracking and research explanations, without raw-data APIs or odds exports? Please confirm this satisfies the restriction on data being the primary product sold. Please clarify third-party LLM processing, stored line-history display after cancellation, sportsbook naming/logo rights and any additional commercial fee.

The vendor publishes team@the-odds-api.com as its contact. A draft is saved in the founder's Gmail; no licence reply exists.

An older provider key-issuance email was found. That establishes prior issuance only, not current account entitlement or a commercial agreement. Its key appeared in a returned email preview during the account check. Do not reuse or copy it; rotate it in the provider dashboard and use secure credential entry for the replacement. No secret value is retained in this repository.
