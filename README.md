# TFT Assistant

A personal second-monitor reference for Teamfight Tactics. It crawls ranked matches from
Riot's API, derives comps, item groups and early-game plans from the final boards, and builds
static pages that put one comp's core, flex packages, items and unlock conditions on one
screen.

[docs/plan.md](docs/plan.md) holds the design and the slice order.

## Status

Slice 0, the feasibility spike. The crawl, the match store, the static-data join and the trait
module exist. [docs/slice-0-findings.md](docs/slice-0-findings.md) records what the spike has
measured.

## Run it

The client reads the key from the `RIOT_API_KEY` environment variable, or from
`~/.config/tft-assistant/riot.env` as a line `RIOT_API_KEY=<key>`.

```sh
uv run tft probe      # one ladder, one match: report the rate limits and payload fields
uv run tft crawl      # store the matches of the NA, EUW and KR apex ladders
uv run pytest
```

## Riot's terms

This project runs on a personal API key, which Riot issues for private use. The source is
public; a deployment of it is not open to the public.

TFT Assistant isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot
Games or anyone officially involved in producing or managing Riot Games properties. Riot Games,
and all associated properties are trademarks or registered trademarks of Riot Games, Inc.
