"""Where the tool keeps what it writes: the match store, the comp ids and the static-data cache."""

from __future__ import annotations

import os
from pathlib import Path


def state_path(name: str, default: str) -> Path:
    """`name` under `TFT_STATE_DIR` when that is set, and `default` when it is not.

    A person's machine keeps the store and the cache in their usual places under the home
    directory. An unattended run has one volume, so it names one directory for both.
    """
    root = os.environ.get("TFT_STATE_DIR")
    return Path(root) / name if root else Path(default).expanduser()
