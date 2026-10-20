# Fair or Foul

Code and data pipeline behind **Fair or Foul**, a Substack series that takes a piece of
conventional baseball wisdom, tests it against data, and simulates to explain why it holds or
doesn't. Each claim gets a verdict: **fair** (holds), **foul** (does not hold) or **too close to
call**.

This repository exists so that every number and figure in a post can be traced back to code.
Nothing in a post is typed by hand.

| Post | Question | Folder |
|---|---|---|
| 1 | When does it pay to steal a base? | [posts/01-stolen-bases](posts/01-stolen-bases/) |

## Reproduce

Requirements: macOS or Linux, [uv](https://docs.astral.sh/uv/) (it installs the pinned Python
3.12 itself) and `make`.

```bash
make all
```

That one command installs dependencies, downloads the raw data, converts it to Parquet and
regenerates every report and figure. Individual steps:

| Command | What it does |
|---|---|
| `make setup` | Create the virtual environment from `uv.lock` |
| `make data` | Download raw data (Retrosheet, MLB Stats API, Baseball Savant) into `data/raw/` and convert it to Parquet in `data/parquet/` |
| `make audit` | Regenerate `posts/01-stolen-bases/data_audit.md` |
| `make test` | Run unit tests |

Raw data is never committed (`data/` is git-ignored). Downloads are cached: rerunning skips
files that are already present and records a SHA-256 checksum for each in
`data/raw/<source>/manifest.json`.

Query the data with DuckDB from Python:

```python
from common.db import connect
con = connect()
con.sql("select count(*) from plays where sb2 = 1").show()
```

## Layout

```
common/        shared code: definitions, paths, DuckDB views, download scripts
claims/        registry of claims and attributed quotes, one YAML file per post
posts/NN-*/    one folder per post: analysis/, figures/, post.md, audit reports
tests/         unit tests for shared definitions
data/          (git-ignored) raw downloads and Parquet files
```

## Data sources and attributions

### Retrosheet

Play-by-play data comes from Retrosheet's parsed play-by-play files
(<https://www.retrosheet.org/downloads/plays.html>).

> The information used here was obtained free of
> charge from and is copyrighted by Retrosheet. Interested
> parties may contact Retrosheet at 20 Sunset Rd.,
> Newark, DE 19711.

This wording is copied from the notice on Retrosheet's download pages (game.htm and
downloads/plays.html, checked 2026-10-20). Retrosheet's standalone `notice.txt` (last modified
2023-12-03) gives the same statement but ends "Interested parties may contact Retrosheet at
\"www.retrosheet.org\"."

### MLB Advanced Media (Baseball Savant, MLB Stats API)

Statcast leaderboards (<https://baseballsavant.mlb.com>) and official team totals from the MLB
Stats API (<https://statsapi.mlb.com>) are proprietary content of MLB Advanced Media, L.P.,
used here for individual, non-commercial research. The scripts make about one request per
season per table, one second apart, and never download full pitch-level seasons. Nothing
downloaded is committed or redistributed. Note that MLB's Terms of Use
(<https://www.mlb.com/official-information/terms-of-use>) also restrict automated access; the
project owner reviewed this and judged this limited use acceptable. If you rerun the
downloads, that judgement is yours to make.

### FanGraphs and Baseball-Reference

Used only as published references for cross-checks. Their sites block scripted access, and this
repository does not scrape them.

## License

- Code: [MIT](LICENSE).
- Post text and figures (`posts/`, `claims/`): [CC BY 4.0](LICENSE-content).
- Data is not included and keeps its sources' terms (see above).
