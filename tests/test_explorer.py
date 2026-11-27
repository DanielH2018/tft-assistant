import json

from tft_assistant.boards import Board, BoardUnit
from tft_assistant.explorer import ALPHABET, encode, prune, write
from tft_assistant.static_data import Item, StaticData, Unit

STATIC = StaticData(
    units={name: Unit(name, name, 2, (), 1.0, None) for name in ("Ahri", "Zyra")},
    traits={},
    items={name: Item(name, name, (), None, None, False) for name in ("Cap", "Edge")},
)


def board(placement, level, *units):
    return Board("NA1_1", placement, level, 30, tuple(BoardUnit(name, stars, tuple(items)) for name, stars, items in units), {})


def decode(document):
    """Read the document as the page's script does."""
    symbols = {symbol: number for number, symbol in enumerate(document["alphabet"])}

    def two(text):
        return symbols[text[0]] * len(symbols) + symbols[text[1]]

    boards = []
    for line in document["boards"].split("\n"):
        units, at = [], 2
        while at < len(line):
            stars, held = divmod(symbols[line[at + 2]], 4)
            items = [document["items"][two(line[at + 3 + 2 * n : at + 5 + 2 * n])] for n in range(held)]
            units.append((document["units"][two(line[at : at + 2])], stars, items))
            at += 3 + 2 * held
        boards.append((int(line[0]), symbols[line[1]], units))
    return boards


def test_a_board_reads_back_with_its_placement_level_units_stars_and_items():
    boards = [
        board(1, 9, ("Zyra", 3, ["Cap", "Edge", "Cap"]), ("Ahri", 1, [])),
        board(8, 10, ("Ahri", 2, ["Edge"])),
    ]

    assert decode(encode(boards, STATIC)) == [
        (1, 9, [("Zyra", 3, ["Cap", "Edge", "Cap"]), ("Ahri", 1, [])]),
        (8, 10, [("Ahri", 2, ["Edge"])]),
    ]


def test_a_unit_or_an_item_the_set_does_not_know_is_left_out():
    boards = [board(4, 8, ("Dummy", 1, ["Cap"]), ("Ahri", 2, ["From another set", "Cap"]))]

    assert decode(encode(boards, STATIC)) == [(4, 8, [("Ahri", 2, ["Cap"])])]


def test_the_document_is_json_whose_board_lines_need_no_escape():
    assert '"' not in ALPHABET and "\\" not in ALPHABET
    document = encode([board(1, 9, ("Zyra", 3, ["Cap"]))], STATIC)

    assert json.loads(json.dumps(document)) == document
    assert json.dumps(document["boards"]) == f'"{document["boards"]}"'


def test_the_same_boards_are_one_file_and_a_file_no_snapshot_names_is_removed(tmp_path):
    first = write([board(1, 9, ("Zyra", 3, []))], STATIC, tmp_path)
    again = write([board(1, 9, ("Zyra", 3, []))], STATIC, tmp_path)
    other = write([board(2, 9, ("Zyra", 3, []))], STATIC, tmp_path)

    prune(tmp_path, [first])

    assert first == again != other
    assert [path.name for path in (tmp_path / "explorer").iterdir()] == [first.split("/")[1]]
