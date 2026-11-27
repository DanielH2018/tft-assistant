# TFT Assistant — Claude Code context

`docs/plan.md` holds the design and the slice order. `docs/slice-0-findings.md` holds what the
live API showed, and it overrides any assumption about Riot's payload.

## Working here

- Run everything through `uv run`: `uv run pytest`, `uv run tft <command>`.
- A change lands through a pull request from a feature branch; a hook blocks a push to `main`.
  Merge your own pull request with `gh pr merge <n> --squash` once the tests pass. The operator
  ruled on 2026-11-26 that this repository needs no per-PR approval.
- The Riot key lives in `~/.config/tft-assistant/riot.env` or in `RIOT_API_KEY`. Never print the
  file, the variable or a request header.
- The repository is public. Crawled matches, built pages, personal notes and deployment
  hostnames stay out of it.
- No code names a unit, trait, item or mechanic of one set. A set's facts live under
  `src/tft_assistant/data/sets/<n>/`.
- Riot counts requests per key, and `riot.RateLimiter` counts per process. A second process that
  calls the API while `tft crawl` runs pushes both into 429 responses, so check for a running
  crawl before starting one. A deployment's `tft refresh` crawls all day on its key, so a local
  crawl on the same key collides with it: develop against the matches the store holds.
- `.github/workflows/ci.yml` runs the tests and builds the image on every commit. Wait for a
  pull request's checks before merging: `cc-wait gh-ci --pr <n>`.
- A release publishes the image, and a deployment follows releases. To release, raise `version`
  in `pyproject.toml`, run `uv lock`, and merge that. Then tag the merge commit `v<version>` and
  push the tag. CI refuses a tag that is not the project's version.
- `TFT_STATE_DIR` moves the match store, the comp ids, the edits and the static-data cache into
  one directory, which is how the image keeps them on its `/data` volume (`paths.state_path`).
