from tft_assistant.paths import state_path
from tft_assistant.refresh import refresh


def test_a_refresh_builds_before_its_first_crawl_and_waits_out_a_cycle_the_crawl_finished_early():
    done = []
    ticks = iter([0, 600, 1000, 4700])

    refresh(
        lambda: done.append("crawl"),
        lambda: done.append("build"),
        cycle_seconds=3600,
        cycles=2,
        clock=lambda: next(ticks),
        sleep=lambda seconds: done.append(f"sleep {seconds:.0f}"),
    )

    assert done == ["build", "crawl", "build", "sleep 3000", "crawl", "build", "sleep 0"]


def test_a_refresh_outlives_a_crawl_that_fails_and_crawls_again_next_cycle(capsys):
    done = []
    crawls = iter([RuntimeError("league-challenger on euw1 returned 401"), None])

    def crawl():
        done.append("crawl")
        outcome = next(crawls)
        if outcome:
            raise outcome

    refresh(
        crawl,
        lambda: done.append("build"),
        cycle_seconds=3600,
        cycles=2,
        clock=lambda: 0,
        sleep=lambda seconds: done.append(f"sleep {seconds:.0f}"),
    )

    assert done == ["build", "crawl", "build", "sleep 3600", "crawl", "build", "sleep 3600"]
    assert "returned 401" in capsys.readouterr().out


def test_state_lives_under_the_state_directory_when_one_is_named(monkeypatch, tmp_path):
    monkeypatch.delenv("TFT_STATE_DIR", raising=False)
    assert state_path("matches.db", "~/.local/share/tft-assistant/matches.db").name == "matches.db"
    assert "tft-assistant" in state_path("matches.db", "~/.local/share/tft-assistant/matches.db").parts

    monkeypatch.setenv("TFT_STATE_DIR", str(tmp_path))
    assert state_path("matches.db", "~/.local/share/tft-assistant/matches.db") == tmp_path / "matches.db"
