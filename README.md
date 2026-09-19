# quantum-optics-digest

Morning digest of new arXiv papers on superconducting artificial atoms and quantum optics on other platforms, ranked by a Claude Code cloud routine and published on GitHub Pages.

Design: [PLAN.md](PLAN.md). Routine steps: [ROUTINE.md](ROUTINE.md).

## Layout

```
scripts/fetch.py    arXiv → out/candidates.json, out/status.json, out/seen_next.json
scripts/render.py   out/ + out/ranking.json → digests/YYYY-MM-DD.json, docs/ (pages + feed.xml)
scripts/feedback.py 👍/👎 GitHub issues → state/feedback.json (read by the ranking prompt)

If export.arxiv.org is unreachable, each pool falls back to OpenAlex using its `backup_query`
(`config/queries.toml`). OpenAlex indexes preprints several days late and carries no arXiv
categories, so a backup run is much thinner than usual and the page banner says so. It exists to
keep the digest publishing through an arXiv outage, not to match it.
src/digest/         arxiv.py select.py openalex.py ranking.py store.py render.py pipeline.py
config/             queries.toml (arXiv queries per pool), settings.toml
interests/          one statement per section; the model ranks against these; watchlist.toml (authors)
prompts/            rank_daily.md, rank_weekly.md
state/              seen.json (advanced only on a successful render), openalex_cache.json, feedback.json
digests/            one JSON per run, the source of truth for the page
docs/               generated static site (GitHub Pages root), Atom feed at docs/feed.xml,
                    zotero.js + data/<run>.json for the in-page "save to Zotero" button;
                    data/latest.json always points at the newest daily run
widget/             native WidgetKit desktop widget (widget/README.md)
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

Citation counts and venues come from OpenAlex, which needs no API key (`[citations]` in `config/settings.toml`). Answers are cached in `state/openalex_cache.json`; unknown papers are retried after a day, counts refresh after a week. Every render then replays that cache over the digests of the last `backfill_days`, so a throttled run repairs itself and a preprint that later gains citations or a journal venue picks them up. To retry without a full run: `uv run scripts/render.py --backfill-only`.

## Feed, watchlist, feedback

- **Atom feed** at `/feed.xml`: one entry per digest run listing papers scored 50 or more (and watched ones) with their why-lines. Any reader or a Telegram RSS bot turns it into a notification.
- **Watchlist**: add authors to `interests/watchlist.toml`. Their papers are tagged `watch:<name>` and always appear in the main list with a ★ and a why-line, whatever the score. The score itself is not affected.
- **Feedback**: every paper has 👍 / 👎 links that open a prefilled GitHub issue (labels `feedback` + `up`/`down`). Each run starts with `uv run scripts/feedback.py`, which records open feedback issues in `state/feedback.json`, closes them, and the ranking prompt reads the last 50 as calibration examples. It uses `gh` when available and the GitHub REST API otherwise; reading a public repo's issues needs no token, closing them needs `GH_TOKEN`/`GITHUB_TOKEN`. Records are merged by issue number, so an issue left open is re-read harmlessly.
- **Desktop widget**: [`widget/`](widget/README.md) is a native macOS widget showing today's top papers, in the desktop widget gallery. It fetches the published `data/latest.json`, so it needs nothing from this checkout at runtime.
- **Explain**: every paper shown in full carries an Explain button that opens a plain-English account of it — what they did, how it works, why it matters, what to be skeptical of. The ranking model writes it during the run (field `eli5`, rules in `prompts/rank_daily.md`), so the page stays static and needs no JavaScript or API key. Papers with no explanation simply show no button. The house style lives in the `eli5` skill under `.claude/skills/`, adapted from [Companion-Inc/feynman](https://github.com/Companion-Inc/feynman) (MIT); ask Claude to "ELI5" any paper in a session to get the long form.
- **Save to Zotero**: click "Zotero…" in the page header once, enter your Zotero user ID and an API key with write access (zotero.org/settings/keys), and name a collection (default `to-read`, created if missing). The key is kept in that browser's localStorage only; nothing goes through the repo. On every page load the script (`src/digest/zotero.js`, copied to `docs/`) reads the collection and ticks the papers already in it. `+Z` creates a preprint item (arXiv DOI, abstract, authors) with a linked PDF and a why-note, or files an existing library item into the collection. Clicking a tick removes the paper from the collection; if the page created it and it is in no other collection, the item is deleted outright. Both ask for confirmation.
