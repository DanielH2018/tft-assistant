"""Turn the game's description templates into the plain text a hover card shows.

A template is the game's own markup: `@Name@` and `@Name*100@` for a value, `%i:scaleAD%` for
a stat's picture, `<br>` and `<li>` for a new line, and tags that only colour the text. A
trait's template has one `<row>` for each breakpoint, read with that breakpoint's values.

A value is under its name or under a hash of it. A line that names a value the data does not
hold is left out: those are the counters a game fills in as it runs, such as damage dealt.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_STATS = {
    "scaleAD": "Attack Damage",
    "scaleAP": "Ability Power",
    "scaleAS": "Attack Speed",
    "scaleHealth": "Health",
    "scaleArmor": "Armor",
    "scaleMR": "Magic Resist",
    "scaleDR": "Durability",
    "scaleManaRegen": "Mana Regen",
    "TFTManaRegen": "Mana Regen",
    "goldCoins": "gold",
}
"""What each stat picture stands for. A picture this does not name is dropped."""

_ROW = re.compile(r"<row>(.*?)</row>", re.DOTALL | re.IGNORECASE)
_VALUE = re.compile(r"@([^@*]+?)(\*100)?@")
_PICTURE = re.compile(r"%i:([A-Za-z]+)%")
_PICTURES = re.compile(r"(?:%i:[A-Za-z]+%\s*)+")
_KEYWORD = re.compile(r"\{\{[^}]*\}\}")
_BREAK = re.compile(r"<br\s*/?>|<li>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")


def hashed(name: str) -> str:
    """The key the data files a value under when it hides the name: 32-bit FNV-1a of the lower-cased name."""
    value = 0x811C9DC5
    for byte in name.lower().encode():
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return f"{{{value:08x}}}"


def _number(value: float) -> str:
    return f"{round(value, 2):g}"


def _line(line: str, values: Mapping[str, Any]) -> str | None:
    """One line with its values filled in, or None when the data lacks one of them."""
    missing = False

    def fill(match: re.Match[str]) -> str:
        nonlocal missing
        found = values.get(match[1], values.get(hashed(match[1])))
        if not isinstance(found, int | float):
            missing = True
            return ""
        return _number(found * 100 if match[2] else found)

    filled = _VALUE.sub(fill, line)
    if missing:
        return None
    # A run of pictures names its stats. A stat's name follows its picture in some templates,
    # and then the picture adds nothing.
    def stats(match: re.Match[str]) -> str:
        rest = filled[match.end() :].lstrip(" +0123456789.%").lower()
        names = [_STATS[picture] for picture in _PICTURE.findall(match[0]) if picture in _STATS]
        return " " + " and ".join(name for name in names if not rest.startswith(name.lower())) + " "

    text = _TAG.sub("", _KEYWORD.sub("", _PICTURES.sub(stats, filled))).replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip() or None


def render(template: str | None, values: Mapping[str, Any]) -> str:
    """A template as text, a line of the template to a line."""
    lines = (_line(line, values) for line in _BREAK.split(template or ""))
    return "\n".join(line for line in lines if line)


def render_trait(template: str | None, effects: list[dict[str, Any]]) -> tuple[str, tuple[str, ...]]:
    """A trait's opening text, and one line for each breakpoint in the order of `effects`.

    A breakpoint with no row of its own, or whose row names a value the data lacks, gets an empty line.
    """
    template = template or ""
    first = (effects[0].get("variables") or {}) if effects else {}
    opening = render(_ROW.sub("", template), first)
    rows = _ROW.findall(template)
    lines = []
    for number, effect in enumerate(effects):
        values = {**(effect.get("variables") or {}), "MinUnits": effect["minUnits"]}
        lines.append((render(rows[number], values) if number < len(rows) else ""))
    return opening, tuple(lines)
