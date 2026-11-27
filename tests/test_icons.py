import httpx

from tft_assistant.icons import mirror


def snapshot_of(*urls):
    units = {f"U{index}": {"name": f"U{index}", "icon": url} for index, url in enumerate(urls)}
    return {"units": units, "traits": {"T": {"name": "T", "icon": None}}, "items": {}}


def test_a_mirrored_icon_is_a_file_in_the_site_that_the_snapshot_points_at(tmp_path):
    snapshot = snapshot_of("https://icons.test/a.png", "https://icons.test/b.png")
    pictures = {"https://icons.test/a.png": b"picture a", "https://icons.test/b.png": b"picture b"}

    line = mirror([snapshot], tmp_path / "site", fetch=pictures.__getitem__, cache=tmp_path / "cache")

    paths = [unit["icon"] for unit in snapshot["units"].values()]
    assert [(tmp_path / "site" / path).read_bytes() for path in paths] == [b"picture a", b"picture b"]
    assert snapshot["traits"]["T"]["icon"] is None
    assert line == "2 icons in the site"


def test_an_icon_that_cannot_be_downloaded_keeps_its_address(tmp_path):
    snapshot = snapshot_of("https://icons.test/a.png", "https://icons.test/gone.png")

    def fetch(url):
        if url.endswith("gone.png"):
            raise httpx.ConnectError("no route")
        return b"picture a"

    line = mirror([snapshot], tmp_path / "site", fetch=fetch, cache=tmp_path / "cache")

    assert snapshot["units"]["U1"]["icon"] == "https://icons.test/gone.png"
    assert snapshot["units"]["U0"]["icon"].startswith("icons/")
    assert line == "1 icons in the site, 1 left at their source"


def test_a_second_build_downloads_nothing_and_removes_the_icons_it_no_longer_names(tmp_path):
    downloads = []

    def fetch(url):
        downloads.append(url)
        return url.encode()

    both = snapshot_of("https://icons.test/a.png", "https://icons.test/b.png")
    mirror([both], tmp_path / "site", fetch=fetch, cache=tmp_path / "cache")
    dropped = both["units"]["U1"]["icon"]

    one = snapshot_of("https://icons.test/a.png")
    mirror([one], tmp_path / "site", fetch=fetch, cache=tmp_path / "cache")

    assert downloads == ["https://icons.test/a.png", "https://icons.test/b.png"]
    assert [path.name for path in (tmp_path / "site" / "icons").iterdir()] == [one["units"]["U0"]["icon"].split("/")[1]]
    assert not (tmp_path / "site" / dropped).exists()
