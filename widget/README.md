# Desktop widget

An [Übersicht](https://tracesof.net/uebersicht/) widget that draws today's digest onto the desktop
wallpaper: top papers per section with score, kind badge and why-line. Clicking a paper opens its
arXiv page, clicking the header opens the site.

It reads the published `data/latest.json` over the network, so it needs no checkout, no Python and
no local run — it works on any Mac that can reach the site.

## Install

```sh
brew install --cask ubersicht
open -a Übersicht                     # menu-bar icon appears; allow it to draw on the desktop
ln -s "$PWD/widget/quantum-optics-digest.widget" \
      ~/Library/Application\ Support/Übersicht/widgets/
```

Übersicht picks the widget up immediately and reloads it whenever `index.jsx` changes.

## Tweaks

All at the top of `index.jsx`:

- `PER_SECTION` — papers per section (watchlist papers are always shown on top of this).
- `SECTIONS` — which sections to draw. `computing` is deliberately absent: those papers are held
  for the Saturday weekly, exactly as on the daily pages.
- `refreshFreq` — how often it refetches (default 30 min; the routine publishes once a morning).
- `className` — position (`top`/`right`), width and colours. The palette follows the site's dark theme.

## Notes

- The date turns orange when the newest run is more than two days old, which is what a failed or
  skipped routine looks like from outside.
- Network failure, a 404 and malformed JSON each draw a one-line message instead of a blank card.
- `data/latest.json` is written by `render_site` and always points at the newest *daily* digest, so
  the widget never has to guess a run date across weekends and failed runs.
