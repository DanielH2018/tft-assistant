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
uv run tft crawl      # store the matches of the NA, EUW and KR apex ladders
uv run tft comps --patch 18.7          # comps of a patch; --since, --until and --platform narrow it
uv run tft build --out site            # write site/index.html from the stored matches
uv run pytest
```

## Riot's terms

This project runs on a personal API key, which Riot issues for private use. The source is
public; a deployment of it is not open to the public.

TFT Assistant isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot
Games or anyone officially involved in producing or managing Riot Games properties. Riot Games,
and all associated properties are trademarks or registered trademarks of Riot Games, Inc.
