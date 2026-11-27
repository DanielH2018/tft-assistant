"""Copy the icons a page shows into its site, so the page's own server serves them.

Community Dragon serves an icon with an hour's cache life, so a browser asks for every icon
again each hour, from a second host. A copy in the site is named by its content: its address
changes when the picture does, and the server can tell a browser to keep it for good.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx

from tft_assistant.static_data import CACHE_DIR

ICON_DIR = "icons"
_MAX_AGE_SECONDS = 7 * 24 * 3600
_TABLES = ("units", "traits", "items")


def _fetch(url: str) -> bytes:
    response = httpx.get(url, timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    return response.content


def _cached(url: str, cache: Path, fetch: Callable[[str], bytes]) -> bytes | None:
    """The picture at `url`, downloaded at most once a week; None when there is no copy to use.

    A download that fails falls back on the copy from an earlier week.
    """
    kept = cache / f"{hashlib.sha256(url.encode()).hexdigest()[:24]}.png"
    if not kept.exists() or time.time() - kept.stat().st_mtime > _MAX_AGE_SECONDS:
        try:
            content = fetch(url)
        except httpx.HTTPError:
            return kept.read_bytes() if kept.exists() else None
        cache.mkdir(parents=True, exist_ok=True)
        kept.write_bytes(content)
    return kept.read_bytes()


def mirror(
    snapshots: Sequence[dict[str, Any]],
    site: Path,
    *,
    fetch: Callable[[str], bytes] = _fetch,
    cache: Path | None = None,
) -> str:
    """Write every icon the snapshots name under `site`, and point the snapshots at the copies.

    The snapshots change in place: an icon's address becomes a path relative to the page. An icon
    that cannot be had keeps its address, so the page shows it from where it came. A copy no
    snapshot names any more is removed. Returns one line that says how it went.
    """
    entries = [entry for snapshot in snapshots for table in _TABLES for entry in snapshot[table].values()]
    urls = sorted({entry["icon"] for entry in entries if (entry["icon"] or "").startswith("http")})
    cache = cache or CACHE_DIR / ICON_DIR
    with ThreadPoolExecutor(max_workers=8) as pool:
        pictures = dict(zip(urls, pool.map(lambda url: _cached(url, cache, fetch), urls), strict=True))

    folder = site / ICON_DIR
    folder.mkdir(parents=True, exist_ok=True)
    local: dict[str, str] = {}
    for url, picture in pictures.items():
        if picture is not None:
            name = f"{hashlib.sha256(picture).hexdigest()[:20]}.png"
            if not (folder / name).exists():
                (folder / name).write_bytes(picture)
            local[url] = f"{ICON_DIR}/{name}"
    for entry in entries:
        entry["icon"] = local.get(entry["icon"], entry["icon"])
    for stale in set(folder.iterdir()) - {site / path for path in local.values()}:
        stale.unlink()

    missed = len(urls) - len(local)
    return f"{len(local)} icons in the site" + (f", {missed} left at their source" if missed else "")
