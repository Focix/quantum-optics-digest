# Quantum Optics Digest — system design and implementation plan

Rev 2, 2026-09-10. Interactive version: https://claude.ai/code/artifact/58ccfec2-0590-4091-9332-6676b3e17921 (also `design/plan.html`).

## Summary

Every weekday at 09:00 Moscow a Claude Code cloud routine clones this repo, runs a Python script that pulls the last seven days of arXiv listings for three fixed query sets, drops anything already shown, enriches the rest with Semantic Scholar metadata, and hands the candidates to the routine's own model. The model sorts them into three sections, scores each against a written interest statement, writes a one-line reason per paper, and a render script turns the result into a static page committed to `docs/` and served by GitHub Pages. Saturday at 10:00 a second routine does the same for the week's superconducting quantum computing papers with a stronger model.

No MCP server is involved in the routine. The arxiv and Semantic Scholar MCP servers are thin wrappers over the same public APIs and cannot be attached to a cloud routine; they are for interactive sessions only.

## Decisions

| Decision | Answer |
|---|---|
| Topic | One digest, three daily sections. **A** superconducting artificial atoms, quantum-optics side only. **B** quantum optics on other platforms, ranked for novelty. **C** dark matter / axion searches with superconducting qubits or single microwave photon detection. |
| Excluded daily | Superconducting quantum computing (error correction, processors, gate benchmarks). Held for the weekly section. |
| Sources | Daily: arXiv for candidates, Semantic Scholar for enrichment. Weekly: arXiv plus a Semantic Scholar bulk search for journal papers not on arXiv. |
| Window | Rolling 7 days, deduplicated against `state/seen.json` committed to the repo. |
| Runner | Claude Code cloud routine, repo cloned. Python does fetch/dedupe/enrich; the routine's model ranks. No MCP. |
| Intelligence | Model relevance ranking, one-line "why" per paper. Top 10 per section, titles-only list for the rest. |
| Output | Static HTML on GitHub Pages from a public repo. Today + previous 14 days on one page, older days as archive pages. |
| Failure | Red banner on the page with the error text. No email. |
| Schedule | Weekdays 09:00 Moscow = `0 6 * * 1-5` UTC. Saturday 10:00 Moscow = `0 7 * * 6` UTC. No DST in Moscow. |
| Models | Sonnet 5 daily, Opus 5 weekly. |
| Feedback | Read-only v1. Edit `interests/*.md` by hand. |
| Repo | `github.com/Focix/quantum-optics-digest`, clone at `~/Projects/quantum-optics-digest`. |

## Constraints found

- **Cloud routines cannot attach local MCP servers.** Routines accept only claude.ai connectors over HTTP. The arxiv / s2 / zotero servers are stdio uv tools registered only in Codex (`~/.codex/config.toml`).
- **Routines have no persistent disk.** State survives only by being committed.
- **The routine's network is an allowlist.** The Default environment reaches package registries and GitHub only. `export.arxiv.org` must be added under Custom network access (keep the default list). `api.semanticscholar.org` is reached by storing the key as an environment *API credential*, which attaches the key outside the sandbox and opens the host. Python, uv, gh are preinstalled (Ubuntu 24.04 x86_64).
- **Pushes to main are conditional.** A routine may push to a non-`claude/*` branch only if it is unprotected, nobody else has an open PR from it, and every commit is the user's. Routine commits carry the user's GitHub identity, so a solo unprotected main is fine.
- **Semantic Scholar terms.** 1 request/second, exponential backoff on 429, keys unused ~60 days may be revoked (weekday use keeps it alive).
- **arXiv API.** ~3 s between requests, occasional 503, announcements Sun–Thu ~20:00 US Eastern → nothing new on Sat/Sun mornings in Moscow.
- **GitHub Pages** on a free account needs a public repo; queries and interest statements will be public.
- **Machine is a MacBook Air.** Local scheduling rejected because the lid is often closed.

## Architecture

```
arXiv API ──┐
            ├─► fetch.py ──candidates──► routine model ──ranking──► render.py ──docs/──► git push ──► GitHub Pages
S2 API ─────┘   │ ▲
                ▼ │
            state/ (seen.json, s2_cache.json)   [committed]
```

- **fetch.py** — one arXiv query per section, last 7 days, sorted by submission date; drops seen IDs; tags survivors (`platform:sc`, `computing`, …); one S2 `POST /paper/batch` for the remaining IDs; writes `out/candidates.json` and `out/status.json`. Updates `seen.json` only after a successful write.
- **Routine model** — reads candidates + `interests/*.md`, writes `out/ranking.json` per the contract below. Never fetches.
- **render.py** — merges into `digests/YYYY-MM-DD.json`, regenerates `docs/index.html` from the last 15 digests plus one archive page per older day; shows the banner when `status.json` reports an error or the newest digest is stale.
- Scripts use PEP 723 inline metadata and run with `uv run`. Deps: `httpx`, `feedparser`.

## Repository layout

```
scripts/      fetch.py  render.py  s2.py
config/       queries.toml  settings.toml
interests/    a_superconducting.md  b_other_platforms.md  c_dark_matter.md  weekly_computing.md
prompts/      rank_daily.md  rank_weekly.md
state/        seen.json  s2_cache.json
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
| C | quant-ph, hep-ex, hep-ph, physics.ins-det | `(abs:"dark matter" OR abs:axion OR abs:"dark photon" OR abs:"hidden photon") AND (abs:qubit OR abs:superconducting OR abs:"single photon" OR abs:haloscope OR abs:"photon counting" OR abs:"microwave cavity")` | 0–3 |

The A pool is split by the model: optics → A, computing → tagged and held for Saturday. B candidates also in the A pool are removed so a paper appears once. Weekly adds one S2 bulk search: `"superconducting qubit" | transmon | fluxonium`, last 14 days, Physics, papers without an arXiv ID.

## Interest statements (drafts; edit in `interests/`)

**A. Superconducting artificial atoms — relevant.** Quantum optics with superconducting circuits: single- and few-photon microwave sources; photon correlation measurements (g2, cross-correlation, antibunching); temporal/spectral shaping of itinerant microwave photons; quantum state transfer between qubits, cavities or nodes; quantum information protocols on a few qubits where the physics, not the benchmark, is the point; time-domain and time-bin entangled states; waveguide QED, giant atoms, dressed states, scattering off one or a few artificial atoms. Not relevant daily: error correction, surface codes, multi-qubit processors, gate fidelity records, fabrication-only papers, calibration tooling → tag `computing`, low daily score.

**B. Other platforms — already standard.** Score low unless there is a genuinely new twist: transmission and reflection measurements of a single emitter coupled to an open transmission line or open waveguide, including the usual extinction, Mollow triplet and power-broadening results. Score high: experiments or theory showing an effect, regime or protocol not obvious from the standard cavity/waveguide QED toolbox, on any platform (atoms, ions, quantum dots, colour centres, optomechanics, photonic circuits).

**C. Dark matter with superconducting devices.** Proposals and results using superconducting qubits, resonators, single microwave photon detectors or quantum sensing protocols to search for axions, dark photons or other dark matter candidates. Include instrumentation papers if the detector is qubit- or photon-counting-based. Exclude pure astrophysics.

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
  "items": [{ "id": "2609.01234", "section": "A", "score": 82,
              "why": "First g2 measurement of a shaped microwave photon from a fluxonium." }] }
```

- `score` 0–100 against the section statement. ≥80 read today; 50–79 worth the title; <50 matched the query, not the interest.
- `section` ∈ {A, B, C, computing}. `computing` items are held for Saturday.
- `why` ≤ 25 words, present tense, names the concrete result, never restates the title.
- Cap 120 candidates per run (newest kept, overflow noted in status). ~60 abstracts ≈ 15k input tokens.
- Render: top 10 per section with why-line; the rest titles-only. Nothing dropped.

## The page

Static, Moscow dates, no JS required (details/summary for collapsed lists).
- **Banner** only when status has an error or the newest digest is >1 working day old; carries the failing step, error text, and a link to the run log.
- **Today**: sections A, B, C — title → abstract page, first three authors, date, why-line, S2 citation count and venue when present; collapsed "also matched" list per section.
- **This week** (Saturdays): the weekly ten with citation counts.
- **Previous days**: last 14, collapsed, with counts.
- **Archive** links at the foot.

## Routines

Both use the Default environment, tools Bash/Read/Write/Edit/Glob/Grep only. The prompt lives in `ROUTINE.md`; the routine message is just "read ROUTINE.md and follow it for mode daily|weekly".

| Routine | Cron (UTC) | Model | Steps |
|---|---|---|---|
| Daily digest | `0 6 * * 1-5` | Sonnet 5 | 1 `uv run scripts/fetch.py --mode daily` · 2 rank → `out/ranking.json` · 3 `uv run scripts/render.py` · 4 commit digests/state/docs, push main · 5 on any failure still run render with `--error "text"` and commit |
| Weekly computing | `0 7 * * 6` | Opus 5 | same with `--mode weekly` (week's computing-tagged digests + S2 venue search) |

**Semantic Scholar key**: stored as an API credential on the Default environment — host `api.semanticscholar.org`, header `x-api-key`, no prefix. The proxy attaches it after the request leaves the VM; nothing in the repo or session sees it. Without it fetch.py notes "unauthenticated" in status and continues.

## Rate limits and failure handling

- **S2**: single client in `s2.py`, ≤1 rps, retries 429/5xx with exponential backoff from 2 s, max 5 attempts, caches every answer in `state/s2_cache.json`. Daily traffic: one batch call ≤100 IDs. Weekly: plus 1–2 bulk searches.
- **arXiv**: 3 s between requests, <10 requests per run, 503 retried ×3 after 10 s.
- **Missed run**: absorbed by the 7-day window; no replay needed.
- **Partial failure**: S2 down → digest without enrichment + banner. One arXiv section down → other sections still render.
- **Bad model output**: render.py validates ranking.json; on violation renders the raw candidate list unranked + banner.

## Implementation plan

| Phase | Owner | Steps | Done when |
|---|---|---|---|
| 0 · Access | you | Run `/web-setup` in a Claude Code terminal (syncs the Focix gh token to claude.ai). At claude.ai/code edit the Default environment: network Custom, add `export.arxiv.org`, keep "include default list". When the S2 key arrives add it as an API credential (host `api.semanticscholar.org`, header `x-api-key`, no prefix). | A cloud session from the repo can curl `export.arxiv.org` and call S2 with the key attached. |
| 0 · Local | claude | Register arxiv + s2 MCP servers in Claude Code at user scope. Create the public GitHub repo from this folder and push. | `claude mcp list` shows both connected; repo exists. |
| 1 · Fetch | claude | s2.py, fetch.py, queries.toml, settings.toml. Backfill 14 days locally, measure volumes, tune phrases. | Per-section counts for two weeks within expected ranges; seen.json populated. |
| 2 · Ranking | claude | Interest statements + rank_daily.md. Two manual ranking runs on real candidates in a local session. | You approve both top-10 lists, or edit statements and rerun once. |
| 3 · Page | claude | render.py + style.css; generate docs from backfill; enable Pages on `docs/`. | Page loads on phone and laptop, both themes, 14 days visible. |
| 4 · Routines | claude | ROUTINE.md; create daily routine, run once by hand, read log, confirm commit + page update; then weekly. | One successful manual run each, commit on main by the routine. |
| 5 · Observe | you | Read five weekdays of digests, note mis-rankings, edit statements once. | One week of digests, one statement edit, v2 decision. |

First run shows the whole 7-day window (long). Backfill in phase 1 marks older papers seen, so from day two only new submissions appear.

## Risks and later work

- **Cloud egress** depends on the allowlist entry (arXiv) and the API credential (S2); verified in phase 0. Fallback: launchd + `claude -p` locally, page as a Claude artifact.
- **Git push from the routine** depends on `/web-setup` and an unprotected main with only Focix commits. A failed push leaves the run log as the only record; the next run redoes the work since seen.json was never committed.
- **Ranking variance** day to day; rubric + fixed statements reduce it. v2: pin a paper's score at first display.
- **Public reading list**; switch to private repo + rendered Markdown if uncomfortable.
- **Query drift**; titles-only list exposes misses inside the pool. Revisit queries.toml quarterly.

v2 candidates: feedback buttons feeding the next ranking; author watchlist section; Zotero export via zotero MCP in a local session; Telegram/email push of the top three.
