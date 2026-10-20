"""Download official team batting totals per season from the MLB Stats API.

Used as the official reference for season SB and CS totals. One request per season:
    https://statsapi.mlb.com/api/v1/teams/stats?season={year}&group=hitting&stats=season
        &sportIds=1&gameType=R

Output:
    data/raw/mlb_stats_api/teams_hitting/{year}.json   unchanged response
    data/raw/mlb_stats_api/manifest.json
    data/parquet/mlb_team_hitting.parquet               one row per team-season

Data is proprietary content of MLB Advanced Media, L.P., used here for individual,
non-commercial research (see README).

Usage:
    uv run python -m common.download_mlb_stats --start 2000 --end 2025
"""

import argparse
import json

import pandas as pd

from common.fetch import fetch
from common.paths import PARQUET, RAW

URL = (
    "https://statsapi.mlb.com/api/v1/teams/stats?season={year}&group=hitting&stats=season"
    "&sportIds=1&gameType=R"
)
RAW_DIR = RAW / "mlb_stats_api" / "teams_hitting"
MANIFEST = RAW / "mlb_stats_api" / "manifest.json"
OUT = PARQUET / "mlb_team_hitting.parquet"


def rows(year: int, payload: dict) -> list[dict]:
    (block,) = payload["stats"]  # exactly one stats block expected
    out = []
    for split in block["splits"]:
        stat = split["stat"]
        out.append(
            {
                "season": year,
                "team_id": split["team"]["id"],
                "team": split["team"]["name"],
                "games": stat["gamesPlayed"],
                "sb": stat["stolenBases"],
                "cs": stat["caughtStealing"],
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=int, default=2000)
    parser.add_argument("--end", type=int, default=2025)
    args = parser.parse_args()

    records = []
    for year in range(args.start, args.end + 1):
        path = fetch(URL.format(year=year), RAW_DIR / f"{year}.json", MANIFEST)
        records += rows(year, json.loads(path.read_text()))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_parquet(OUT, index=False)
    print(f"wrote {OUT} ({len(records)} team-seasons)")


if __name__ == "__main__":
    main()
