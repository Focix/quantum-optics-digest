# Routine instructions

You are running inside a Claude Code cloud routine with this repository cloned. It runs once a week, Monday 09:00 Moscow, and produces one digest with four sections: A superconducting artificial atoms, B quantum optics on other platforms, C foundations of quantum mechanics, and computing. Follow these steps exactly. Use only Bash, Read, Write, Edit, Glob and Grep. Never fetch URLs yourself; the scripts do all network access.

## Steps

1. Pull reader feedback, then fetch candidates:
   ```
   uv run scripts/feedback.py
   uv run scripts/fetch.py
   ```
   `feedback.py` folds 👍/👎 issues into `state/feedback.json` and closes them; it never fails the run (it prefers `gh` and falls back to the GitHub REST API when `gh` is missing, as it is in the cloud environment; without a `GH_TOKEN` it records the issues but leaves them open, which is harmless — continue past any warning). `fetch.py` makes one arXiv request per pool (A, B, C) plus an OpenAlex journal search and prints a status object. Exit code 1 means a partial failure that is already recorded in `out/status.json`; continue anyway if `out/candidates.json` exists. If the script crashed (no `out/candidates.json`), go to step 5.
2. Read `prompts/rank_weekly.md`, `interests/a_superconducting.md`, `interests/b_other_platforms.md`, `interests/c_foundations.md`, `interests/computing.md`, `state/feedback.json`, and `out/candidates.json`. Rank the candidates per the prompt and write `out/ranking.json`. Use today's date in Moscow for `run`. There can be well over a hundred candidates; write the file in one go with every id.
3. Render:
   ```
   uv run scripts/render.py
   ```
   It validates the ranking; if it reports `status error: ranking invalid`, fix `out/ranking.json` and rerun once.
4. Commit and push:
   ```
   git add digests state docs
   git commit -m "Weekly digest $(TZ=Europe/Moscow date +%F)"
   git push origin main
   ```
5. On any failure you cannot recover from, still publish the banner so the page tells the reader what went wrong:
   ```
   uv run scripts/render.py --error "step N: <one line with the error text>" --log-url "<URL of this run's log if you know it>"
   git add docs && git commit -m "Weekly digest failed: <short reason>" && git push origin main
   ```

## Notes

- `out/` is scratch and is gitignored. `state/seen.json` is only advanced by a successful render, so a failed run repeats the same candidates next time.
- The fetch window is 14 days although the run is weekly: arXiv lists a paper up to about three days after its submission date, and `state/seen.json` drops the overlap.
- Never edit `interests/`, `config/` or `prompts/` from a routine; the owner edits those by hand. `interests/watchlist.toml` lists authors whose papers always get a why-line; `fetch.py` tags them `watch:<name>`.
- `state/feedback.json` is written only by `scripts/feedback.py`; commit it with the rest of `state`.
- `fetch.py` retries arXiv 429/503 with a jittered doubling backoff (`[arxiv]` in `config/settings.toml`), then gives up quickly and refills the pool from OpenAlex instead. A fully throttled run takes about two minutes. **Let it run — never re-run it by hand to "retry faster"; that is what made the 2026-09-14 run worse.**
- A pool whose status starts with `backup:` came from OpenAlex, not arXiv. That is a **success, not a failure**: publish it normally, do not use the step 5 error render. `status["error"]` already carries a line explaining the degraded source, and the page banner shows it. Expect far fewer papers than usual, and none from the last few days — OpenAlex indexes preprints late.
- Only when every pool reports `error:` (arXiv failed *and* the backup failed or is disabled) is the run genuinely broken; then go to step 5. A single failed pool still publishes the others.
- Citation counts come from OpenAlex (no key). If `api.openalex.org` is unreachable the status shows `"citations": "error: ..."`, the digest still renders, and the page banner explains.
- Every render also retries the counts earlier runs missed, across the last 30 days, and records the outcome in `status.backfill`. It may rewrite older files in `digests/`; step 4 already commits them. A throttled lookup therefore fixes itself on the next run, so **do not hand-retry one** — and never edit a past digest to add counts. To repair between runs: `uv run scripts/render.py --backfill-only`.
- `digests/` also holds the daily digests from before 2026-09-28. They are history: render them, never rewrite them by hand.
