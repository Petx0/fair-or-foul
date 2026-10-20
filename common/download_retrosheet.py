"""Download Retrosheet parsed play-by-play files and convert them to Parquet.

Source: https://www.retrosheet.org/downloads/plays.html ("Parsed Play-by-Play by Season").
Each season is a zip holding one CSV with one row per play (177 columns, documented on that page).

Why this format: it is Retrosheet's own parse of its event files, so it needs no external parser
(e.g. Chadwick), and it keeps the raw event text (`event` column) next to the derived flags, so
every flag can be audited against the original scoring.

Output:
    data/raw/retrosheet/plays/{year}plays.zip   unchanged download
    data/raw/retrosheet/manifest.json           URL, download time, Last-Modified, SHA-256
    data/parquet/retrosheet_plays/{year}.parquet

Usage:
    uv run python -m common.download_retrosheet --start 2000 --end 2025
"""

import argparse
import tempfile
import zipfile
from pathlib import Path

import duckdb

from common.fetch import fetch
from common.paths import PARQUET, RAW

URL = "https://www.retrosheet.org/downloads/plays/{year}plays.zip"
RAW_DIR = RAW / "retrosheet" / "plays"
MANIFEST = RAW / "retrosheet" / "manifest.json"
OUT_DIR = PARQUET / "retrosheet_plays"

# Columns kept as text. Everything else in plays.csv is an integer count, flag or code and is
# cast strictly, so an unexpected value fails loudly instead of becoming NULL.
# `count` ("12", or "??" when unknown) and `fseq` ("643", 0 = unknown fielder) are codes whose
# leading zeros matter, so they stay as text too.
TEXT_COLUMNS = {
    "gid", "event", "site", "batteam", "pitteam", "batter", "pitcher", "bathand", "pithand",
    "count", "pitches", "br1_pre", "br2_pre", "br3_pre", "br1_post", "br2_post", "br3_post",
    "lob_id1", "lob_id2", "lob_id3", "pr1_pre", "pr2_pre", "pr3_pre", "pr1_post", "pr2_post",
    "pr3_post", "run_b", "run1", "run2", "run3", "prun_b", "prun1", "prun2", "prun3",
    "l1", "l2", "l3", "l4", "l5", "l6", "l7", "l8", "l9",
    "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9",
    "fseq", "loc", "hittype", "umphome", "ump1b", "ump2b", "ump3b", "umplf", "umprf",
    "gametype", "pbp",
}


def to_parquet(year: int, zip_path: Path) -> Path:
    """Extract the season CSV to a temp dir and write a typed Parquet file."""
    out = OUT_DIR / f"{year}.parquet"
    if out.exists():
        return out
    expected = f"{year}plays.csv"
    with zipfile.ZipFile(zip_path) as zf, tempfile.TemporaryDirectory() as tmp:
        names = zf.namelist()
        if names != [expected]:
            raise ValueError(f"{zip_path.name}: expected only {expected}, found {names}")
        csv_path = Path(tmp) / expected
        csv_path.write_bytes(zf.read(expected))

        con = duckdb.connect()
        src = f"read_csv('{csv_path}', all_varchar = true, header = true)"
        columns = [r[0] for r in con.sql(f"describe select * from {src}").fetchall()]
        select = []
        for c in columns:
            if c in TEXT_COLUMNS:
                select.append(f'"{c}"')
            elif c == "date":
                select.append("strptime(date, '%Y%m%d')::date as date")
            else:
                select.append(f'cast("{c}" as integer) as "{c}"')
        select.append(f"{year}::smallint as season")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        con.sql(
            f"copy (select {', '.join(select)} from {src}) to '{out}' "
            "(format parquet, compression zstd)"
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=int, default=2000)
    parser.add_argument("--end", type=int, default=2025)
    args = parser.parse_args()

    for year in range(args.start, args.end + 1):
        zip_path = fetch(URL.format(year=year), RAW_DIR / f"{year}plays.zip", MANIFEST)
        out = to_parquet(year, zip_path)
        print(f"{year}: {out.relative_to(PARQUET.parent.parent)}")


if __name__ == "__main__":
    main()
