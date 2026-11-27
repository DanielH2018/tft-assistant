# TFT Assistant

A personal second-monitor reference for Teamfight Tactics. It crawls ranked matches from
Riot's API, derives comps, item groups and early-game plans from the final boards, and builds
static pages that put one comp's core, flex packages, items and unlock conditions on one
screen.

[docs/plan.md](docs/plan.md) holds the design and the slice order.

## Status

Slice 1, the comps view. `tft build` writes one self-contained page: a comp list beside a detail
pane with the comp's core, flex packages, traits, item priority and default board.
[docs/slice-0-findings.md](docs/slice-0-findings.md) records what the feasibility spike measured.

## Run it

The client reads the key from the `RIOT_API_KEY` environment variable, or from
`~/.config/tft-assistant/riot.env` as a line `RIOT_API_KEY=<key>`.

```sh
uv run tft probe      # one ladder, one match: report the rate limits and payload fields
uv run tft crawl      # store the matches of the NA, EUW and KR ladders, from the top
uv run tft comps --patch 18.7          # comps of a patch; --since, --until and --platform narrow it
uv run tft build --out site            # write site/index.html from the stored matches
uv run tft refresh --out site          # build, then crawl and build again every hour, until stopped
uv run tft serve --site site           # serve the page on port 8080, and keep the notes written on it
uv run pytest
```

## Run it unattended

`tft refresh` is the unattended run. It builds the page from the matches the store holds, then
crawls and builds again once a cycle. A cycle lasts `--minutes`, an hour unless told otherwise.
After each crawl it deletes matches that started more than `--keep-days` ago, 30 unless told
otherwise, so the store stops growing.

The image runs it. CI builds and proves the image on every commit, and publishes
`ghcr.io/danielh2018/tft-assistant` when a version tag such as `v0.2.0` is pushed, tagged
`0.2.0` and `latest`.

```sh
docker run -e RIOT_API_KEY -v tft-data:/data ghcr.io/danielh2018/tft-assistant
```

| | |
|---|---|
| `/data` | The one directory the run writes: the match store, the static-data cache and the page under `site/`. `TFT_STATE_DIR` names it. |
| `RIOT_API_KEY` | The key, given at run time. The image holds none. |
| User | The image runs as user 10001 and works as any other user that can write `/data`. |
| Serving | The run serves nothing. Any static file server pointed at `/data/site` serves the page. `tft serve --site /data/site` serves it too, and keeps the notes a reader writes on it under `/data/keep`, beside the comp ids the notes are keyed by. That directory is the one thing here no API gives back, so back it up. The server checks nobody's identity: put it behind a login. |

## Riot's terms

This project runs on a personal API key, which Riot issues for private use. The source is
public; a deployment of it is not open to the public.

TFT Assistant isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot
Games or anyone officially involved in producing or managing Riot Games properties. Riot Games,
and all associated properties are trademarks or registered trademarks of Riot Games, Inc.
