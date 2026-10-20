"""Filesystem locations used across the repo."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
PARQUET = DATA / "parquet"
POSTS = ROOT / "posts"
CLAIMS = ROOT / "claims"
