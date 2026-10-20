"""Cached, logged HTTP downloads shared by all download scripts.

Every file is saved unchanged under data/raw/<source>/ and recorded in that source's
manifest.json with its URL, download time, Last-Modified header, size and SHA-256.
"""

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

USER_AGENT = "fair-or-foul research pipeline (non-commercial)"
PAUSE_SECONDS = 1.0  # between requests, to keep load on each source low


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, path: Path, manifest_path: Path) -> Path:
    """Download `url` to `path` unless it already exists. Raises on any HTTP error."""
    if path.exists():
        return path
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=120)
    resp.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)

    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest[str(path.relative_to(manifest_path.parent))] = {
        "url": url,
        "downloaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "last_modified": resp.headers.get("Last-Modified"),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    time.sleep(PAUSE_SECONDS)
    return path
