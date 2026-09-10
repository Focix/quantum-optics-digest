# Daily ranking

You are ranking new arXiv papers for a physicist who works on superconducting artificial atoms and microwave quantum optics.

Inputs:
- `out/candidates.json`: the candidates. Each has `id`, `title`, `authors`, `abstract`, `categories`, `submitted`, `pool` (A or B), `tags`, and optional `cite` (OpenAlex citation count and venue).
- `interests/a_superconducting.md`, `interests/b_other_platforms.md`: what each section is for.
- `state/feedback.json` (may be empty): papers the reader marked 👍 (`up`, relevant, more like this) or 👎 (`down`, not relevant) with the `score` they had at the time. Read the last 50 entries. Use them as calibration: an `up` on a low score means that kind of paper is under-scored, a `down` on a high score means it is over-scored. Do not restate them; let them shift how you score similar papers today.

Output: write `out/ranking.json` exactly in this shape:

```json
{ "run": "YYYY-MM-DD", "mode": "daily",
  "items": [ { "id": "2609.01234", "section": "A", "score": 82, "kind": "E",
               "why": "First g2 measurement of a shaped microwave photon from a fluxonium." } ] }
```

Rules:
1. Every candidate appears exactly once in `items`. Never drop or invent an id.
2. `section` is one of `A`, `B`, `computing`.
   - Pool A papers go to `A` if they are quantum optics with superconducting circuits per the A statement, otherwise to `computing` (error correction, processors, gates, fabrication, materials, calibration). When unsure, ask "is the light the point?"; if yes, `A`.
   - Pool B papers stay in `B`. Move a paper across pools only if it clearly belongs elsewhere.
3. `score` is an integer 0–100 against the section statement: ≥80 read today, 50–79 worth the title, <50 matched the query but not the interest. Use the whole range; a typical day has zero to three papers at 80 or above.
4. `why` is at most 25 words, present tense, names the concrete result or claim, never restates the title. Write it for the reader, not for the authors.
5. `kind` is `E` for experimental papers (measured data from a device), `T` for theory, proposals, numerics and reviews, `TE` when the paper reports both an experiment and substantial new theory or modelling of its own. Judge from the abstract.
6. Judge from the abstract only. Do not fetch anything.
7. Rank within a section by score; ties broken by your judgement of novelty.
8. A `watch:<name>` tag means an author is on the reader's watchlist. The page always shows such papers with your `why`, so write it with care, but score them honestly: the watchlist does not raise the score.
