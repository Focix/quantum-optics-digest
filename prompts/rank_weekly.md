# Weekly ranking

You are ranking the week's new papers for a physicist who works on superconducting artificial atoms and microwave quantum optics, who also follows superconducting quantum computing and the foundations of quantum mechanics. The digest comes out once a week, on Monday morning, so each section should read as "what this week brought".

Inputs:
- `out/candidates.json`: the candidates. Each has `id`, `title`, `authors`, `abstract`, `categories`, `submitted`, `pool`, `tags`, and optional `cite` (OpenAlex citation count and venue). `pool` is `A`, `B` or `C` for arXiv papers (the arXiv query they matched), or `journal` for journal articles found through OpenAlex with no arXiv version (tag `source:openalex`, `url` instead of an arXiv id).
- `interests/a_superconducting.md`, `interests/b_other_platforms.md`, `interests/c_foundations.md`, `interests/computing.md`: what each section is for.
- `state/feedback.json` (may be empty): papers the reader marked 👍 (`up`, relevant, more like this) or 👎 (`down`, not relevant) with the `score` they had at the time. Read the last 50 entries. Use them as calibration: an `up` on a low score means that kind of paper is under-scored, a `down` on a high score means it is over-scored. Do not restate them; let them shift how you score similar papers this week.

Output: write `out/ranking.json` exactly in this shape:

```json
{ "run": "YYYY-MM-DD", "mode": "weekly",
  "items": [ { "id": "2609.01234", "section": "A", "score": 82, "kind": "E",
               "why": "First g2 measurement of a shaped microwave photon from a fluxonium.",
               "eli5": { "plain": "They made a single microwave photon with a chosen pulse shape and proved it really was one photon.",
                         "how": "A fluxonium qubit emits into a shaped drive, and two detectors count coincidences; a dip at zero delay means the photons arrive one at a time.",
                         "matters": "Shaped single photons are what you hand to a remote node, so this is a piece of a microwave quantum network.",
                         "caveat": "The dip is measured on a small sample at one shaping setting; the photon rate and loss budget are not yet network-grade." } } ] }
```

Rules:
1. Every candidate appears exactly once in `items`. Never drop or invent an id.
2. `section` is one of `A`, `B`, `C`, `computing`.
   - Pool A papers go to `A` if they are quantum optics with superconducting circuits per the A statement, otherwise to `computing` (error correction, processors, gates, fabrication, materials, calibration). When unsure, ask "is the light the point?"; if yes, `A`.
   - Pool B papers stay in `B`, pool C papers in `C`. Move a paper across sections only if it clearly belongs elsewhere: a single-photon Bell test whose point is the foundations belongs in `C`, a foundations-flavoured paper whose point is a new optics effect belongs in `B`.
   - `journal` papers go to `computing`, or to `A` if the light is the point.
3. `score` is an integer 0–100 against that section's statement: ≥80 read this week, 50–79 worth the title, <50 matched the query but not the interest. Use the whole range. In `A`, `B` and `C` a typical week has zero to five papers at 80 or above. In `computing` the top ten should be the ten a colleague would mention at Monday coffee; give at most ten computing papers 80 or more, and weight citation counts when present.
4. `why` is at most 25 words, present tense, names the concrete result or claim, never restates the title. Write it for the reader, not for the authors.
5. `kind` is `E` for experimental papers (measured data from a device), `T` for theory, proposals, numerics, conceptual arguments and reviews, `TE` when the paper reports both an experiment and substantial new theory or modelling of its own. Judge from the abstract.
6. `eli5` is a plain-English explanation for a physicist outside the paper's sub-field, in four fields, each one or two sentences: `plain` (what they did, no jargon), `how` (the mechanism, method or argument), `matters` (why it matters to someone working on superconducting circuits and microwave quantum optics; for `C`, what it changes about how we should read quantum mechanics), `caveat` (the honest limitation, not a disclaimer). Write it for the ten highest-scoring papers of each section plus every `watch:` paper, and omit the field entirely on everything else: those are the papers the page shows in full. Never restate the title, and never just re-word `why`: `why` is the one-line reason to read it, `eli5` is the explanation. Define or drop jargon; one good analogy beats three weak ones; keep what the paper shows separate from what it speculates. The house style is in `.claude/skills/eli5/SKILL.md`.
7. Judge from the abstract only. Do not fetch anything.
8. Rank within a section by score; ties broken by your judgement of novelty.
9. A `watch:<name>` tag means an author is on the reader's watchlist. The page always shows such papers with your `why`, so write it with care, but score them honestly: the watchlist does not raise the score.
