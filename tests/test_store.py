from datetime import datetime

import pytest

from tft_assistant.store import Selection, Store, patch_of


def match(match_id, *, set_number=19, version="Version 19.1.123.456", queue_id=1100, started="2026-12-03T12:00"):
    return {
        "metadata": {"match_id": match_id},
        "info": {
            "tft_set_number": set_number,
            "game_version": version,
            "queue_id": queue_id,
            "game_datetime": datetime.fromisoformat(started).timestamp() * 1000,
        },
    }


def ids(store, selection):
    return [m["metadata"]["match_id"] for m in store.matches(selection)]


@pytest.fixture
def store():
    store = Store(":memory:")
    store.add_match("na1", match("NA1_1"))
    store.add_match("na1", match("NA1_2", version="Version 19.2.1.1", started="2026-12-17T12:00"))
    store.add_match("kr", match("KR_1", started="2026-12-04T12:00"))
    store.add_match("kr", match("KR_2", queue_id=1090))
    store.add_match("kr", match("KR_3", set_number=18, version="Version 18.7.1.1", started="2026-11-20T12:00"))
    return store


def test_a_selection_reads_one_sets_ranked_matches_in_time_order(store):
    assert ids(store, Selection(19)) == ["NA1_1", "KR_1", "NA1_2"]


def test_a_selection_narrows_by_patch_platform_and_time_window(store):
    assert ids(store, Selection(19, patches=("19.1",))) == ["NA1_1", "KR_1"]
    assert ids(store, Selection(19, platforms=("kr",))) == ["KR_1"]
    assert ids(store, Selection(19, since=datetime(2026, 12, 4), until=datetime(2026, 12, 17))) == ["KR_1"]
    assert store.count(Selection(19, patches=("19.1", "19.2"), queue_id=1090)) == 1


def test_patches_summarises_what_the_store_holds(store):
    assert [(p.set_number, p.patch, p.matches) for p in store.patches()] == [(18, "18.7", 1), (19, "19.1", 2), (19, "19.2", 1)]


def test_missing_names_the_ids_not_stored_and_a_repeated_add_keeps_one_copy(store):
    store.add_match("na1", match("NA1_1"))

    assert store.missing(["NA1_1", "NA1_9", "KR_1"]) == ["NA1_9"]
    assert store.count(Selection(19)) == 3


def test_patch_of_rejects_a_version_with_no_patch_number():
    assert patch_of("Linux Version 19.1.700.1 (Dec 01 2026)") == "19.1"
    with pytest.raises(ValueError, match="no patch number"):
        patch_of("unknown")
