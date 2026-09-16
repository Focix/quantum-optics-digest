import SwiftUI
import WidgetKit

struct Entry: TimelineEntry {
    let date: Date
    let digest: Digest?
    let cached: Bool
}

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> Entry {
        Entry(date: Date(), digest: nil, cached: false)
    }

    func getSnapshot(in context: Context, completion: @escaping (Entry) -> Void) {
        Task {
            let (digest, cached) = await DigestLoader.load()
            completion(Entry(date: Date(), digest: digest, cached: cached))
        }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> Void) {
        Task {
            let (digest, cached) = await DigestLoader.load()
            let entry = Entry(date: Date(), digest: digest, cached: cached)
            // The routine publishes once a morning; a failed fetch is worth retrying sooner.
            let next = Date().addingTimeInterval(digest == nil || cached ? 15 * 60 : 60 * 60)
            completion(Timeline(entries: [entry], policy: .after(next)))
        }
    }
}

struct Header: View {
    let digest: Digest?
    let cached: Bool

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text("Quantum Optics").font(.caption).fontWeight(.semibold)
            Spacer()
            if let digest {
                Text(label(digest))
                    .font(.system(size: 10))
                    .foregroundStyle(digest.isStale || cached ? Color.orange : .secondary)
            }
        }
    }

    private func label(_ digest: Digest) -> String {
        guard let date = digest.runDate else { return digest.run }
        return date.formatted(.dateTime.weekday(.abbreviated).day().month(.abbreviated))
    }
}

struct DigestView: View {
    @Environment(\.widgetFamily) private var family
    let entry: Entry

    /// How much fits: (papers per section, section headings, why-lines).
    private var layout: (limit: Int, headings: Bool, why: Bool) {
        switch family {
        case .systemSmall: return (2, false, false)
        case .systemLarge: return (5, true, true)
        default: return (3, true, false)
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Header(digest: entry.digest, cached: entry.cached)
            if let digest = entry.digest {
                let sections = Section.all.map { ($0.title, digest.papers($0.key, limit: layout.limit)) }
                    .filter { !$0.1.isEmpty }
                if sections.isEmpty {
                    Text("Nothing scored above the threshold.")
                        .font(.caption).foregroundStyle(.secondary)
                } else {
                    ForEach(sections, id: \.0) { title, papers in
                        if layout.headings {
                            Text(title)
                                .font(.system(size: 9, weight: .semibold))
                                .textCase(.uppercase)
                                .foregroundStyle(Color.accentColor)
                                .padding(.top, 2)
                        }
                        ForEach(papers) { paper in
                            Row(paper: paper, showWhy: layout.why)
                        }
                    }
                }
            } else {
                Text("Digest unavailable — offline, or the site has not published yet.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
        }
        .widgetURL(DigestLoader.site)
        .containerBackground(.fill.tertiary, for: .widget)
    }
}

struct DigestWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "QuantumOpticsDigest", provider: Provider()) { entry in
            DigestView(entry: entry)
        }
        .configurationDisplayName("Quantum Optics Digest")
        .description("Today's top arXiv papers from your digest.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}

@main
struct DigestWidgetBundle: WidgetBundle {
    var body: some Widget {
        DigestWidget()
    }
}
