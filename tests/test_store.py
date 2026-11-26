from datetime import UTC, datetime

import pytest

from tft_assistant.store import Selection, Store

RANKED, NORMAL = 6080, 6090


def at(day, hour=12):
    return datetime(2026, 12, day, hour, tzinfo=UTC)


def match(match_id, *, set_number=19, queue_id=RANKED, started=at(3)):
    return {
        "metadata": {"match_id": match_id},
        "info": {
            "tft_set_number": set_number,
            "game_version": "TFT Unreal Version ?.?.?.?",
            "queue_id": queue_id,
            "game_datetime": started.timestamp() * 1000,
        },
    }


def ids(store, selection):
    return [m["metadata"]["match_id"] for m in store.matches(selection)]


@pytest.fixture
def store():
    store = Store(":memory:")
    store.add_match("na1", match("NA1_1"))
    store.add_match("na1", match("NA1_2", started=at(17)))
    store.add_match("kr", match("KR_1", started=at(4)))
    store.add_match("kr", match("KR_2", queue_id=NORMAL))
    store.add_match("kr", match("KR_3", set_number=18, started=at(1)))
    return store


def test_a_selection_reads_one_sets_matches_of_one_queue_in_time_order(store):
    assert ids(store, Selection(19, RANKED)) == ["NA1_1", "KR_1", "NA1_2"]
    assert ids(store, Selection(19, NORMAL)) == ["KR_2"]


def test_a_selection_narrows_by_platform_and_time_window(store):
    assert ids(store, Selection(19, RANKED, platforms=("kr",))) == ["KR_1"]
    assert ids(store, Selection(19, RANKED, since=at(4), until=at(17))) == ["KR_1"]
    assert store.count(Selection(19, RANKED, since=at(4))) == 2


def test_holdings_counts_matches_per_set_and_queue(store):
    assert [(h.set_number, h.queue_id, h.matches) for h in store.holdings()] == [
        (18, RANKED, 1),
        (19, RANKED, 3),
        (19, NORMAL, 1),
    ]
    assert store.holdings()[1].last == at(17)


def test_newest_is_the_start_of_a_selections_latest_match_and_none_without_one(store):
    assert store.newest(Selection(19, RANKED)) == at(17)
    assert store.newest(Selection(19, RANKED, until=at(4))) == at(3)
    assert store.newest(Selection(20, RANKED)) is None


def test_a_selection_with_more_matches_than_a_limit_is_narrowed_to_its_newest(store):
    every = Selection(19, RANKED)

    assert ids(store, store.capped(every, 2)) == ["KR_1", "NA1_2"]
    assert store.capped(every, 2).since == at(4)
    assert store.capped(every, 3) is every


def test_pruning_deletes_the_matches_of_every_set_and_queue_that_started_before_a_moment(store):
    assert store.prune(at(4)) == 3

    assert ids(store, Selection(19, RANKED)) == ["KR_1", "NA1_2"]
    assert [(h.set_number, h.queue_id) for h in store.holdings()] == [(19, RANKED)]


def test_missing_names_the_ids_not_stored_and_a_repeated_add_keeps_one_copy(store):
    store.add_match("na1", match("NA1_1"))

    assert store.missing(["NA1_1", "NA1_9", "KR_1"]) == ["NA1_9"]
    assert store.count(Selection(19, RANKED)) == 3
