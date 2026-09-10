# Routine instructions

You are running inside a Claude Code cloud routine with this repository cloned. The message you received names a mode: `daily` or `weekly`. Follow the steps for that mode exactly. Use only Bash, Read, Write, Edit, Glob and Grep. Never fetch URLs yourself; the scripts do all network access.

## Daily (weekdays 09:00 Moscow)

1. Fetch candidates:
   ```
   uv run scripts/fetch.py --mode daily
   ```
   It prints a status object. Exit code 1 means a partial failure that is already recorded in `out/status.json`; continue anyway if `out/candidates.json` exists. If the script crashed (no `out/candidates.json`), go to step 5.
2. Read `prompts/rank_daily.md`, `interests/a_superconducting.md`, `interests/b_other_platforms.md`, and `out/candidates.json`. Rank the candidates per the prompt and write `out/ranking.json`. Use today's date in Moscow for `run`.
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

Same as daily with `--mode weekly`, `prompts/rank_weekly.md`, `interests/weekly_computing.md`, and the commit message `Weekly computing digest <date>`. The weekly fetch reads the week's daily digests and does no arXiv call.

## Notes

- `out/` is scratch and is gitignored. `state/seen.json` is only advanced by a successful render, so a failed run repeats the same candidates next time.
- Never edit `interests/`, `config/` or `prompts/` from a routine; the owner edits those by hand.
- Citation counts come from OpenAlex (no key). If `api.openalex.org` is unreachable the status shows `"citations": "error: ..."`, the digest still renders, and the banner explains.
