---
name: eli5
description: Explain a paper or technical idea in plain English with minimal jargon, concrete analogies, and clear takeaways. Use when the user says "ELI5 this", asks for a simple explanation of a paper or result, wants jargon removed, or asks what something technically dense actually means. Also the house style for the `eli5` field the ranking model writes into out/ranking.json.
---

# ELI5

Adapted from the `eli5` skill in [Companion-Inc/feynman](https://github.com/Companion-Inc/feynman) (MIT).
Feynman's own `feynman alpha ...` lookups are replaced here by this repo's sources.

When the user names a specific paper, arXiv id, DOI or URL, work from the paper itself: the
abstract already in `out/candidates.json` or `digests/YYYY-MM-DD.json`, `src/digest/openalex.py`
for metadata, or the arXiv abstract page. If the user gives only a topic, pick 1-3 representative
papers and anchor the explanation on the clearest one.

Structure a full explanation with:
- `One-Sentence Summary`
- `Big Idea`
- `How It Works`
- `Why It Matters`
- `What To Be Skeptical Of`
- `If You Remember 3 Things`

Guidelines:
- Short sentences, concrete words.
- Define jargon immediately or drop it.
- One good analogy beats three weak ones.
- Separate what the paper shows from what it speculates.
- Keep it inline unless the user asks for an artifact.

## The digest's `eli5` field

The page's Explain button shows a four-field version of the same thing, written by the ranking
model into `out/ranking.json` and carried through to `digests/` and `docs/`:

| field | what goes in it |
| --- | --- |
| `plain` | the One-Sentence Summary: what the paper did, no jargon |
| `how` | How It Works, one or two sentences, the mechanism or method |
| `matters` | Why It Matters to someone working on superconducting circuits and microwave quantum optics |
| `caveat` | What To Be Skeptical Of: the honest limitation, not a disclaimer |

The reader is a physicist, so "plain English" means no sub-field jargon, not no physics. Do not
restate the title, and do not repeat `why` — `why` is the one-line reason to read it, `eli5` is
the explanation for someone outside the sub-field. `prompts/rank_daily.md` holds the binding rules.
