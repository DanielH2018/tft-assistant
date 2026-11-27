import socket
import struct
import threading
import time

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


def test_the_health_answer_is_small_and_says_whether_the_site_has_a_page(site, tmp_path):
    with_page = httpx.get(f"{site}/api/health")
    (tmp_path / "site" / "index.html").unlink()
    without = httpx.get(f"{site}/api/health")

    assert (with_page.status_code, with_page.json()) == (200, {"page": True})
    assert (without.status_code, without.json()) == (503, {"page": False})


def test_a_client_that_hangs_up_mid_answer_costs_one_log_line_and_no_traceback(site, tmp_path, capfd):
    (tmp_path / "site" / "index.html").write_bytes(b"x" * 20_000_000)
    host, port = site.removeprefix("http://").split(":")

    with socket.create_connection((host, int(port))) as client:
        client.sendall(b"GET /index.html HTTP/1.1\r\nHost: test\r\n\r\n")
        client.recv(1024)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    logged = ""
    for _ in range(50):
        logged += capfd.readouterr().err
        if "hung up" in logged:
            break
        time.sleep(0.1)

    assert "hung up before the answer was sent" in logged
    assert "Traceback" not in logged
    assert httpx.get(f"{site}/api/health").status_code == 200


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
