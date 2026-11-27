"""Where the tool keeps what it writes.

The match store, the static-data cache and the page come back from an API or a build. The edits
and the comp ids they are keyed by do not, so they sit apart under `keep/`, which is the one
directory an unattended run has to back up.
"""

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
