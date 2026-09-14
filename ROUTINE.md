# Routine instructions

You are running inside a Claude Code cloud routine with this repository cloned. The message you received names a mode: `daily` or `weekly`. Follow the steps for that mode exactly. Use only Bash, Read, Write, Edit, Glob and Grep. Never fetch URLs yourself; the scripts do all network access.

## Daily (weekdays 09:00 Moscow)

1. Pull reader feedback, then fetch candidates:
   ```
   uv run scripts/feedback.py
   uv run scripts/fetch.py --mode daily
   ```
   `feedback.py` folds 👍/👎 issues into `state/feedback.json` and closes them; it never fails the run (it prefers `gh` and falls back to the GitHub REST API when `gh` is missing, as it is in the cloud environment; without a `GH_TOKEN` it records the issues but leaves them open, which is harmless — continue past any warning). `fetch.py` prints a status object. Exit code 1 means a partial failure that is already recorded in `out/status.json`; continue anyway if `out/candidates.json` exists. If the script crashed (no `out/candidates.json`), go to step 5.
2. Read `prompts/rank_daily.md`, `interests/a_superconducting.md`, `interests/b_other_platforms.md`, `state/feedback.json`, and `out/candidates.json`. Rank the candidates per the prompt and write `out/ranking.json`. Use today's date in Moscow for `run`.
3. Render:
   ```
   uv run scripts/render.py --mode daily
   ```
   It validates the ranking; if it reports `status error: ranking invalid`, fix `out/ranking.json` and rerun once.
4. Commit and push:
   ```
   git add digests state docs
   git commit -m "Daily digest $(TZ=Europe/Moscow date +%F)"
   git push origin main
   ```
5. On any failure you cannot recover from, still publish the banner so the page tells the reader what went wrong:
   ```
   uv run scripts/render.py --mode daily --error "step N: <one line with the error text>" --log-url "<URL of this run's log if you know it>"
   git add docs && git commit -m "Daily digest failed: <short reason>" && git push origin main
   ```

## Weekly (Saturday 10:00 Moscow)

Same as daily (including `scripts/feedback.py` first) with `--mode weekly`, `prompts/rank_weekly.md`, `interests/weekly_computing.md`, and the commit message `Weekly computing digest <date>`. The weekly fetch reads the week's daily digests and does no arXiv call.

## Notes

- `out/` is scratch and is gitignored. `state/seen.json` is only advanced by a successful render, so a failed run repeats the same candidates next time.
- Never edit `interests/`, `config/` or `prompts/` from a routine; the owner edits those by hand. `interests/watchlist.toml` lists authors whose papers always get a why-line; `fetch.py` tags them `watch:<name>`.
- `state/feedback.json` is written only by `scripts/feedback.py`; commit it with the rest of `state`.
- `fetch.py` is deliberately slow: it paces arXiv requests and rides out 429/503 throttling with a jittered doubling backoff (`[arxiv]` in `config/settings.toml`), honouring `Retry-After`. A healthy run takes seconds, but a throttled one can take ~15 minutes per pool before it gives up. **Let it run — do not interrupt it, and never re-run it by hand to "retry faster"; that is what made the 2026-09-14 run worse.** If it still reports 429 for every pool, arXiv is refusing us outright: go to step 5 and let tomorrow's run pick the candidates up (`state/seen.json` is not advanced).
- Citation counts come from OpenAlex (no key). If `api.openalex.org` is unreachable the status shows `"citations": "error: ..."`, the digest still renders, and the banner explains.
