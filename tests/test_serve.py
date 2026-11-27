import threading

import httpx
import pytest

from tft_assistant.edits import Edits
from tft_assistant.serve import server

COMP = "0123456789"


@pytest.fixture
def site(tmp_path):
    """The address of a server over a one-file site and an edit store on disk."""
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "index.html").write_text("<p>the page</p>")
    running = server(tmp_path / "site", Edits(tmp_path / "edits.db"), 0)
    threading.Thread(target=running.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{running.server_address[1]}"
    running.shutdown()
    running.server_close()


def test_the_page_is_served_beside_the_api(site):
    assert httpx.get(f"{site}/index.html").text == "<p>the page</p>"


def test_a_browser_keeps_an_icon_for_good_and_asks_again_for_the_page(site, tmp_path):
    (tmp_path / "site" / "icons").mkdir()
    (tmp_path / "site" / "icons" / "0123.png").write_bytes(b"a picture")

    kept = {path: httpx.get(f"{site}/{path}").headers["Cache-Control"] for path in ("icons/0123.png", "index.html", "icons/gone.png")}

    assert kept == {
        "icons/0123.png": "public, max-age=31536000, immutable",
        "index.html": "no-cache",
        "icons/gone.png": "no-cache",
    }


def test_edits_put_on_a_comp_are_read_back_with_its_set_and_no_other(site):
    put = httpx.put(f"{site}/api/edits/19/{COMP}", json={"name": "Reroll A", "notes": "roll at 8"})

    assert put.status_code == 204
    assert httpx.get(f"{site}/api/edits/19").json() == {COMP: {"name": "Reroll A", "notes": "roll at 8"}}
    assert httpx.get(f"{site}/api/edits/20").json() == {}


def test_an_empty_note_removes_the_edit(site):
    httpx.put(f"{site}/api/edits/19/{COMP}", json={"notes": "roll at 8"})

    httpx.put(f"{site}/api/edits/19/{COMP}", json={"notes": ""})

    assert httpx.get(f"{site}/api/edits/19").json() == {}


@pytest.mark.parametrize(
    ("path", "sent", "status"),
    [
        (f"/api/edits/19/{COMP}", {"json": {"rank": "S"}}, 400),
        (f"/api/edits/19/{COMP}", {"json": {"notes": "x" * 4001}}, 400),
        (f"/api/edits/19/{COMP}", {"json": ["notes"]}, 400),
        (f"/api/edits/19/{COMP}", {"content": "notes=x", "headers": {"Content-Type": "text/plain"}}, 415),
        ("/api/edits/19/not-a-comp-id", {"json": {"notes": "x"}}, 404),
    ],
    ids=["unknown field", "too long", "not an object", "not json", "not a comp id"],
)
def test_a_put_the_api_cannot_take_is_refused_and_stores_nothing(site, path, sent, status):
    assert httpx.put(f"{site}{path}", **sent).status_code == status
    assert httpx.get(f"{site}/api/edits/19").json() == {}
