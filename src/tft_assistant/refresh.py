"""The unattended run: keep the store and the page current with nobody starting a command."""

from __future__ import annotations

import itertools
import time
from collections.abc import Callable


def refresh(
    crawl: Callable[[], object],
    build: Callable[[], object],
    *,
    cycle_seconds: float,
    cycles: int | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], object] = time.sleep,
) -> None:
    """Build the page, then crawl and build again once a cycle, for `cycles` cycles or for ever.

    The first build comes before any crawl, so a restarted run has a page from the matches it
    already holds within seconds. A crawl that ends before its cycle does has walked the whole
    ladder. The run then waits out the cycle, because a second walk straight away finds almost
    nothing new.

    A crawl that fails does not end the run. An expired key or an API outage lasts longer than a
    restart takes, and a run that exits on one leaves its container restarting, which a
    deployment reads as the whole service being down while the page is fine. The run prints the
    failure, builds from the matches the crawl stored before it failed, and crawls again next
    cycle. A build that fails does end the run: that is a fault in this code, not in the API.
    """
    build()
    for _ in itertools.count() if cycles is None else range(cycles):
        started = clock()
        try:
            crawl()
        except Exception as failure:  # noqa: BLE001 - whatever the API did, the next cycle tries again
            print(f"the crawl failed and the next cycle tries again: {failure}", flush=True)
        build()
        sleep(max(0.0, cycle_seconds - (clock() - started)))
