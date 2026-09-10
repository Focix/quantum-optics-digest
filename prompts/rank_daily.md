# Daily ranking

You are ranking new arXiv papers for a physicist who works on superconducting artificial atoms and microwave quantum optics.

Inputs:
- `out/candidates.json`: the candidates. Each has `id`, `title`, `authors`, `abstract`, `categories`, `submitted`, `pool` (A, B or C), `tags`, and optional `cite` (OpenAlex citation count and venue).
- `interests/a_superconducting.md`, `interests/b_other_platforms.md`, `interests/c_dark_matter.md`: what each section is for.

Output: write `out/ranking.json` exactly in this shape:

```json
{ "run": "YYYY-MM-DD", "mode": "daily",
  "items": [ { "id": "2609.01234", "section": "A", "score": 82,
               "why": "First g2 measurement of a shaped microwave photon from a fluxonium." } ] }
```

Rules:
1. Every candidate appears exactly once in `items`. Never drop or invent an id.
2. `section` is one of `A`, `B`, `C`, `computing`.
   - Pool A papers go to `A` if they are quantum optics with superconducting circuits per the A statement, otherwise to `computing` (error correction, processors, gates, fabrication, materials, calibration). When unsure, ask "is the light the point?"; if yes, `A`.
   - Pool B papers stay in `B`; pool C papers stay in `C`. Move a paper across pools only if it clearly belongs elsewhere.
3. `score` is an integer 0–100 against the section statement: ≥80 read today, 50–79 worth the title, <50 matched the query but not the interest. Use the whole range; a typical day has zero to three papers at 80 or above.
4. `why` is at most 25 words, present tense, names the concrete result or claim, never restates the title. Write it for the reader, not for the authors.
5. Judge from the abstract only. Do not fetch anything.
6. Rank within a section by score; ties broken by your judgement of novelty.
