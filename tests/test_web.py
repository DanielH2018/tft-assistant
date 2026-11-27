"""Checks on the page's script that need no browser."""

import re
from collections import Counter

from tft_assistant.build import WEB_DIR

DECLARED = re.compile(r"^(?:async )?function (\w+)|^(?:const|let) (\w+) =", re.MULTILINE)


def declared(script):
    return Counter(first or second for first, second in DECLARED.findall(script))


def test_the_script_declares_each_top_level_name_once():
    # A second `function` of one name replaces the first without an error, for every caller.
    twice = [name for name, count in declared((WEB_DIR / "app.js").read_text()).items() if count > 1]

    assert twice == []


def test_a_name_declared_twice_is_found():
    assert declared("function save(a) {}\nconst other = 1;\nasync function save() {}\n")["save"] == 2
