from datetime import UTC, datetime

import pytest

from tft_assistant.sets import GameSet, Patch, latest_set_number


def at(day):
    return datetime(2026, 12, day, tzinfo=UTC)


SET = GameSet(19, "TFTSet19", 1100, (Patch("19.1", at(2)), Patch("19.2", at(16))))


def test_a_patch_window_runs_to_the_next_patch_and_the_last_one_is_open():
    assert SET.window("19.1") == (at(2), at(16))
    assert SET.window("19.2") == (at(16), None)
    with pytest.raises(KeyError, match="no patch '19.9'"):
        SET.window("19.9")


def test_patch_at_names_the_live_patch_and_nothing_before_the_calendar():
    assert SET.patch_at(at(10)) == "19.1"
    assert SET.patch_at(at(16)) == "19.2"
    assert SET.patch_at(at(1)) is None


def test_a_selection_intersects_a_patch_with_a_time_window():
    assert (SET.selection().since, SET.selection().until) == (None, None)

    whole_patch = SET.selection(patch="19.1", platforms=("kr",))
    assert (whole_patch.set_number, whole_patch.queue_id, whole_patch.platforms) == (19, 1100, ("kr",))
    assert (whole_patch.since, whole_patch.until) == (at(2), at(16))

    last_days = SET.selection(patch="19.1", since=at(10), until=at(20))
    assert (last_days.since, last_days.until) == (at(10), at(16))

    assert SET.selection(patch="19.2", since=at(1)).since == at(16)


def test_the_standing_selections_cover_the_live_patch_its_recent_days_the_previous_patch_and_the_set():
    standing = SET.standing_selections(at(20))

    assert [(label, selection.since, selection.until) for label, selection in standing] == [
        ("Patch 19.2", at(16), None),
        ("Patch 19.2, last 3 days", at(17), None),
        ("Patch 19.2, last 24 hours", at(19), None),
        ("Patch 19.1", at(2), at(16)),
        ("Set 19, every stored match", None, None),
    ]


def test_a_set_file_loads_its_queue_and_a_calendar_of_timezone_aware_starts():
    game_set = GameSet.load(18)

    assert latest_set_number() >= 18
    assert game_set.ranked_queue == 1100
    assert game_set.patch_at(datetime(2026, 11, 20, tzinfo=UTC)) == "18.7"
