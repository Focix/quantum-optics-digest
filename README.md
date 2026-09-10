# quantum-optics-digest

Morning digest of new arXiv papers on superconducting artificial atoms and quantum optics on other platforms, ranked by a Claude Code cloud routine and published on GitHub Pages.

Design: [PLAN.md](PLAN.md). Routine steps: [ROUTINE.md](ROUTINE.md).

## Layout

```
scripts/fetch.py    arXiv → out/candidates.json, out/status.json, out/seen_next.json
scripts/render.py   out/ + out/ranking.json → digests/YYYY-MM-DD.json, docs/ (pages + feed.xml)
scripts/feedback.py 👍/👎 GitHub issues → state/feedback.json (read by the ranking prompt)
src/digest/         arxiv.py select.py openalex.py ranking.py store.py render.py pipeline.py
config/             queries.toml (arXiv queries per pool), settings.toml
interests/          one statement per section; the model ranks against these; watchlist.toml (authors)
prompts/            rank_daily.md, rank_weekly.md
state/              seen.json (advanced only on a successful render), openalex_cache.json, feedback.json
digests/            one JSON per run, the source of truth for the page
docs/               generated static site (GitHub Pages root), Atom feed at docs/feed.xml
```

## Run locally

```
uv sync
uv run scripts/fetch.py --mode daily            # ~10 s, three arXiv requests
# rank out/candidates.json per prompts/rank_daily.md into out/ranking.json
uv run scripts/render.py --mode daily
open docs/index.html
```

Tests and typecheck: `uv run pytest` and `uv run mypy`.

Citation counts and venues come from OpenAlex, which needs no API key (`[citations]` in `config/settings.toml`). Answers are cached in `state/openalex_cache.json`; unknown papers are retried after a day, counts refresh after a week.

## Feed, watchlist, feedback

- **Atom feed** at `/feed.xml`: one entry per digest run listing papers scored 50 or more (and watched ones) with their why-lines. Any reader or a Telegram RSS bot turns it into a notification.
- **Watchlist**: add authors to `interests/watchlist.toml`. Their papers are tagged `watch:<name>` and always appear in the main list with a ★ and a why-line, whatever the score. The score itself is not affected.
- **Feedback**: every paper has 👍 / 👎 links that open a prefilled GitHub issue (labels `feedback` + `up`/`down`). Each run starts with `uv run scripts/feedback.py`, which records open feedback issues in `state/feedback.json`, closes them, and the ranking prompt reads the last 50 as calibration examples.
