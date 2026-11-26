"""Write the site: one self-contained page with every snapshot embedded in it."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

WEB_DIR = Path(__file__).parent / "web"


def build_site(snapshots: Sequence[dict[str, Any]], out_dir: Path) -> Path:
    """Write `index.html` under `out_dir` and return its path.

    The snapshots travel inside the page as JSON, so the page needs no server beside the file.
    """
    data = json.dumps(list(snapshots), separators=(",", ":")).replace("</", "<\\/")
    page = (WEB_DIR / "index.html").read_text()
    for marker, content in (
        ("/*STYLE*/", (WEB_DIR / "style.css").read_text()),
        ("/*SCRIPT*/", (WEB_DIR / "app.js").read_text()),
        ("/*SNAPSHOTS*/", data),
    ):
        page = page.replace(marker, content)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "index.html"
    target.write_text(page)
    return target
