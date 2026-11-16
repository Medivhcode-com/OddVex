# data/external — third-party sample data (not committed)

Small samples of openly published sports data, fetched on **2026-11-16** for licence and format evaluation only.
See `docs/research/OPEN_DATASETS_2026-11-16.md` for the full evaluation and `LICENSES.md` here for licence links.

> **These files contain REAL team and player names. They must not be shown in the product, in demos shown outside
> the team, in screenshots or in marketing until the Founder opens gate G-12 (real names) and counsel has reviewed
> the licences below.** The running product stays on synthetic data (`data_mode: "synthetic"`).

- Nothing in this directory is committed: `.gitignore` ignores everything except `README.md`, `LICENSES.md` and itself.
- Every file was fetched with plain `curl` through the session proxy from a public GitHub URL. No login, API key,
  header spoofing or TLS bypass was used. No sportsbook site was contacted.
- Files are untrusted input. Parse them as data; never execute anything from this directory.
- To re-create a file, run `curl -L -o <file> <source URL>`.

## Files saved

| File | Bytes | Source URL | Licence | Required attribution | Verdict |
|---|---:|---|---|---|---|
| `nflverse/schedules_games.csv` | 2,190,087 | https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv | CC BY 4.0 (repository `LICENSE.md`) | "Data: nflverse (nflverse-data), CC BY 4.0", link to licence, note changes | Internal testing only |
| `nflverse/stats_player_week_2024.parquet` | 849,243 | https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2024.parquet | CC BY 4.0 (same) | same | Internal testing only |
| `sportsdataverse/nba_player_box_2024.parquet` | 610,610 | https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_player_boxscores/player_box_2024.parquet | CC BY 4.0 (README badge); upstream is ESPN | "Data: SportsDataverse (hoopR), CC BY 4.0" | Internal testing only |
| `sportsdataverse/nba_schedule_2024.parquet` | 143,706 | https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_schedules/nba_schedule_2024.parquet | same | same | Internal testing only |
| `sportsdataverse/nhl_player_box_2024.parquet` | 463,346 | https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nhl_player_boxscores/player_box_2024.parquet | CC BY 4.0 (README badge); upstream is the NHL web API | "Data: SportsDataverse (fastRhockey), CC BY 4.0" | Internal testing only |
| `sportsdataverse/nhl_schedule_2024.parquet` | 32,443 | https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nhl_schedules/nhl_schedule_2024.parquet | same | same | Internal testing only |
| `retrosheet/teams-2023.csv` | 1,021,123 | https://raw.githubusercontent.com/chadwickbureau/retrosplits/master/daybyday/teams-2023.csv | ODbL 1.0 (database) + DbCL 1.0 (contents); underlying data © Retrosheet | "The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at www.retrosheet.org." plus ODbL notice | Usable now (share-alike applies) |
| `chadwick_register/people-0.csv` | 4,266,429 | https://raw.githubusercontent.com/chadwickbureau/register/master/data/people-0.csv | ODC Attribution License 1.0 | "Chadwick Baseball Bureau Register, ODC-BY 1.0" | Usable now |
| `openfootball/en.1_2024-25.json` | 110,141 | https://raw.githubusercontent.com/openfootball/football.json/master/2024-25/en.1.json | Public domain dedication (README) | None required; credit "openfootball" as courtesy | Usable now |
| `international_results/results.csv` | 3,764,347 | https://raw.githubusercontent.com/martj42/international_results/master/results.csv | CC0 1.0 | None required | Usable now |

Total: 10 files, 13,451,475 bytes. Each source directory is under 5 MB.

## What each file is

- `nflverse/schedules_games.csv` — one row per NFL game, 1999–2026 (7,548 rows): teams, scores, kickoff, and closing
  `spread_line` / `total_line` (1999 onward) plus `home_moneyline`, `away_moneyline`, spread and total prices
  (2006 onward). **Single consensus line, no sportsbook named.** The origin of the betting columns is not documented
  in the files read this session.
- `nflverse/stats_player_week_2024.parquet` — player-week statistics, 2024 season (not opened here: no Parquet reader
  is installed; only the `PAR1` magic bytes were checked).
- `sportsdataverse/*.parquet` — NBA and NHL 2024 season schedules and player box scores (same caveat: magic bytes only).
- `retrosheet/teams-2023.csv` — MLB team game-by-game batting/pitching/fielding lines, 2023 (4,944 rows).
  The matching player file `playing-2023.csv` is larger than 5 MB and was deliberately not saved.
- `chadwick_register/people-0.csv` — one shard (`people-0`; the register is split across several files) of the baseball people register: cross-reference ids
  (MLBAM, Retrosheet, Baseball-Reference, FanGraphs) and names (32,941 rows).
- `openfootball/en.1_2024-25.json` — English Premier League 2024/25 fixtures and results.
- `international_results/results.csv` — men's international football results since 1872 (49,940 rows).

## Attempted but not saved

| URL | Result | Why |
|---|---|---|
| https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2024.csv | HTTP 200, aborted | Larger than the 5 MB cap; the Parquet version was saved instead |
| https://github.com/nflverse/nflverse-data/releases/download/players/players.csv | HTTP 200, aborted | Larger than the 5 MB cap |
| https://github.com/nflverse/nfldata/raw/master/data/games.csv | 403 from the session's GitHub gateway | Repository not enabled for this session; not retried |
| https://github.com/nflverse/nflverse-pbp/raw/master/teams_colors_logos.csv | 403 from the session's GitHub gateway | Same; not retried |
| https://raw.githubusercontent.com/fivethirtyeight/data/master/nba-elo/nbaallelo.csv | HTTP 200, aborted | Larger than the 5 MB cap |
| https://projects.fivethirtyeight.com/nhl-api/nhl_elo_latest.csv | Proxy refused CONNECT (403) | Host not allowed; not retried |
| https://raw.githubusercontent.com/chadwickbureau/retrosplits/master/daybyday/playing-2023.csv | HTTP 200, aborted | Larger than the 5 MB cap |
| https://raw.githubusercontent.com/chadwickbureau/retrosheet/master/gamelog/GL2023.TXT | HTTP 404 | Guessed path does not exist |
| https://raw.githubusercontent.com/openfootball/football.json/master/2024-25/en.1.clubs.json | HTTP 404 | File does not exist for this season |
