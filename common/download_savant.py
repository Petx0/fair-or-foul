"""Download Baseball Savant (Statcast) leaderboards, plus a small pitch-level sample.

Leaderboards are one CSV per season, all players (no qualification minimum), regular season.
The pitch-level sample is a single game day per season, used only to audit which columns exist
in which year. Full pitch-level seasons are deliberately not downloaded.

Output:
    data/raw/savant/{board}/{year}.csv             unchanged CSV export
    data/raw/savant/manifest.json
    data/parquet/savant_{board}.parquet            all seasons, with a `season` column

Data is proprietary content of MLB Advanced Media, L.P., used here for individual,
non-commercial research (see README).

Usage:
    uv run python -m common.download_savant --start 2015 --end 2025
"""

import argparse

import pandas as pd

from common.fetch import fetch
from common.paths import PARQUET, RAW

BASE = "https://baseballsavant.mlb.com"
RAW_DIR = RAW / "savant"
MANIFEST = RAW_DIR / "manifest.json"

# board -> (first season offered by the page's season selector, URL template)
LEADERBOARDS = {
    "sprint_speed": (
        2015,
        "/leaderboard/sprint_speed?year={year}&position=&team=&min=0&csv=true",
    ),
    "poptime": (
        2015,
        "/leaderboard/poptime?year={year}&team=&min2b=0&min3b=0&csv=true",
    ),
    "catcher_throwing": (
        2016,
        ("/leaderboard/catcher-throwing?game_type=Regular&n=1&season_start={year}"
            "&season_end={year}&split=no&team=&type=Cat&csv=true"),
    ),
    "pitcher_running_game": (
        2016,
        ("/leaderboard/pitcher-running-game?game_type=Regular&n=1&season_start={year}"
            "&season_end={year}&split=no&team=&type=Pit&with_team_only=1&csv=true"),
    ),
    "basestealing_run_value": (
        2016,
        ("/leaderboard/basestealing-run-value?game_type=Regular&n=1&season_start={year}"
            "&season_end={year}&split=no&team=&type=Run&with_team_only=1&csv=true"),
    ),
}

PITCH_SAMPLE_URL = (
    "/statcast_search/csv?all=true&hfGT=R%7C&hfSea={year}%7C&player_type=pitcher"
    "&game_date_gt={day}&game_date_lt={day}&type=details"
)


def sample_day(year: int) -> str:
    # 2020 opened on July 23; every other season has games on June 15.
    return f"{year}-08-15" if year == 2020 else f"{year}-06-15"


def read_csv(path) -> pd.DataFrame:
    # Savant CSVs start with a byte-order mark. Read everything as text: column types differ
    # across seasons, and this layer only stores what was downloaded.
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=int, default=2015)
    parser.add_argument("--end", type=int, default=2025)
    args = parser.parse_args()
    PARQUET.mkdir(parents=True, exist_ok=True)

    for board, (first, template) in LEADERBOARDS.items():
        frames = []
        for year in range(max(first, args.start), args.end + 1):
            path = fetch(BASE + template.format(year=year), RAW_DIR / board / f"{year}.csv", MANIFEST)
            frames.append(read_csv(path).assign(season=year))
        out = PARQUET / f"savant_{board}.parquet"
        pd.concat(frames, ignore_index=True).to_parquet(out, index=False)
        print(f"{board}: {sum(len(f) for f in frames)} rows -> {out.name}")

    frames = []
    for year in range(args.start, args.end + 1):
        day = sample_day(year)
        url = BASE + PITCH_SAMPLE_URL.format(year=year, day=day)
        df = read_csv(fetch(url, RAW_DIR / "pitch_sample" / f"{day}.csv", MANIFEST))
        if df.empty:
            raise ValueError(f"pitch sample for {day} is empty")
        frames.append(df.assign(season=year, sample_day=day))
    out = PARQUET / "savant_pitch_sample.parquet"
    pd.concat(frames, ignore_index=True).to_parquet(out, index=False)
    print(f"pitch_sample: {sum(len(f) for f in frames)} rows -> {out.name}")


if __name__ == "__main__":
    main()
