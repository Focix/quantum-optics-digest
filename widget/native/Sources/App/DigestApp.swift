import Combine
import SwiftUI
import WidgetKit

/// The Command Line Tools SDK has no SwiftUIMacros plugin, so `@State` is unavailable here;
/// an ObservableObject does the same job with plain property wrappers.
final class DigestModel: ObservableObject {
    @Published var digest: Digest?
    @Published var cached = false
    @Published var loading = true

    @MainActor func load() async {
        loading = true
        let result = await DigestLoader.load()
        digest = result.digest
        cached = result.cached
        loading = false
    }
}

/// The container app. macOS only offers a widget in the gallery if its host app is installed,
/// so this window is deliberately small: today's digest, and the two buttons worth having.
struct ContentView: View {
    @StateObject private var model = DigestModel()

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text("Quantum Optics Digest").font(.headline)
                Spacer()
                if let digest = model.digest {
                    Text(digest.run + (model.cached ? " (cached)" : ""))
                        .font(.subheadline)
                        .foregroundStyle(digest.isStale || model.cached ? .orange : .secondary)
                }
            }
            if model.loading {
                ProgressView().frame(maxWidth: .infinity)
            } else if let digest = model.digest {
                ScrollView {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(Section.all, id: \.key) { section in
                            let papers = digest.papers(section.key, limit: 5)
                            if !papers.isEmpty {
                                Text(section.title).font(.caption).fontWeight(.semibold)
                                    .foregroundStyle(Color.accentColor)
                                ForEach(papers) { Row(paper: $0, showWhy: true) }
                            }
                        }
                    }
                }
            } else {
                Text("Digest unavailable — offline, or the site has not published yet.")
                    .foregroundStyle(.secondary)
            }
            Divider()
            HStack {
                Button("Open site") { NSWorkspace.shared.open(DigestLoader.site) }
                Spacer()
                Button("Refresh widget") {
                    WidgetCenter.shared.reloadAllTimelines()
                    Task { await model.load() }
                }
            }
        }
        .padding(14)
        .frame(width: 380, height: 460)
        .task { await model.load() }
    }
}

@main
struct DigestApp: App {
    var body: some Scene {
        Window("Quantum Optics Digest", id: "main") {
            ContentView()
        }
        .windowResizability(.contentSize)
    }
}
