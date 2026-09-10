# Weekly ranking

You are picking the week's superconducting quantum computing papers for a physicist who works on superconducting qubits but reads computing results only once a week.

Inputs:
- `out/candidates.json`: computing-tagged papers from this week's daily digests, plus (when enabled) journal papers found through OpenAlex (tag `source:openalex`, `url` instead of an arXiv id). Fields as in the daily contract; `pool` is `weekly`.
- `interests/weekly_computing.md`: what makes a paper worth hearing about.

Output: write `out/ranking.json` in this shape:

```json
{ "run": "YYYY-MM-DD", "mode": "weekly",
  "items": [ { "id": "2609.01234", "section": "weekly", "score": 91,
               "why": "Logical qubit below threshold with a distance-7 surface code on 101 qubits." } ] }
```

Rules:
1. Every candidate appears exactly once; `section` is always `weekly`.
2. `score` 0–100. The top ten should be the ten a colleague would mention at Monday coffee. Give at most ten papers a score of 80 or more.
3. `why` at most 25 words, present tense, concrete result, never the title again.
4. Prefer results over surveys, experiments over proposals; weight citation counts when present.
5. Judge from the abstracts. Do not fetch anything.
