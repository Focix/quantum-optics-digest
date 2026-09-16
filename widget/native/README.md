# Native widget (WidgetKit)

A real macOS widget: right-click the desktop → Edit Widgets → **Quantum Optics Digest**, in small,
medium and large. It sits in the desktop widget layer like Calendar or Weather — it slides aside
for windows, follows the system theme, and dims when you focus an app.

It reads the published `data/latest.json`, so it needs no checkout at
runtime, and it keeps the last successful response so an offline Mac still shows yesterday's papers
(marked orange) instead of an empty card.

## Build and install

```sh
./build.sh                # build, ad-hoc sign, install to /Applications
./build.sh --no-install   # leave it in build/
open "/Applications/Quantum Optics Digest.app"   # once, so the widget reaches the gallery
```

No Xcode needed — WidgetKit and SwiftUI both ship in the Command Line Tools SDK, and an ad-hoc
signature (`codesign -s -`) is enough for a widget you run yourself. The one non-obvious part is
the link step: a widget extension's entry point must be `_NSExtensionMain` (`-Xlinker -e`), as
Xcode links them, because that handshake tells ExtensionFoundation which extension point the
process serves. Entering Swift's `@main` instead aborts at launch with "Unrecognized extension
type"; chronod then logs "Connection to extension process was invalidated", its descriptor query
fails, and the widget silently never appears in the gallery. Two consequences of having no signing identity: the widget cannot use an App Group (hence the fetch-and-cache in each process
rather than a shared container), and `@State` is unavailable because its macro plugin lives inside
Xcode — `DigestModel` is an `ObservableObject` for that reason alone.

The app window is deliberately minimal. macOS only lists a widget whose host app is installed and
has been launched once, so the app exists to be that host; it shows the same digest, opens the
site, and force-refreshes the widget timeline.

## Layout per size

| Size | Shows |
| --- | --- |
| Small | Date, top 2 papers per section, no headings |
| Medium | Section headings, top 3 per section |
| Large | Section headings, top 5 per section, with why-lines |

Watchlist papers appear on top of those counts with a ★, whatever they scored, as on the site.
Clicking a paper opens its arXiv page; clicking elsewhere opens the digest site. `computing`
papers are left out, since they are held for the Saturday weekly.

Timeline refresh is hourly, or every 15 minutes while a fetch is failing.

## Sources

```
Sources/Shared/Digest.swift     model, section list, fetch + cache
Sources/Shared/PaperRow.swift   score / kind badge / ★ / title / why, shared by app and widget
Sources/Widget/DigestWidget.swift  TimelineProvider, the three layouts, WidgetBundle
Sources/App/DigestApp.swift     host app window
Resources/                      Info.plists and entitlements for both bundles
```
