# OddVex Competitor Matrix

- **Research date:** 2026-11-15 (all retrievals on this date)
- **Scope:** US-market betting-intelligence products (research, odds, EV, tracking). Competitors are functional benchmarks only.
- **Status:** Research input. Nothing here is a product commitment.

## How to read the tags (read this first)

| Tag | Meaning |
|---|---|
| **[Verified · official]** | Stated in content the web-search tool returned this session from the vendor's own site, help center or store listing. URL given. |
| **[Verified · 3P]** | Stated in content the web-search tool returned this session from a third party (price tracker, reviewer, competitor comparison page). URL given. Lower confidence; competitor-authored pages are flagged. |
| **[Assumption]** | General knowledge or inference. Not confirmed this session. |

**Important limitation.** Direct page fetching (WebFetch and curl) was blocked for every host by this session's network policy. "Verified" therefore means *the search tool read that URL and reported the statement this session*. I did not open any page myself, could not read full pricing tables, and could not see live in-app paywalls. Treat every price as "needs one human check on the live page before it is quoted anywhere". See `SOURCES.md` for the full list and for what could not be accessed.

Where sources disagree, both figures are shown rather than one being picked.

---

## 1. Comparison table

Legend: ● = present, ◐ = partial / gated / weak evidence, ○ = not found, ? = unknown. Each cell is backed by the section for that competitor; cells with no tag there are **[Assumption]**.

| Capability | BettingPros | Action Network | Outlier | Rithmm | OddsJam | Pikkit | Props.Cash | Juice Reel | Unabated | Linemate |
|---|---|---|---|---|---|---|---|---|---|---|
| Odds comparison | ● | ● (60+ books in Labs; prediction markets) | ● | ◐ | ● (100+ books) | ● (free line shopping) | ● (props, books + DFS) | ● (incl. SGP) | ● (sharp/market-maker books) | ● (parlay builder) |
| Props analyzer | ● (Prop Bet Analyzer) | ◐ (prop projections) | ● (core product) | ● (AI prop predictions) | ◐ (via EV/odds screen) | ○ | ● (core product) | ◐ (AI prop picks) | ● (Props Simulator) | ● (hit rates, trends) |
| Line movement | ◐ | ● (Labs detail; PRO alerts) | ● (Premium+ odds movement) | ? | ● (line movement history) | ◐ (odds alerts) | ? | ? | ● | ? |
| EV / arb tools | ◐ (EV metric on bets) | ◐ (signals, systems) | ● (EV in Premium+, arb/middles in Pro) | ○ | ● (EV, arb, middles, low hold) | ◐ (CLV; reviewer says no EV finder) | ○ | ◐ (CLV) | ● (Edge Tool, Unabated Line) | ○ |
| Bet tracker | ● | ● | ○ (not found) | ◐ (manual, per 3P) | ● (free) | ● (core product) | ○ | ● (core product) | ◐ (CLV calculator) | ◐ (My Picks tab) |
| Sportsbook sync | ● (complaints noted) | ● (BetSync, free) | ○ | ○ | ● (via SharpSports) | ● (30+ books, sync-only) | ○ | ● (300+ claimed) | ○ | ○ |
| AI assistant | ● (Sharp AI, Elite tier) | ● (Playbook) | ● (AI Analysis, token-metered) | ● (Scout; custom models) | ◐ (marketing mention only) | ? | ○ | ● (AI bots/picks) | ◐ (Gambly partnership) | ○ |
| Community / social | ◐ | ● (follow experts) | ○ | ◐ (Discord, model leaderboard) | ◐ (coaching in Platinum) | ● (follow/copy bets; Pro Discord) | ○ | ● (marketplace, group chat) | ● (Premium Discord, streams) | ○ |
| Alerts | ? | ● (PRO real-time) | ● (Premium) | ◐ (signals) | ● | ● (Pro odds alerts) | ? | ? | ● | ? |
| Backtesting / systems | ● (Betting Systems, Elite) | ● (PRO Systems; custom in Labs) | ○ | ● (custom model builder) | ○ | ○ | ○ | ○ | ◐ (simulators) | ○ |
| Platforms | iOS, Android, web | iOS, Android, web | iOS, web (Android ?) | iOS, Android | iOS, web (Android ?) | iOS, Android | iOS, web (Android ?) | iOS, web (Android ?) | Web (apps ?) | iOS, Android, web |
| Entry paid price (monthly) | $29.99 (Plus) | $24.99–$59.99 (conflicting) | $19.99 (Premium) | $29.99 (Core) | ~$199–$250 (conflicting) | $29.99 (Pro) | $19.99 | $8.99 IAP (unclear) | $199 (Premium); Basic tier exists | $14.99 ($9.99 also listed) |
| Free tier | Yes | Yes | Trial only (limited free web picks) | Trial only | Free tracker/tools; trial for paid | Yes (generous) | Trial only | Yes | Yes (Basic) | Yes |

---

## 2. Per-competitor detail

### 2.1 BettingPros (FantasyPros family)

| Field | Finding |
|---|---|
| Positioning | Mass-market research and picks hub with a props analyzer at the centre; consensus odds and expert picks. **[Verified · official]** https://www.bettingpros.com/premium/ |
| Platforms | iOS and Android apps plus web. **[Verified · official]** https://apps.apple.com/us/app/id1468109182 ; Android listing seen via tracker **[Verified · 3P]** https://apppricinglab.com/app/google_play/com.bettingpros.app.play |
| Core features | Prop Bet Analyzer (filter by hit rate, cover probability), Prop Bet Cheat Sheet, Parlay Builder, odds checker for spreads/totals/moneylines/futures. **[Verified · official]** https://apps.apple.com/us/app/id1468109182 |
| Sports | NFL, NBA, MLB, NHL, NCAAB, NCAAF, WNBA "and more". **[Verified · official]** same listing |
| Sportsbook sync | Syncs bets, balances and history from books incl. FanDuel, DraftKings, PrizePicks; sync is in the Free tier. **[Verified · official]** https://support.bettingpros.com/hc/en-us/articles/26544514477339-What-is-included-with-BettingPros-PLUS-and-ELITE-subscriptions . A SharpSports post titled "BettingPros adds bet tracking with SharpSports" indicates the sync vendor (title-level evidence only). **[Verified · official, title only]** https://sharpsports.io/post/bettingpros-adds-bet-tracking-with-sharpsports |
| Sync reliability | A third-party review audit (Mar 2026, 99 reviews) lists sync failures as the top complaint (e.g. DraftKings no longer syncing, no bet365). Single auto-generated source; weight lightly. **[Verified · 3P]** https://marlvel.ai/intel-report/sports/com-bettingpros-app |
| EV / sharp tools | Expected Value and Cover Probability metrics; "Smart Money insights" in Plus. **[Verified · official]** support article above |
| Props tooling | Hit-rate history, consensus line vs historical results, best odds across books. **[Verified · official]** https://blog.fantasypros.com/8-24-2022-bettingpros-prop-bet-analyzer/ (2022 article; may be dated) |
| AI | "Sharp AI" assistant, Elite tier only. **[Verified · official]** support article above |
| Backtesting | Betting Systems library, Elite only. Count conflicts: 14,000+ (help article) vs 29,000+ (pricing page). **[Verified · official]** https://www.bettingpros.com/premium/ |
| Community | Expert picks and consensus; no evidence of a user social feed. **[Assumption]** |
| Free vs paid | Free: consensus odds, select expert picks, Bet Ratings, EV, hit-rate history, player stats, sync. Plus: picks/projections on every prop, advanced metrics, bet analytics, expert analysis. Elite: Plus + Sharp AI, Betting Systems, higher API limits. Legacy "Premium" closed to new buyers. **[Verified · official]** https://support.bettingpros.com/hc/en-us/articles/7729645653275-What-are-the-different-premium-levels-and-subscription-lengths |
| Pricing | **Plus $29.99/mo or $119.99/yr; Elite $49.99/mo or $199.99/yr.** **[Verified · official]** https://support.bettingpros.com/hc/en-us/articles/26544095753371-How-much-does-your-premium-subscription-cost-What-plans-do-you-offer-How-to-Upgrade (retrieved 2026-11-15). Tracker shows legacy Premium $29.99/mo, $119.99/yr (snapshot 2026-05-16). **[Verified · 3P]** https://apppricinglab.com/iap/apple/1468109182 |

### 2.2 Action Network (Better Collective)

| Field | Finding |
|---|---|
| Positioning | Media-plus-tools brand: odds, public betting data, expert picks, free bet tracking; paid tier adds projections, signals and systems. **[Verified · official]** https://www.actionnetwork.com/ |
| Platforms | iOS, Android, web. **[Verified · official]** https://www.actionnetwork.com/app |
| Core features | Cross-book odds comparison, bet/money percentages, PRO Report, PRO Projections, PRO Systems, expert pick alerts (non-PRO users see a 30-minute delay). **[Verified · official]** https://actionnetworkhq.zendesk.com/hc/en-us/articles/14456167617805-Subscription-options |
| Prediction markets | Odds tools include Kalshi/Polymarket pricing; BetSync imports event-contract trades. **[Verified · official]** https://www.actionnetwork.com/education/action-network-betsync-prediction-markets-explained |
| Sportsbook sync | BetSync: one-way import, does not place bets, available in the free app. Named books include BetMGM and bet365; full current list not confirmed. **[Verified · official]** https://actionnetwork.com/betsync ; https://www.actionnetwork.com/betsync/bet365 |
| Bet tracker | Manual + sync tracking across books, parlays from screenshots. **[Verified · official]** https://www.actionnetwork.com/general/faq (page is old) |
| EV / sharp tools | Real-time betting signals, detailed line movement, custom systems, customizable odds board in **Action Labs**; Labs cites 60+ sportsbooks. **[Verified · official]** https://www.actionnetwork.com/press/introducing-action-labs |
| Props | Player prop projections in PRO. **[Verified · official]** https://apps.apple.com/us/app/action-network-sports-betting/id1083677479 |
| AI | **Playbook**: AI assistant that turns picks (text or screenshot) into a bet slip, works via X and Discord and the app; free with daily query limits, uncapped for PRO (as of Oct 2025). **[Verified · official]** https://www.actionnetwork.com/education/introducing-playbook-actions-image-to-bet-slip-bot ; **[Verified · 3P]** https://www.vegasinsider.com/sportsbooks/sports-betting-news/action-network-launches-playbook-ai-bot-for-sports-bettors/ |
| Community | Follow experts and their picks. **[Verified · official]** Subscription-options article above |
| Free vs paid | Free: odds, tracking, BetSync, delayed expert picks. PRO: projections, signals, systems, real-time alerts. Labs: PRO + custom systems and odds board. Whether public money % is free or paid conflicts between the FAQ and the store listing. **[Verified · official]** |
| Pricing | **Conflicting; treat as unconfirmed.** (a) Web pricing page shows $59.99/mo list price with promotional annual rates ($199.99 and $299 both appear on variants of the page). **[Verified · official]** https://www.actionnetwork.com/pricing . (b) US App Store tracker (Apr 2026): PRO Weekly $9.99, Monthly $24.99, 3-Month $59.99, Annual $119.99. **[Verified · 3P]** https://apppricinglab.com/iap/apple/1083677479 . Action Labs price: not found. |

### 2.3 Outlier

| Field | Finding |
|---|---|
| Positioning | Props-first research app that layers EV/arb tooling on top for higher tiers. **[Verified · official]** https://www.outlier.bet/ |
| Platforms | iOS app and web. **[Verified · official]** https://apps.apple.com/us/app/-/id6443885102 . Android: **[Assumption]** (not confirmed). |
| Core features | Player-prop insights, props and game research, injuries and matchups beside book prices, advanced visuals, odds tracking, real-time alerts. **[Verified · official]** https://help.outlier.bet/en/articles/12556823-choosing-the-right-outlier-plan-for-your-betting-style |
| Sportsbook sync / tracker | None found. **[Assumption]** (absence of evidence) |
| EV / sharp tools | Premium+: positive-EV indicators and odds movement. Pro: full +EV feed, sharp-book odds, arbitrage feed with stake suggestions, middles, boosted-parlay highlights. **[Verified · official]** same help article |
| AI | "AI Analysis" weighs trends, matchups, injuries and line movement for and against a line. Metered by tokens: 5 in trial, 5/mo Premium, 30/mo Premium+ (promotional). **[Verified · official]** https://www.outlier.bet/ |
| Live product | **React Live**, a separate subscription app for in-game signals (launched 2026-03-01); included with Pro. **[Verified · official]** https://www.outlier.bet/sports-betting-strategy/company-news/outlier-launches-react-live/ |
| Community | None found. **[Assumption]** |
| Free vs paid | No permanent free plan in-app; 7-day trial on each tier. Free web pages show 3 insights + 3 popular bets per book without an account. **[Verified · official]** https://www.outlier.bet/nfl-free-bets/ ; **[Verified · 3P, competitor]** https://www.oddsshopper.com/articles/comparisons/oddsshopper-vs-outlier |
| Pricing | **Premium $19.99/mo; Premium+ $29.99/mo ($299/yr early-bird); Pro $79.99/mo.** **[Verified · official]** help articles above and https://help.outlier.bet/en/articles/12159312-premium-launch-announcement . Annual via tracker (Mar 2026): $199.99 / $299.99 / $359.99. **[Verified · 3P]** https://apppricinglab.com/iap/apple/6443885102 . One third-party page cites $129.99/mo for Pro; unresolved. |

### 2.4 Rithmm

| Field | Finding |
|---|---|
| Positioning | "AI sports betting" app: model-driven predictions for props and games, with a user-facing custom model builder. **[Verified · official]** https://www.rithmm.com/ai-sports-betting |
| Platforms | iOS and Android. **[Verified · official]** https://apps.apple.com/us/app/rithmm/id1641010681 ; Android **[Verified · 3P]** https://www.nowsecure.com/marc-app/rithmm-ai-sports-betting-android/ |
| Core features | AI player-prop and game predictions, "Bolt Picks" (highest-confidence daily picks), "Smart Signals", parlays and DFS support; NFL, NBA, MLB, college. **[Verified · official]** App Store listing above |
| Custom models | Build models from 100+ stat factors (Premium), copy models from a public leaderboard, or have AI generate one; NFL/NBA player-adjustment tool in Premium. **[Verified · 3P, competitor]** https://statsniper.com/statsniper-vs-rithmm/ |
| AI assistant | "Scout" AI analyst in Pro and Premium, not Core. **[Verified · official]** https://www.rithmm.com/ai-sports-betting |
| Sync / tracker | Tracking appears manual, no sportsbook sync. **[Verified · 3P, competitor]** statsniper page above |
| EV / odds | No EV/arb tooling found; Rithmm positions itself against OddsJam as a model tool. **[Verified · official, title-level]** https://www.rithmm.com/post/rithmm-vs-oddsjam-which-sports-betting-tool-is-right-for-you |
| Transparency | Does not publish aggregate accuracy or ROI (per a review quoted by a competitor). **[Verified · 3P, competitor]** statsniper page above |
| Community | Discord and social, not in-app. **[Verified · 3P, competitor]** same |
| Free vs paid | Free download; 7-day trial, card required, one per user. **[Verified · official]** |
| Pricing | **Core $29.99/mo or $239.99/yr; Pro $49.99/mo; Premium $99.99/mo or $999.99/yr.** **[Verified · official]** https://www.rithmm.com/ai-sports-betting (retrieved 2026-11-15). Some App Store storefronts show different amounts (e.g. Core $34.99). |

### 2.5 OddsJam

| Field | Finding |
|---|---|
| Positioning | Profit-oriented "sharp" toolkit: +EV, arbitrage and middles scanners on a fast odds screen. Priced for users who expect the tool to pay for itself. **[Verified · official]** https://oddsjam.com/betting-tools |
| Platforms | Web and iOS. **[Verified · official]** https://apps.apple.com/app/id6448072108 . Android: **[Assumption]**. |
| Core features | Odds screen (100+ books, main/alt markets, props), line movement history, custom weighted consensus with alerts. **[Verified · official]** https://oddsjam.com/subscribe/sportsbooks-screen |
| EV / sharp tools | Positive EV, arbitrage, middles, low holds, promo converter, live bets with auto refresh, 1:1 coaching (Platinum). Sharp Money tier detects unusually large bets. **[Verified · official]** https://oddsjam.com/lp/ads/zeke-platinum ; https://oddsjam.com/betting-tools/sharp-money |
| Bet tracker / sync | Free tracker, auto-grading, CLV; sync **through SharpSports** (DraftKings, FanDuel, BetMGM, Caesars, PrizePicks and others named; articles are several years old). **[Verified · official]** https://oddsjam.com/betting-education/how-to-sync-sportsbooks-with-oddsjam-bet-tracker |
| AI | Only a marketing line on the fantasy product ("AI-powered bets"); no documented assistant. **[Verified · official]** https://fantasy.oddsjam.com/ |
| B2B | Sells an odds API. **[Verified · official]** https://oddsjam.com/odds-api |
| Free vs paid | Free tracker and calculators; 7-day trial on paid plans; no permanent free tier for scanners found. **[Verified · official]** https://oddsjam.com/betting-tools/positive-ev |
| Pricing | **Conflicting.** Platinum $499.99/mo (promo: 50% off first month; page dated Sep 2026). **[Verified · official]** https://oddsjam.com/lp/ads/zeke-platinum . Positive EV Global $399.99/mo. **[Verified · official]** https://oddsjam.com/subscribe/positive-ev-global . Fantasy Optimizer $69/mo. **[Verified · official]** https://oddsjam.com/subscribe/fantasy . Sharp Money ~$6.60–$8/day billed monthly (stale page). **[Verified · official]** https://oddsjam.com/subscribe . App Store: Gold $199.99, Positive EV Monthly $499.99. **[Verified · 3P]** https://apppricinglab.com/app/apple/6448072108 . Third-party "$49/mo" claims are from auto-generated pages and are not credible. |

### 2.6 Pikkit

| Field | Finding |
|---|---|
| Positioning | Social bet tracker built on automatic sportsbook sync; analytics upsell. Reported 600,000+ users. **[Verified · official]** https://pikkit.com/ ; user count **[Verified · 3P]** https://opticodds.com/blog/how-you-bet-the-big-game-super-bowl-lx-betting-trends |
| Platforms | iOS and Android. **[Verified · official]** https://apps.apple.com/us/app/pikkit-sports-betting-tracker/id1586567110 ; Android **[Verified · 3P]** https://www.similarweb.com/app/google/com.pikkit.android/ |
| Sportsbook sync | "BookSync": 30+ sportsbooks and DFS sites, read-only (cannot place bets or move funds). **No manual entry** (sync only). **[Verified · official]** https://pikkit.com/pro ; manual-entry point **[Verified · 3P, competitor]** https://statsniper.com/statsniper-vs-pikkit/ |
| Sync vendor | Integrated OpticOdds' "odds and bet-tracking API". **[Verified · 3P, vendor case study]** https://opticodds.com/customers/pikkit |
| Free tier | Unlimited sync and tracking, line shopping, community features. **[Verified · official]** https://pikkit.com/pro |
| Pro features | CLV analysis (benchmark selectable: best available, no-vig fair odds, custom books, own book), scenario analysis, SGP line shopping, odds alerts, promo tracking, exposure tracking, private Discord; "20+ premium features". **[Verified · official]** https://pikkit.com/pro ; https://pikkit.com/closing-line-value |
| EV tools | A user review says Pro does not include an EV finder. **[Verified · 3P]** App Store review via listing above |
| Community | Follow friends/influencers, view and copy their bets (free). **[Verified · 3P, competitor]** statsniper page above |
| AI | None found. **[Assumption]** |
| Pricing | **Pro $29.99/mo or $199.99/yr, 7-day trial.** **[Verified · official]** https://pikkit.com/pro (retrieved 2026-11-15). Tracker agrees (snapshot 2026-05-09). **[Verified · 3P]** https://apppricinglab.com/iap/apple/1586567110 . An older review cites $39.99/$299.99. |

### 2.7 Props.Cash

| Field | Finding |
|---|---|
| Positioning | Single-purpose player-prop research tool; explicitly not a picks service and does not take wagers. **[Verified · official]** https://apps.apple.com/us/app/props-cash-prop-pick-finder/id1606752641 |
| Platforms | iOS and web. **[Verified · official]** listing above; https://classic.props.cash/ . Android: **[Assumption]**. |
| Core features | Hit rates (L5/L10/L20 per user reviews), matchup grades, trends, splits, opponent data, player correlations, sort by matchup grade. **[Verified · official]** listing above |
| Odds comparison | Prop lines and odds compared across sportsbooks and DFS sites. **[Verified · official]** listing above |
| Sports | Listing: NFL, NBA, WNBA, NHL, NCAA, MLB. Website adds EPL, MLS, CSGO. **[Verified · official]** https://classic.props.cash/ |
| Sync / tracker / EV / AI / community | None found. **[Assumption]** |
| Pricing | **All Sports $19.99/mo or $199.99/yr; NFL or NBA season pass $99.99; 7-day trial.** **[Verified · 3P]** https://adapty.io/paywall-library/props-cash/ (paywall capture, date unknown); trial **[Verified · official]** App Store listing. |

### 2.8 Juice Reel

| Field | Finding |
|---|---|
| Positioning | Free synced bet tracker that monetises through a verified picks marketplace and AI pick bots. **[Verified · official]** https://www.juicereel.com/blog/what-is-juice-reel |
| Platforms | iOS and web app. **[Verified · official]** https://apps.apple.com/us/app/juice-reel-bet-tracker-tips/id1527960097 ; https://app.juicereel.com/marketplace . Android: **[Assumption]**. |
| Sportsbook sync | Claims 300+ sportsbooks and DFS sites, automatic import. Vendor claim, unverified; it is 10x Pikkit's stated count and may count differently. **[Verified · official]** App Store listing above |
| Tracker analytics | Profit, ROI and CLV by sport, team, market, bet type. **[Verified · 3P, competitor]** https://statsniper.com/statsniper-vs-juice-reel/ |
| Odds | Best-odds and SGP odds comparison. **[Verified · official]** listing above |
| AI | AI pick bots with public records; flagship bot from $24.99/week; single picks unlockable with in-app points; some AI picks free. AI page cites 40M+ synced bets analysed. **[Verified · official]** https://www.juicereel.com/ai-player-props-today-best-ai-player-prop-bets-and-picks/ |
| Community | Marketplace where handicapper records are verified from synced accounts; sellers keep 50% (80% on self-referred subs). Group chat and livestreaming. **[Verified · 3P]** https://marlvel.ai/api/llm/apps/sports/com-juiceintegration-juicereel ; listing above |
| Free vs paid | Core app free; "premium datapoints" cost extra. **[Verified · official]** blog page above |
| Pricing | IAPs: "Juice Plus" $8.99, Profile Access $1.99–$49.99. **[Verified · 3P]** https://apppricinglab.com/app/apple/1527960097 . No official pricing page found. Note: "$7.99 Pro / $19.99 Unlimited" figures that appear near Juice Reel in search results belong to Stat Sniper, not Juice Reel. |

### 2.9 Other competitors discovered

| Product | What it is | Price evidence | Notes |
|---|---|---|---|
| **Unabated** | Sharp-bettor toolkit: odds screen with market-maker books, proprietary vig-free "Unabated Line", Edge Tool, calculators, NFL/CFB futures and player-props simulators, Premium Discord and livestreams. **[Verified · official]** https://unabated.com/post/benefits-of-unabated-premium-membership | **Premium $199/mo or $1,584/yr.** **[Verified · official]** same URL (page ~July 2026). Free Basic tier keeps hold and CLV calculators and recreational books. | Also sells APIs (see data doc). Works with Gambly (AI betting chatbot); a third party calls it a merger, Unabated's pages show a partnership. **[Verified · official]** https://unabated.com/odds-api/free |
| **Linemate** | Beginner-friendly research app: "Discover" feed of data-backed plays, hit rates, trend analysis, cross-book parlay builder, My Picks tab; added prediction-market analytics in v2.2.0 (Sep 2026). **[Verified · official]** https://apps.apple.com/us/app/linemate-find-your-next-bet/id1635246793 ; changelog via APK mirror **[Verified · 3P]** | **$14.99/mo, $59.99/yr; free tier.** **[Verified · official]** https://linemate.io/pricing . App Store also lists a $9.99 monthly. | Cheapest credible paid tier in the set. Data from OpticOdds. **[Verified · 3P, vendor case study]** https://opticodds.com/customers/linemate |
| **DarkHorse Odds** | Self-described matched-betting software; "Bet Finders" show best price across the user's books; free calculators (hedge, arb, parlay, promo); demo and free trial. **[Verified · official]** https://about.darkhorseodds.com/guides/what-we-offer | Not found. | Reviews prediction-market venues (Kalshi) alongside sportsbooks. |
| **OddsShopper** | Odds shopping + "Portfolio EV" tool; free tier plus OS Core and OS Pro. **[Verified · official]** https://www.oddsshopper.com/articles/comparisons/oddsshopper-vs-outlier | Not stated on its own pages; one blog says $99/mo. **[Verified · 3P]** https://nuropicks.vercel.app/blog/2026-ai-sports-betting-landscape | 7-day trial. |
| **Stat Sniper** | Newer AI analytics app with "Chad" AI chat, prop tracker, injury feed, community; free tier includes one AI "Quick Take" per game and limited chat. **[Verified · official]** https://statsniper.com/pricing/ | Pro $7.99/mo or $76.90/yr. **[Verified · official]** https://apps.apple.com/us/app/stat-sniper/id6479165781 . Pro Plus $19.99/mo. **[Verified · 3P]** https://www.saasworthy.com/product/stat-sniper/pricing | Aggressive comparison-page SEO against every incumbent. Sets a very low AI price anchor. |
| **SharpStack (4for4)** | +EV scanner, arbitrage finder, pick'em tools, bet tracker. **[Verified · official]** https://www.4for4.com/sharpstack-landing | $79/mo (+EV tool), $99 tier, $499/yr; lifetime option mentioned. **[Verified · official]** same | Mid-priced EV alternative. |
| **PlayerProps.ai** | AI props app. | $59.99/mo, $499.99/yr. **[Verified · official]** https://apps.apple.com/app/id6502717388 | Not researched further. |
| **PropsMadness** | Prop research tool, free tier. | $25/mo or $250/yr. **[Verified · 3P]** https://www.bettoredge.com/post/propsmadness-review | Not researched further. |
| **Oddschecker+** | Odds comparison with an EV tool. | $29.99/mo (Dec 2024 article). **[Verified · official, dated]** https://www.oddschecker.com/us/insight/promotions/20241206-oddscheckerplus-holiday-sale | Price may have changed. |
| PrizePicks-adjacent optimizers, Optimal, DGF, others | Not researched this session. | — | **[Assumption]** that a long tail of DFS pick'em optimizers exists. |

---

## 3. Patterns worth noting

1. **Sync is free everywhere it exists.** BettingPros, Action Network, Pikkit, OddsJam and Juice Reel all give tracking/sync away and charge for analysis on top. **[Verified]** (sections above)
2. **AI assistants are now common but shallow or metered.** Sharp AI (Elite only), Playbook (free, capped), Outlier AI Analysis (token allowance), Rithmm Scout (mid tier and up), Stat Sniper Chad (free, capped). None was found publishing accuracy or calibration data. **[Verified]** for existence; **[Assumption]** for "none publish calibration".
3. **Prediction markets are being folded into betting tools** (Action Network odds and BetSync, Linemate analytics, Unabated free API, DarkHorse reviews). **[Verified]**
4. **Price bands are clearly separated:** research $15–$30/mo, AI-model $30–$100/mo, EV/arb $80–$500/mo. **[Verified]** (see `PRICING_RESEARCH.md`)
5. **Nobody in the set clearly combines** props research, honest AI explanation, EV context and a synced tracker with CLV in one affordable product. BettingPros and Action Network come closest on breadth. **[Assumption]** (synthesis)
