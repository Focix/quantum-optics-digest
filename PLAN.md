# Quantum Optics Digest — system design and implementation plan

Rev 2, 2026-09-10. Interactive version: https://claude.ai/code/artifact/58ccfec2-0590-4091-9332-6676b3e17921 (also `design/plan.html`).

## Summary

Every weekday at 09:00 Moscow a Claude Code cloud routine clones this repo, runs a Python script that pulls the last seven days of arXiv listings for two fixed query sets, drops anything already shown, enriches the rest with OpenAlex citation metadata, and hands the candidates to the routine's own model. The model sorts them into two sections, scores each against a written interest statement, writes a one-line reason per paper, and a render script turns the result into a static page committed to `docs/` and served by GitHub Pages. Saturday at 10:00 a second routine does the same for the week's superconducting quantum computing papers with a stronger model.

No MCP server is involved in the routine. The arxiv and Semantic Scholar MCP servers (the latter now unused) are thin wrappers over the same public APIs and cannot be attached to a cloud routine; they are for interactive sessions only.

## Decisions

| Decision | Answer |
|---|---|
| Topic | One digest, two daily sections. **A** superconducting artificial atoms, quantum-optics side only. **B** quantum optics on other platforms, ranked for novelty. (A third section on dark-matter searches was dropped on 2026-09-10.) |
| Excluded daily | Superconducting quantum computing (error correction, processors, gate benchmarks). Held for the weekly section. |
| Sources | Daily: arXiv for candidates, OpenAlex for citation counts and venues (Semantic Scholar rejected the key request, 2026-09-10). Weekly: arXiv plus an OpenAlex journal search for papers not on arXiv. |
| Window | Rolling 7 days, deduplicated against `state/seen.json` committed to the repo. |
| Runner | Claude Code cloud routine, repo cloned. Python does fetch/dedupe/enrich; the routine's model ranks. No MCP. |
| Intelligence | Model relevance ranking, one-line "why" per paper. Top 10 per section, titles-only list for the rest. |
| Output | Static HTML on GitHub Pages from a public repo. Today + previous 14 days on one page, older days as archive pages. |
| Failure | Red banner on the page with the error text. No email. |
| Schedule | Weekdays 09:00 Moscow = `0 6 * * 1-5` UTC. Saturday 10:00 Moscow = `0 7 * * 6` UTC. No DST in Moscow. |
| Models | Sonnet 5 daily, Opus 5 weekly. |
| Feedback | 👍/👎 per paper → GitHub issue → `state/feedback.json` → ranking prompt. Statements in `interests/*.md` still edited by hand. |
| Repo | `github.com/Focix/quantum-optics-digest`, clone at `~/Projects/quantum-optics-digest`. |

## Constraints found

- **Cloud routines cannot attach local MCP servers.** Routines accept only claude.ai connectors over HTTP. The arxiv / s2 / zotero servers are stdio uv tools registered only in Codex (`~/.codex/config.toml`).
- **Routines have no persistent disk.** State survives only by being committed.
- **The routine's network is an allowlist.** The Default environment reaches package registries and GitHub only. `export.arxiv.org` must be added under Custom network access (keep the default list). `api.semanticscholar.org` is reached by storing the key as an environment *API credential*, which attaches the key outside the sandbox and opens the host. Python, uv, gh are preinstalled (Ubuntu 24.04 x86_64).
- **Pushes to main are conditional.** A routine may push to a non-`claude/*` branch only if it is unprotected, nobody else has an open PR from it, and every commit is the user's. Routine commits carry the user's GitHub identity, so a solo unprotected main is fine.
- **OpenAlex terms.** No key; 100k requests/day, ~10 rps; a `mailto` parameter selects the polite pool. Semantic Scholar rejected the key request (2026-09-10).
- **arXiv API.** ~3 s between requests, occasional 503, announcements Sun–Thu ~20:00 US Eastern → nothing new on Sat/Sun mornings in Moscow.
- **GitHub Pages** on a free account needs a public repo; queries and interest statements will be public.
- **Machine is a MacBook Air.** Local scheduling rejected because the lid is often closed.

## Architecture

```
arXiv API ──┐
            ├─► fetch.py ──candidates──► routine model ──ranking──► render.py ──docs/──► git push ──► GitHub Pages
OpenAlex ───┘   │ ▲
                ▼ │
            state/ (seen.json, openalex_cache.json)   [committed]
```

- **fetch.py** — one arXiv query per section, last 7 days, sorted by submission date; drops seen IDs; tags survivors (`platform:sc`, `computing`, …); one OpenAlex works lookup per 50 remaining IDs; writes `out/candidates.json`, `out/status.json` and `out/seen_next.json`. `state/seen.json` is advanced by render.py only when a digest is written, so a failed ranking re-shows the same candidates next run.
- **Routine model** — reads candidates + `interests/*.md`, writes `out/ranking.json` per the contract below. Never fetches.
- **render.py** — merges into `digests/YYYY-MM-DD.json`, regenerates `docs/index.html` from the last 15 digests plus one archive page per older day; shows the banner when `status.json` reports an error or the newest digest is stale.
- A uv project (`pyproject.toml`): logic in the `src/digest` package, `scripts/` are thin CLIs run with `uv run`. Deps: `httpx`, `tzdata`; the Atom feed is parsed with the standard library. Tests with pytest, `mypy --strict`.

## Repository layout

```
scripts/      fetch.py  render.py                      thin CLIs
src/digest/   arxiv.py select.py openalex.py ranking.py store.py render.py pipeline.py
tests/        pytest suite (mock transports, no network)
config/       queries.toml  settings.toml
interests/    a_superconducting.md  b_other_platforms.md  c_dark_matter.md  weekly_computing.md
prompts/      rank_daily.md  rank_weekly.md
state/        seen.json  openalex_cache.json
digests/      YYYY-MM-DD.json
docs/         index.html  style.css  archive/YYYY-MM-DD.html      (GitHub Pages root)
out/          gitignored per-run scratch
ROUTINE.md    the exact prompt the routine follows
PLAN.md       this document
design/       plan.html
```

## Queries

arXiv search syntax, `sortBy=submittedDate`, `max_results=200`, client-side 7-day filter. Broad on purpose; exclusion is the model's job.

| Section | Categories | Query core | Expected/day |
|---|---|---|---|
| A + weekly pool | quant-ph, cond-mat.mes-hall, cond-mat.supr-con | `abs:"superconducting qubit" OR abs:transmon OR abs:fluxonium OR abs:"circuit QED" OR abs:"circuit quantum electrodynamics" OR abs:"artificial atom" OR abs:"microwave photon" OR abs:"Josephson junction"` | 20–40, of which 3–8 optics |
| B | quant-ph, physics.optics, physics.atom-ph | `abs:"cavity QED" OR abs:"waveguide QED" OR abs:"single photon" OR abs:"single-photon" OR abs:"photon statistics" OR abs:"resonance fluorescence" OR abs:"squeezed light" OR abs:"quantum emitter" OR abs:"giant atom" OR abs:optomechanical OR (abs:Rydberg AND abs:photon) OR (abs:"trapped ion" AND abs:photon) OR (abs:"quantum dot" AND abs:photon)` minus the A pool | 20–40 |

The A pool is split by the model: optics → A, computing → tagged and held for Saturday. B candidates also in the A pool are removed so a paper appears once. Weekly adds one OpenAlex journal search: `"superconducting qubit" OR transmon OR fluxonium`, last 14 days, journal articles without an arXiv version.

## Interest statements (drafts; edit in `interests/`)

**A. Superconducting artificial atoms — relevant.** Quantum optics with superconducting circuits: single- and few-photon microwave sources; photon correlation measurements (g2, cross-correlation, antibunching); temporal/spectral shaping of itinerant microwave photons; quantum state transfer between qubits, cavities or nodes; quantum information protocols on a few qubits where the physics, not the benchmark, is the point; time-domain and time-bin entangled states; waveguide QED, giant atoms, dressed states, scattering off one or a few artificial atoms. Not relevant daily: error correction, surface codes, multi-qubit processors, gate fidelity records, fabrication-only papers, calibration tooling → tag `computing`, low daily score.

**B. Other platforms — already standard.** Score low unless there is a genuinely new twist: transmission and reflection measurements of a single emitter coupled to an open transmission line or open waveguide, including the usual extinction, Mollow triplet and power-broadening results. Score high: experiments or theory showing an effect, regime or protocol not obvious from the standard cavity/waveguide QED toolbox, on any platform (atoms, ions, quantum dots, colour centres, optomechanics, photonic circuits).

**Weekly — superconducting quantum computing, what is hot.** From the week's computing-tagged papers pick ten a researcher in superconducting qubits would want to have heard of: new records, new qubit designs or couplers, new architectures, error-correction milestones, results from major groups, anything already collecting citations. Prefer results over surveys.

## Ranking contract

```jsonc
// out/candidates.json (fetch.py)
[{ "id": "2609.01234", "title": "...", "authors": ["..."], "abstract": "...",
   "categories": ["quant-ph"], "submitted": "2026-09-13", "pool": "A",
   "tags": ["platform:sc", "computing"],
   "s2": { "citationCount": 0, "tldr": "...", "venue": "" } }]

// out/ranking.json (routine model)
{ "run": "2026-09-14", "mode": "daily",
  "items": [{ "id": "2609.01234", "section": "A", "score": 82, "kind": "E",
              "why": "First g2 measurement of a shaped microwave photon from a fluxonium." }] }
```

- `score` 0–100 against the section statement. ≥80 read today; 50–79 worth the title; <50 matched the query, not the interest.
- `section` ∈ {A, B, computing}. `computing` items are held for Saturday.
- `why` ≤ 25 words, present tense, names the concrete result, never restates the title.
- `kind` ∈ {T, E, TE}: theory, experiment, or both; shown as a badge on every paper.
- Cap 120 candidates per run (newest kept, overflow noted in status). ~60 abstracts ≈ 15k input tokens.
- Render: top 10 per section with why-line; the rest titles-only. Nothing dropped.

## The page

Static, Moscow dates, no JS required (details/summary for collapsed lists). Three pages with a shared nav: `index.html` for section A, `b.html` for section B, `weekly.html` for the Saturday digest plus the computing pool collected since the last one.
- **Banner** only when status has an error or the newest digest is >1 working day old; carries the failing step, error text, and a link to the run log.
- **Today**: sections A and B — title → abstract page, first three authors, date, why-line, OpenAlex citation count and venue when present; collapsed "also matched" list per section.
- **This week** (Saturdays): the weekly ten with citation counts.
- **Previous days**: last 14, collapsed, with counts.
- **Archive** links at the foot.

## Routines

Both use the Default environment, tools Bash/Read/Write/Edit/Glob/Grep only. The prompt lives in `ROUTINE.md`; the routine message is just "read ROUTINE.md and follow it for mode daily|weekly".

| Routine | Cron (UTC) | Model | Steps |
|---|---|---|---|
| Daily digest | `0 6 * * 1-5` | Sonnet 5 | 1 `uv run scripts/fetch.py --mode daily` · 2 rank → `out/ranking.json` · 3 `uv run scripts/render.py` · 4 commit digests/state/docs, push main · 5 on any failure still run render with `--error "text"` and commit |
| Weekly computing | `0 7 * * 6` | Opus 5 | same with `--mode weekly` (week's computing-tagged digests + OpenAlex journal search) |

**Citations**: OpenAlex, no key. `api.openalex.org` must be on the environment's allowed domains next to `export.arxiv.org`. `[citations] enabled = false` in `config/settings.toml` switches it off.

## Rate limits and failure handling

- **OpenAlex**: single client in `openalex.py`, ≤1 rps, retries 429/5xx with exponential backoff from 2 s, max 5 attempts, caches every answer with a fetch date in `state/openalex_cache.json` (misses retried after 1 day, hits after 7). Daily traffic: one request per 50 IDs. Weekly: plus one journal search.
- **arXiv**: 3 s between requests, <10 requests per run, 503 retried ×3 after 10 s.
- **Missed run**: absorbed by the 7-day window; no replay needed.
- **Partial failure**: OpenAlex down → digest without enrichment + banner. One arXiv section down → other sections still render.
- **Bad model output**: render.py validates ranking.json; on violation renders the raw candidate list unranked + banner.

## Implementation plan

| Phase | Owner | Steps | Done when |
|---|---|---|---|
| 0 · Access | you | Run `/web-setup` in a Claude Code terminal (syncs the Focix gh token to claude.ai). At claude.ai/code open the cloud-icon environment selector, edit the environment: network Custom, add `export.arxiv.org` and `api.openalex.org`, keep "include default list". | A cloud session from the repo can curl both hosts. |
| 0 · Local | claude | Register arxiv + s2 MCP servers in Claude Code at user scope. Create the public GitHub repo from this folder and push. | `claude mcp list` shows both connected; repo exists. |
| 1 · Fetch | claude | s2.py, fetch.py, queries.toml, settings.toml. Backfill 14 days locally, measure volumes, tune phrases. | Per-section counts for two weeks within expected ranges; seen.json populated. |
| 2 · Ranking | claude | Interest statements + rank_daily.md. Two manual ranking runs on real candidates in a local session. | You approve both top-10 lists, or edit statements and rerun once. |
| 3 · Page | claude | render.py + style.css; generate docs from backfill; enable Pages on `docs/`. | Page loads on phone and laptop, both themes, 14 days visible. |
| 4 · Routines | claude | ROUTINE.md; create daily routine, run once by hand, read log, confirm commit + page update; then weekly. | One successful manual run each, commit on main by the routine. |
| 5 · Observe | you | Read five weekdays of digests, note mis-rankings, edit statements once. | One week of digests, one statement edit, v2 decision. |

First run shows the whole 7-day window (long). Backfill in phase 1 marks older papers seen, so from day two only new submissions appear.

## Risks and later work

- **Cloud egress** depends on the allowlist entries for `export.arxiv.org` and `api.openalex.org`; verified in phase 0. Fallback: launchd + `claude -p` locally, page as a Claude artifact.
- **Git push from the routine** depends on `/web-setup` and an unprotected main with only Focix commits. A failed push leaves the run log as the only record; the next run redoes the work since seen.json was never committed.
- **Ranking variance** day to day; rubric + fixed statements reduce it. v2: pin a paper's score at first display.
- **Public reading list**; switch to private repo + rendered Markdown if uncomfortable.
- **Query drift**; titles-only list exposes misses inside the pool. Revisit queries.toml quarterly.

Done 2026-09-10 (v2 first round): Atom feed at `docs/feed.xml`; author watchlist in `interests/watchlist.toml` (tag `watch:<name>`, always shown with a why-line); 👍/👎 links per paper that open a prefilled GitHub issue, folded into `state/feedback.json` by `scripts/feedback.py` at the start of each run and read by the ranking prompts as calibration.

Next candidates: "aged well" re-check of 30/90-day-old papers against OpenAlex; published-venue badge; weekly narrative paragraph; client-side search; Zotero/BibTeX export; Telegram push of the top three; quarterly query miss-audit.
