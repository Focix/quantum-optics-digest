import SwiftUI

/// Score, kind badge and watchlist star, the same shorthand the site uses.
struct Marks: View {
    let paper: Paper

    private var kindColor: Color {
        switch paper.kind {
        case "T": return Color(red: 0.17, green: 0.37, blue: 0.62)
        case "E": return Color(red: 0.18, green: 0.49, blue: 0.31)
        case "TE": return Color(red: 0.48, green: 0.29, blue: 0.62)
        default: return .secondary
        }
    }

    var body: some View {
        HStack(spacing: 4) {
            Text(paper.score.map(String.init) ?? "")
                .font(.caption).monospacedDigit()
                .foregroundStyle((paper.score ?? 0) >= 80 ? Color.accentColor : .secondary)
                .fontWeight((paper.score ?? 0) >= 80 ? .semibold : .regular)
                .frame(width: 20, alignment: .trailing)
            if let kind = paper.kind, !kind.isEmpty {
                Text(kind)
                    .font(.system(size: 8, weight: .bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 3).padding(.vertical, 1)
                    .background(kindColor, in: RoundedRectangle(cornerRadius: 3))
            }
            if !paper.watched.isEmpty {
                Image(systemName: "star.fill").font(.system(size: 7)).foregroundStyle(Color.accentColor)
            }
        }
    }
}

struct Row: View {
    let paper: Paper
    let showWhy: Bool

    var body: some View {
        Link(destination: paper.link) {
            VStack(alignment: .leading, spacing: 1) {
                HStack(alignment: .firstTextBaseline, spacing: 5) {
                    Marks(paper: paper)
                    Text(paper.title)
                        .font(.caption)
                        .fontWeight((paper.score ?? 0) >= 80 ? .semibold : .regular)
                        .lineLimit(showWhy ? 2 : 1)
                        .multilineTextAlignment(.leading)
                }
                if showWhy, let why = paper.why, !why.isEmpty {
                    Text(why)
                        .font(.system(size: 10))
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                        .padding(.leading, 25)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .buttonStyle(.plain)
    }
}
