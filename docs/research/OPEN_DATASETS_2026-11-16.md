# Open datasets for OddVex — 2026-11-16

- **Status:** research input only. Nothing here is approved for display. No account was created, no API key used, no
  sportsbook site contacted, nothing purchased. This is not legal advice.
- **Scope:** historical results, player game logs, historical odds and reference data that can be obtained without
  scraping and without a paid contract. Live odds are out of scope (see `DATA_PROVIDER_VERIFICATION_2026-11-16.md`).
- **Tags:** **[V-direct]** = I fetched the licence/terms file itself this session with `curl` through the session proxy.
  **[V-search]** = the web-search tool returned that statement from the named URL this session; the page itself could
  not be opened. **[Assumption]** = not confirmed this session.
- **Network limits:** the session proxy only allowed `raw.githubusercontent.com` and public `github.com` release
  downloads. Every other host tried returned a proxy 403 on CONNECT and was not retried or routed around
  (section 4). `WebFetch` was deliberately not used on refused hosts.

## 1. Summary

Open data can fully cover an **internal replay/demo and results-based backtesting** for NFL and MLB, and can cover
soccer results, but it cannot cover the product's core odds needs. The strongest find is the nflverse schedule file
(CC BY 4.0): every NFL game 1999–2026 with final score and a closing spread and total, plus moneylines and prices
from 2006 — but it is one unnamed consensus line, not multi-book. Retrosheet (free for commercial use with a credit
line) and the Chadwick Bureau derivatives cover MLB results, player game-by-game lines and ids. openfootball
(public domain) and a CC0 internationals file cover soccer results without odds. NBA and NHL have no cleanly licensed
open source: the SportsDataverse releases are labelled CC BY 4.0 but are compiled from ESPN / NBA / NHL endpoints whose
terms restrict commercial reuse, so they are for internal testing only. The best free soccer-odds archive
(football-data.co.uk) and every free US odds archive found could not have their terms read here and need written
permission before use. Multi-book closing lines, line history, player props, injuries and anything live require a
licensed API. Ten sample files (13.5 MB) were saved under `data/external/` and are git-ignored.

## 2. Comparison table

Verdicts: **Usable now** (licence read, permits commercial use; still behind gate G-12 and counsel) ·
**Internal testing only** · **Needs written permission** · **Not usable**.

| # | Source | Contains | Licence / key term | Commercial use | Automated download | Verdict | Sample saved |
|---|---|---|---|---|---|---|---|
| 1 | nflverse-data releases | NFL schedules + results 1999–2026 with closing spread/total/moneyline; player-week stats; rosters | CC BY 4.0 **[V-direct]**; sister README says data "belong to their respective owners" **[V-direct]** | Licence allows; upstream ownership unclear | Yes — releases exist for programmatic download **[V-direct]** | **Internal testing only** (promote after counsel) | Yes |
| 2 | Retrosheet (retrosheet.org) | MLB game logs, box scores, play-by-play; coverage years **[Assumption]** | Own notice: any use incl. commercial, with credit line **[V-search]**; credit line **[V-direct]** via Chadwick mirror | Allowed | Publisher offers zip/CSV downloads **[V-search]** | **Usable now** | Via #3 (host blocked) |
| 3 | Chadwick `retrosplits` | MLB player and team game-by-game lines derived from Retrosheet | ODbL 1.0 + DbCL 1.0 + Retrosheet credit **[V-direct]** | Allowed; share-alike on derived databases | Yes (public GitHub) | **Usable now** (mind share-alike) | Yes |
| 4 | Chadwick Register | Baseball person ids: MLBAM, Retrosheet, BBRef, FanGraphs keys, names | ODC-BY 1.0 **[V-direct]** | Allowed | Yes | **Usable now** | Yes |
| 5 | Lahman database (SABR) | MLB season-level batting/pitching/teams 1871–2025 | CC BY-SA 3.0 **[V-search]**, not on SABR's own page | Allowed; share-alike | Download page **[V-search]** | **Usable now**, low value (no game level) | No (host blocked) |
| 6 | MLB Stats API / gdx.mlb.com | MLB schedules, box scores, live feeds | "Only individual, non-commercial, non-bulk use" **[V-search]** | Forbidden | Bulk forbidden | **Not usable** | No |
| 7 | NBA.com / stats.nba.com | NBA schedules, box scores, player logs | Terms bar reuse "for public or commercial purposes" **[V-search]** | Forbidden | Undocumented endpoints; not offered | **Not usable** | No |
| 8 | SportsDataverse releases (hoopR NBA, fastRhockey NHL) | NBA + NHL schedules, team/player box scores, 2002–present / recent | CC BY 4.0 badge on release store **[V-direct]**; producers have no data licence **[V-direct]**; upstream ESPN/NBA/NHL | Unclear | Yes (GitHub releases) | **Internal testing only** | Yes |
| 9 | NHL web API (api-web.nhle.com) / NHL.com | NHL schedules, box scores | Terms prohibit "spidering, scraping, or harvesting" **[V-search]** | Forbidden without licence | Forbidden | **Not usable** | No |
| 10 | ESPN site API | Scores, box scores, some odds | Undocumented; terms not retrieved **[Assumption]** | Unclear | Not offered by publisher | **Not usable** | No |
| 11 | football-data.co.uk | Soccer results + bookmaker odds, many leagues **[Assumption — from prior knowledge, not seen this session]** | Site terms **not retrieved** (host blocked; searches found none) | Unclear | CSVs offered for download **[V-search, 3P]** | **Needs written permission** | No |
| 12 | openfootball / football.json | Soccer fixtures + results, major European leagues, 2010– | "dedicated to the public domain" **[V-direct]** | Allowed | Yes — README invites raw GitHub use | **Usable now** | Yes |
| 13 | martj42 / international_results | Men's international results 1872–present | CC0 1.0 **[V-direct]** | Allowed | Yes | **Usable now** (niche) | Yes |
| 14 | StatsBomb open data | Soccer event data, selected competitions | User agreement: may not "commercially exploit the data" **[V-direct]** | Forbidden | Asks users to register | **Not usable** | No |
| 15 | FiveThirtyEight data repo | NBA/NFL/MLB/NHL game results + Elo, to mid-2023 | CC BY 4.0 **[V-direct]** | Allowed | Yes (GitHub); CSV host blocked | **Usable now** (stale, results only) | No (size / host) |
| 16 | Kaggle datasets (e.g. "NFL scores and betting data") | Assorted odds/results uploads | Site terms bar scraping **[V-search]**; download needs an account/API key; per-dataset licences not retrieved | Varies, unverified | Needs credentials | **Not usable** under this task's rules | No |
| 17 | Sports-Reference family | All four leagues, deep history | No tools "based on data you scrape" without permission **[V-search]** | Forbidden | Forbidden | **Not usable** | No |
| 18 | Pinnacle | Sharp closing lines | Public API closed 2025-07-23 **[V-search]**; sportsbook → constitution §4 | Forbidden | Forbidden | **Not usable** | No |
| 19 | The Odds API — historical | Multi-book snapshots; props from 2023-05-03 | Paid plans only **[V-search]** | Allowed under its terms (see verification doc) | Needs key | Paid — **note only** | No |
| 20 | Free US odds archives (SportsOddsHistory, sportsbookreviewsonline, aussportsbetting) | NFL/NBA/MLB/NHL closing lines, some back to 1978 | Terms not retrieved; SportsOddsHistory asks for credit **[V-search]** | Unclear | Unclear | **Needs written permission** | No |
| 21 | "Beat the Bookie" (Kaunitz et al.) | Soccer closing odds + odds series (README lists `closing_odds`, `odds_series` zips **[V-direct]**) | Repo GPL-3.0 per third-party mirror **[V-search]**; data on Dropbox; odds were scraped | Unclear | Not from publisher's licensed host | **Not usable** | No |
| 22 | Mendeley Data: Line Movement / Bookmaker Margin Panel | Aggregate movement and margin statistics only | CC BY 4.0 **[V-search]** | Allowed | Not attempted | **Usable now**, low fit (no game-level odds) | No |
| 23 | Princeton DSS Historical Sports Odds Database | Opening/closing lines NBA/NFL/MLB/NHL 2006–2023 | Purchased from a commercial vendor **[V-search]**; campus licence **[Assumption]** | Forbidden **[Assumption]** | No | **Not usable** | No |
| 24 | MoneyPuck | NHL game and player data | Terms not found | Unclear | Unclear | **Needs written permission** | No |

## 3. Per-source notes

Quotes are 25 words or fewer. "Contract" refers to `services/api/src/oddvex_api/providers/base.py`.

### 3.1 nflverse-data — Internal testing only
- **Data:** https://github.com/nflverse/nflverse-data/releases · **Licence:** https://raw.githubusercontent.com/nflverse/nflverse-data/master/LICENSE.md — "Attribution 4.0 International" **[V-direct]**.
- **Caveat:** https://raw.githubusercontent.com/nflverse/nflreadr/main/README.md — "NFL data accessed by this package belong to their respective owners, and are governed by their terms of use." **[V-direct]** The licence covers nflverse's compilation; it cannot grant rights nflverse does not hold. NFL's own terms were not read **[Assumption: restrictive]**. This is why the verdict is not "Usable now".
- **Contents checked in the saved file [V-direct]:** `games.csv`, 7,548 games, seasons 1999–2026; `spread_line` and `total_line` on 7,439 games (1999–2026); `home_moneyline`/`away_moneyline`, spread prices and over/under prices on about 5,458 games (2006–2026). One line per game, no sportsbook, no timestamp. Where the betting columns come from is not stated in anything read **[Assumption: third-party consensus close]**.
- **Also offered:** player-week stats (`stats_player_week_<season>`), players, rosters, play-by-play, injuries **[V-search / release names; only the 2024 player-week Parquet was fetched]**. FTN charting is CC BY-SA 4.0 with its own attribution **[V-direct]**.
- **Format/size:** CSV, Parquet, RDS; schedule 2.2 MB; a season of player-week stats 0.85 MB Parquet (>5 MB as CSV).
- **Attribution:** credit nflverse, link the licence, state changes.
- **Contract mapping:** `Event` (game_id, teams, gameday+gametime, scores → `Score`, status `final`); `Team` from team abbreviations; `Player` + `GameLogEntry` from player-week stats (passing/rushing/receiving yards, TDs); one synthetic "consensus close" `OddsSnapshot` per market. Cannot fill `LineSeries` (one point only) or `PropOffer`.

### 3.2 Retrosheet — Usable now
- **Data:** https://www.retrosheet.org/downloads/csvdownloads.html · **Terms:** https://www.retrosheet.org/notice.txt — search extract: recipients may make "any desired use of the information, including (but not limited to) selling it, giving it away, or producing a commercial product" **[V-search; wording is the search tool's rendering]**.
- **Required credit [V-direct, https://raw.githubusercontent.com/chadwickbureau/retrosheet/master/README.md]:** "The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at "www.retrosheet.org"."
- **Contents:** game logs (one row per game: date, teams, score, starters), box scores, play-by-play; CSV downloads exist **[V-search]**. Seasons/sizes **[Assumption]**: game logs 1871–2025, roughly 1–2 MB per season uncompressed.
- **Automated download:** files are published for download; the site's robots/terms on bulk fetching were not readable **[Assumption: fine at low volume]**.
- **Contract mapping:** `Event` (+`Score`), `Team` (Retrosheet team keys), `Player` (Retrosheet ids, join names via #3.4), `GameLogEntry` from box/day-by-day lines (hits, HR, RBI, strikeouts, pitcher outs/K). No odds.
- **Not downloaded here:** `www.retrosheet.org` was refused by the proxy.

### 3.3 Chadwick `retrosplits` — Usable now (share-alike)
- **Data + licence:** https://raw.githubusercontent.com/chadwickbureau/retrosplits/master/README.md — "This dataset is made available under the Open Database License" **[V-direct]**, contents under DbCL 1.0, plus the Retrosheet credit.
- **Contents:** `daybyday/playing-<year>.csv` (player game-by-game batting/pitching/fielding) and `daybyday/teams-<year>.csv` (team game-by-game) **[V-direct for teams-2023: 4,944 rows, 81 columns]**. `playing-2023.csv` exists but exceeds 5 MB **[V-direct: HTTP 200, aborted at cap]**.
- **Commercial use:** allowed. **Share-alike:** if OddVex publicly uses a database derived from it, that derived database must be offered under ODbL; "produced works" (screens, charts) need only a notice **[Assumption — my reading of ODbL; counsel to confirm]**. Taking the same facts straight from Retrosheet (#3.2) avoids the share-alike term.
- **Contract mapping:** best single source for MLB `GameLogEntry` (`player_id`, `event_id` = `game.key`, `game_time`, `opponent_team_id`, `is_home` from `team.alignment`, `stats` from `B_*`/`P_*`).

### 3.4 Chadwick Register — Usable now
- **Data:** https://github.com/chadwickbureau/register (`data/people-*.csv`) · **Licence [V-direct]:** "made available under the Open Data Commons Attribution License".
- **Contents [V-direct]:** `key_mlbam`, `key_retro`, `key_bbref`, `key_fangraphs`, names, birth dates, first/last played years; `people-0.csv` is 4.3 MB, 32,941 rows.
- **Contract mapping:** `Player.provider_id` crosswalk — lets a Retrosheet-based replay later be joined to a licensed MLB feed.

### 3.5 Lahman (SABR) — Usable now, low value
- https://sabr.org/lahman-database/ ; licence CC BY-SA 3.0 as stated by third parties (GitHub SABR-datasets, CRAN) **[V-search]**; SABR's own statement not seen. Season-level only, so it does not feed `GameLogEntry`. Useful only for `Team`/`Player` reference. Host blocked; not downloaded.

### 3.6 MLB Stats API — Not usable
- Terms: http://gdx.mlb.com/components/copyright.txt — "Only individual, non-commercial, non-bulk use of the Materials is permitted" **[V-search, quoted by third-party copies; file not opened]**. A paid product is commercial use. Needs an MLB/licensed-vendor agreement.

### 3.7 NBA.com / stats.nba.com — Not usable
- https://www.nba.com/termsofuse — search extract: terms prohibit reusing site materials "for public or commercial purposes" **[V-search; exact clause not retrieved]**. The stats endpoints are undocumented and not offered as a public API **[Assumption]**. Needs a licence (NBA data is distributed via Sportradar/Genius).

### 3.8 SportsDataverse releases (hoopR NBA, fastRhockey NHL) — Internal testing only
- **Data:** https://github.com/sportsdataverse/sportsdataverse-data/releases · **Licence:** CC BY 4.0 badge in https://raw.githubusercontent.com/sportsdataverse/sportsdataverse-data/main/README.md **[V-direct]**. Producer repos' `LICENSE` files are stubs ("COPYRIGHT HOLDER: hoopR.nba authors") **[V-direct]**.
- **Why not "Usable now":** the data is harvested from ESPN, the NBA Stats API and the NHL web API **[V-direct, README headings]**, whose terms restrict that (#3.7, #3.9). A CC badge from the compiler does not clear upstream rights.
- **Contents:** NBA schedules, team and player box scores (hoopR README says 2002–present **[V-direct]**); NHL schedules, player/goalie box scores, rosters. 2024-season files are 30–610 KB Parquet **[V-direct: sizes; contents not opened — no Parquet reader installed]**.
- **Contract mapping:** `Event`, `Team`, `Player`, `GameLogEntry` (points/rebounds/assists; goals/assists/shots) for NBA and NHL. No odds columns were confirmed.

### 3.9 NHL web API — Not usable
- https://www.nhl.com/info/terms-of-service (dated 2025-10-29) — prohibited conduct includes unauthorized "spidering, scraping, or harvesting of content or information" **[V-search]**. Undocumented API; no public terms granting use **[Assumption]**.

### 3.10 ESPN site API — Not usable
- Undocumented endpoints; ESPN/Disney terms were not retrieved **[Assumption: prohibit automated commercial use]**. Not a documented public API, so it fails this task's rule regardless.

### 3.11 football-data.co.uk — Needs written permission
- **Data:** https://www.football-data.co.uk/data.php — CSV per league-season with full-time results, match stats and opening/closing 1X2, over/under and Asian-handicap odds from several bookmakers plus market average/maximum **[Assumption from prior knowledge; third parties describe it as free CSV downloads — V-search, 3P]**.
- **Terms:** the proxy refused the host and two searches found no terms text. A third-party mirror labels it "educational and research purposes only" **[V-search, datahub.io]**. Under this task's rule (terms must be read) nothing was downloaded.
- **Why it matters:** it is the only free multi-book closing-odds archive for a major sport. Recommended action: the Founder emails the site owner for written permission for internal backtesting and, separately, display.
- **Contract mapping if cleared:** `Event` + `Score`; `Sportsbook` per bookmaker column; one closing `OddsSnapshot` per book for moneyline (3-way, `has_draw: true`) and total; a two-point `LineSeries` (open, close) where both exist. Decimal odds must be converted to American.

### 3.12 openfootball — Usable now
- https://github.com/openfootball/football.json — "dedicated to the public domain. Use as you please with no restrictions whatsoever." **[V-direct]**. README explicitly describes using raw GitHub links as a keyless JSON API **[V-direct]**.
- **Contents [V-direct]:** per league-season JSON: round, date, time, `team1`, `team2`, half-time and full-time score. EPL 2024/25 is 110 KB. No odds, no players, no stable ids (team names are the keys).
- **Contract mapping:** `League` (`has_draw: true`), `Team` (id = slug of name), `Event` + `Score`.

### 3.13 martj42 international results — Usable now (niche)
- https://github.com/martj42/international_results , CC0 1.0 **[V-direct]**. 49,940 national-team results 1872–present, 3.8 MB CSV. Only relevant if international soccer is in scope.

### 3.14 StatsBomb open data — Not usable
- https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf — user may not "commercially exploit the data or any analysis derived from the use of the Service" **[V-direct]**. Also requires the StatsBomb logo on published analysis and asks users to register. Not downloaded.

### 3.15 FiveThirtyEight — Usable now, stale
- https://github.com/fivethirtyeight/data — "our data sets are available under the Creative Commons Attribution 4.0 International License" **[V-direct]**. "sports predictions and forecasts are no longer being updated" since 2023-06-13 **[V-direct]**.
- NBA game results + Elo 1946–2015 in `nba-elo/nbaallelo.csv` (>5 MB; README says game information is from Basketball-Reference **[V-direct]**); NFL/MLB/NHL Elo CSVs are linked on `projects.fivethirtyeight.com`, which the proxy refused, and may no longer be served **[Assumption]**.
- **Contract mapping:** `Event` + `Score` only. Useful as a model baseline for backtests, not as a data backbone.

### 3.16 Kaggle — Not usable under this task's rules
- https://www.kaggle.com/terms prohibits "crawling or scraping any page or data" **[V-search]**; downloads need an account or API token **[V-search]**, which this task forbids. Individual datasets (for example "NFL scores and betting data", `spreadspoke_scores.csv`, about 13,500 games **[V-search]**) carry their own licences, none of which could be read. Many are re-uploads of data scraped from sources above, so a permissive label on Kaggle would not settle provenance **[Assumption]**.

### 3.17 Sports-Reference — Not usable
- https://www.sports-reference.com/data_use.html — "you should not create websites or tools based on data you scrape from Sports Reference" **[V-search]**. They state they do not offer an API **[V-search]**.

### 3.18 Pinnacle and other sportsbooks — Not usable
- Constitution §4 forbids scraping sportsbooks. Pinnacle's own docs repo says API access has been "closed for the general public since July 23rd, 2025" **[V-search]**.

### 3.19 The Odds API historical — paid, note only
- https://the-odds-api.com/historical-odds-data/ — "historical data is only available on paid usage plans"; additional markets incl. player props from 2023-05-03 **[V-search]**. The existing verification doc records a 10× credit multiplier for historical calls. This is the realistic route to multi-book closing lines.

### 3.20 Free US odds archives — Needs written permission
- SportsOddsHistory.com (NFL closing odds from 1978; asks for credit **[V-search]**), sportsbookreviewsonline.com (season spreadsheets for NFL/NBA/MLB/NHL **[V-search, 3P]**), aussportsbetting.com **[Assumption — search returned nothing]**. No terms were retrieved for any of them, and their upstream sources are sportsbooks or sites that prohibit reuse. Not downloaded.

### 3.21–3.24 Others
- **Beat the Bookie:** soccer odds scraped from an odds-comparison site, hosted on Dropbox; data licence unverified. Not usable.
- **Mendeley aggregate panels:** CC BY 4.0 but explicitly contain "no odds, prices, bookmaker identities, teams, players or event identifiers" **[V-search]** — context for copy, not data for the contract.
- **Princeton DSS odds database:** vendor-purchased, for the university's users. Not usable.
- **MoneyPuck:** no terms found. Ask before use.

## 4. What was and was not downloaded here

**Saved (all HTTP 200, plain `curl -L`, generic user agent, 5 MB cap per file and per source):**

| File in `data/external/` | Bytes | URL |
|---|---:|---|
| `nflverse/schedules_games.csv` | 2,190,087 | https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv |
| `nflverse/stats_player_week_2024.parquet` | 849,243 | https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2024.parquet |
| `sportsdataverse/nba_player_box_2024.parquet` | 610,610 | https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_player_boxscores/player_box_2024.parquet |
| `sportsdataverse/nba_schedule_2024.parquet` | 143,706 | https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_schedules/nba_schedule_2024.parquet |
| `sportsdataverse/nhl_player_box_2024.parquet` | 463,346 | https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nhl_player_boxscores/player_box_2024.parquet |
| `sportsdataverse/nhl_schedule_2024.parquet` | 32,443 | https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nhl_schedules/nhl_schedule_2024.parquet |
| `retrosheet/teams-2023.csv` | 1,021,123 | https://raw.githubusercontent.com/chadwickbureau/retrosplits/master/daybyday/teams-2023.csv |
| `chadwick_register/people-0.csv` | 4,266,429 | https://raw.githubusercontent.com/chadwickbureau/register/master/data/people-0.csv |
| `openfootball/en.1_2024-25.json` | 110,141 | https://raw.githubusercontent.com/openfootball/football.json/master/2024-25/en.1.json |
| `international_results/results.csv` | 3,764,347 | https://raw.githubusercontent.com/martj42/international_results/master/results.csv |

Total 10 files, 13,451,475 bytes. CSV/JSON files were opened and their headers and row counts checked. The five Parquet
files were only checked for the `PAR1` magic bytes; their columns are **not** verified.

**Attempted, not saved:**

| URL | Result |
|---|---|
| .../nflverse-data/releases/download/stats_player/stats_player_week_2024.csv | 200, aborted: over 5 MB cap |
| .../nflverse-data/releases/download/players/players.csv | 200, aborted: over 5 MB cap |
| https://github.com/nflverse/nfldata/raw/master/data/games.csv | 403 from the session's GitHub gateway (repository not enabled); not retried |
| https://github.com/nflverse/nflverse-pbp/raw/master/teams_colors_logos.csv | 403, same |
| https://raw.githubusercontent.com/fivethirtyeight/data/master/nba-elo/nbaallelo.csv | 200, aborted: over 5 MB cap |
| https://projects.fivethirtyeight.com/nhl-api/nhl_elo_latest.csv | proxy 403 on CONNECT |
| .../chadwickbureau/retrosplits/master/daybyday/playing-2023.csv | 200, aborted: over 5 MB cap |
| .../chadwickbureau/retrosheet/master/gamelog/GL2023.TXT | 404 (guessed path) |
| .../openfootball/football.json/master/2024-25/en.1.clubs.json | 404 |

**Hosts refused by the proxy (one attempt each, licence/terms pages; not retried, not routed around):**
`www.retrosheet.org`, `www.football-data.co.uk`, `www.sports-reference.com`, `gdx.mlb.com`, `www.nba.com`,
`www.nhl.com`, `sabr.org`, `www.kaggle.com`, `the-odds-api.com`, `www.pinnacle.com`, `projects.fivethirtyeight.com`.
`api.github.com` also refused (repository not enabled for the session). For these, terms are known only from search
extracts or not at all, as tagged above.

**Not attempted on purpose:** anything rated Needs written permission or Not usable; Kaggle (needs credentials);
Dropbox-hosted odds; any sportsbook.

## 5. Recommended minimal sets

### (a) Internal realistic demo / replay — never shown outside the team until G-12 opens
| League | Events + scores | Player game logs | Odds | Reference |
|---|---|---|---|---|
| NFL | nflverse `games.csv` | nflverse `stats_player_week_<season>` | nflverse consensus close (spread, total, moneyline) as one pseudo-book | nflverse players/rosters |
| MLB | Retrosheet game logs or `retrosplits` teams file | `retrosplits` `playing-<year>.csv` | none — keep synthetic | Chadwick Register |
| NBA | SportsDataverse schedule (internal only) | SportsDataverse player box (internal only) | none — keep synthetic | from the same files |
| NHL | SportsDataverse schedule (internal only) | SportsDataverse player box (internal only) | none — keep synthetic | from the same files |
| Soccer | openfootball EPL | none | none — keep synthetic | team names from the file |

Real results with synthetic multi-book odds layered on top must stay labelled synthetic (`data_mode`), otherwise the
demo would present invented prices as real ones.

### (b) Backtesting
- **NFL:** nflverse `games.csv` alone supports against-the-spread, totals and moneyline backtests from 2006 (spread and
  total from 1999) against one closing number. It cannot support CLV against a specific book, line-shopping value or
  props.
- **Soccer:** only football-data.co.uk has free multi-book closing odds; obtain written permission first.
- **MLB / NBA / NHL:** open data gives outcomes only. Any odds backtest needs purchased history (The Odds API
  historical snapshots, SportsDataIO, OpticOdds).
- Model baselines: FiveThirtyEight Elo files (CC BY 4.0, through mid-2023).

## 6. Gaps open data cannot fill
- **Live and pre-game odds from named US sportsbooks** — no legitimate free source; scraping books is barred by the constitution.
- **Multi-book closing lines and line history** for NFL/NBA/MLB/NHL — the only open NFL line is a single unnamed consensus number per game.
- **Player props (lines and prices), current or historical** — nothing open found.
- **Injuries, lineups, depth charts** with usable rights — league and ESPN sources are restricted.
- **Current-season NBA and NHL data with clear commercial rights** — league terms forbid it; needs a licensed feed.
- **Stable cross-provider ids** outside baseball — no open equivalent of the Chadwick Register for NFL/NBA/NHL beyond what nflverse compiles.
- **Rights to display real team/player names and marks** — a legal question (gate G-12), not a data question.

All of these need a licensed API under a written agreement; see `DATA_PROVIDER_VERIFICATION_2026-11-16.md` for the
provisional choice and the unsent licence question.

## 7. How to add a replay provider (no code)

A replay provider would be a third implementation of `SportsDataProvider` that reads files from `data/external/`
(or a private bucket) instead of generating data. Suggested shape:

1. **Identity:** `name = "replay"`, a new `data_mode` value such as `"replay"` so no response can be mistaken for live
   or synthetic data. `now()` returns a configurable "replay clock" so past games can appear upcoming, live or final.
2. **Provenance:** every record's `provider` is the source key (`nflverse`, `retrosheet`, `openfootball`…),
   `provider_id` the source's own id, `fetched_at` the file retrieval time recorded in `data/external/README.md`.
3. **Field mapping:**

| Contract model | NFL (nflverse) | MLB (Retrosheet / retrosplits / Register) | Soccer (openfootball) |
|---|---|---|---|
| `League` | fixed row, `has_draw: false`, markets `moneyline/spread/total` | fixed row, `has_draw: false` | one per file, `has_draw: true` |
| `Team` | `home_team`/`away_team` abbreviations; city/nickname from a small hand-kept table | `team.key`; names from a hand-kept table | slug of `team1`/`team2` |
| `Player` | `player_id`, display name, position, team from player-week file | `key_retro` + names from the Register; team from latest game line | not available |
| `Event` | `game_id`; `start_time` = `gameday` + `gametime` (US Eastern → UTC); `score` from `home_score`/`away_score`; status from the replay clock | `game.key`; date only (no first-pitch time in the day-by-day files) | synthetic id from date + teams; `date` + `time`; `score.ft` |
| `OddsSnapshot` | one book `consensus_close`: `spread_line` (positive = home favoured, so home line is its negative), `total_line`, moneylines, prices | none | none |
| `LineSeries` | a single point at kickoff, or omit | none | none |
| `GameLogEntry` | one per player-week row; `stats` keys mapped to the contract's prop market names | one per `playing` row; `is_home` from `team.alignment` | none |
| `PropOffer` | none — return an empty list | none | none |

4. **Honesty rules:** return empty lists rather than inventing odds or props; `health()` should report `degraded`
   with a detail string naming what the source cannot provide; `list_sportsbooks()` must not list real sportsbooks
   that the data does not actually contain.
5. **Before it ships anywhere but a developer machine:** Founder opens G-12, counsel reviews the licences in
   `data/external/LICENSES.md`, attribution strings are added to the UI, and for ODbL sources a decision is recorded
   on share-alike.

## 8. Verification tally

By source (24 rows in the table):

- **Licence/terms read by direct fetch: 8** — #1 nflverse, #3 retrosplits, #4 Chadwick Register, #8 SportsDataverse,
  #12 openfootball, #13 international results, #14 StatsBomb, #15 FiveThirtyEight.
- **Mixed: 1** — #2 Retrosheet (credit line by direct fetch from the Chadwick mirror; the permission wording only by
  search extract).
- **Search extracts only: 10** — #5 Lahman, #6 MLB, #7 NBA, #9 NHL, #16 Kaggle, #17 Sports-Reference, #18 Pinnacle,
  #19 The Odds API historical, #22 Mendeley, #23 Princeton.
- **No terms retrieved: 5** — #10 ESPN, #11 football-data.co.uk, #20 free US odds archives, #21 Beat the Bookie
  (data licence), #24 MoneyPuck. All five are rated Not usable or Needs written permission for that reason.

By content: of the 10 saved files, the 5 CSV/JSON files were opened and their headers/row counts checked; the 5
Parquet files were not opened. Field lists for every source that was not downloaded are assumptions or third-party
descriptions. No "Usable now" verdict rests on an unverified licence except #2's permission wording and #5 and #22,
which are flagged and were not downloaded.

## 9. Sources

Direct fetches: nflverse-data `LICENSE.md` and `README.md`; nflreadr and nfl_data_py READMEs; chadwickbureau
`register`, `retrosheet`, `retrosplits` READMEs; openfootball `football.json` README; martj42 `international_results`
README and LICENSE; statsbomb `open-data` README and `LICENSE.pdf`; fivethirtyeight `data` README, LICENSE and the
nba/nfl/mlb/nhl Elo READMEs; sportsdataverse `sportsdataverse-data`, `hoopR`, `hoopR-nba-data`,
`fastRhockey-data`, `fastRhockey-nhl-data` READMEs/LICENSE files; Lisandro79 `BeatTheBookie` README.

Search extracts (pages not opened): https://www.retrosheet.org/notice.txt · https://sabr.org/lahman-database/ ·
https://www.github.com/awesomedata/awesome-public-datasets/issues/220 (quotes MLB copyright.txt) ·
https://www.nba.com/termsofuse · https://www.nhl.com/info/terms-of-service ·
https://www.sports-reference.com/data_use.html · https://static.pfref.com/bot-traffic.html ·
https://kaggle.com/terms · https://github.com/pinnacleapi/pinnacleapi-documentation ·
https://the-odds-api.com/historical-odds-data/ · https://www.sportsoddshistory.com/about-us ·
https://datahub.io/core/english-premier-league · https://data.mendeley.com/datasets/pdsxx5dgbw ·
https://data.mendeley.com/datasets/yt3xsvk7zn · https://dss.princeton.edu/catalog/resource6741
