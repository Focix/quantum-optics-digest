import Foundation

/// One paper as published in docs/data/latest.json.
struct Paper: Codable, Identifiable, Hashable {
    let id: String
    let title: String
    let section: String
    let score: Int?
    let kind: String?
    let why: String?
    let url: String?
    let tags: [String]?

    var link: URL {
        URL(string: url ?? "") ?? URL(string: "https://arxiv.org/abs/\(id)")!
    }

    /// Names from `watch:<name>` tags; these papers show whatever they scored.
    var watched: [String] {
        (tags ?? []).filter { $0.hasPrefix("watch:") }.map { String($0.dropFirst(6)) }
    }
}

struct Digest: Codable {
    let run: String
    let mode: String
    let items: [String: Paper]

    var runDate: Date? {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.timeZone = TimeZone(identifier: "UTC")
        return f.date(from: run)
    }

    /// A run older than two days means the routine did not publish; the widget says so
    /// rather than passing day-old papers off as today's.
    var isStale: Bool {
        guard let d = runDate else { return false }
        return Date().timeIntervalSince(d) > 2.5 * 86_400
    }

    /// Papers of one section, best first, plus every watchlist paper below the cut.
    func papers(_ section: String, limit: Int) -> [Paper] {
        let all = items.values
            .filter { $0.section == section }
            .sorted { a, b in
                let (x, y) = (a.score ?? 0, b.score ?? 0)
                return x == y ? a.id < b.id : x > y
            }
        return Array(all.prefix(limit)) + all.dropFirst(limit).filter { !$0.watched.isEmpty }
    }
}

enum Section {
    /// `computing` is deliberately absent: those papers are held for the Saturday weekly,
    /// exactly as on the site's daily pages.
    static let all: [(key: String, title: String)] = [
        ("A", "Superconducting atoms"),
        ("B", "Other platforms"),
    ]
}

enum DigestLoader {
    static let site = URL(string: "https://focix.github.io/quantum-optics-digest/")!
    static let data = URL(string: "https://focix.github.io/quantum-optics-digest/data/latest.json")!

    private static var cacheFile: URL? {
        let dir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first
        return dir?.appendingPathComponent("latest.json")
    }

    /// The published digest, or the last one we saw when the network is unavailable.
    static func load() async -> (digest: Digest?, cached: Bool) {
        var request = URLRequest(url: data)
        request.timeoutInterval = 20
        request.cachePolicy = .reloadIgnoringLocalCacheData
        if let (bytes, response) = try? await URLSession.shared.data(for: request),
           (response as? HTTPURLResponse)?.statusCode == 200,
           let digest = try? JSONDecoder().decode(Digest.self, from: bytes) {
            if let file = cacheFile { try? bytes.write(to: file) }
            return (digest, false)
        }
        if let file = cacheFile, let bytes = try? Data(contentsOf: file),
           let digest = try? JSONDecoder().decode(Digest.self, from: bytes) {
            return (digest, true)
        }
        return (nil, false)
    }
}
