import AppKit
import SwiftUI
import UniformTypeIdentifiers

/// "Sync Activity": the files icloudpd downloaded recently, newest first. Click a file to open it.
struct ActivityView: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 8) {
                Button { model.showActivity = false } label: { Image(systemName: "chevron.left") }
                    .buttonStyle(.plain)
                Text("Sync Activity").font(.headline)
                Spacer()
            }
            .padding(12)
            Divider()

            HStack(spacing: 10) {
                SyncBadge(syncing: model.isSyncing)
                VStack(alignment: .leading, spacing: 2) {
                    Text(model.activitySummary).font(.subheadline.weight(.semibold))
                    if case .syncing(let percent, _, let total) = model.state, total > 0 {
                        ProgressView(value: Double(percent), total: 100)
                    } else {
                        Text(model.statusLine).font(.caption).foregroundStyle(.secondary)
                    }
                }
                Spacer()
            }
            .padding(12)
            Divider()

            if model.activity.isEmpty {
                Text("Files appear here as they are downloaded.")
                    .foregroundStyle(.secondary).padding(16)
            } else {
                ScrollView {
                    LazyVStack(spacing: 0) {
                        ForEach(model.activity) { file in
                            ActivityRow(file: file, imported: model.importedPaths.contains(file.path))
                            Divider()
                        }
                    }
                }
                .frame(maxHeight: 380)
            }
        }
    }

}

struct SyncBadge: View {
    let syncing: Bool
    var size: CGFloat = 22

    var body: some View {
        ZStack {
            Circle().fill(Color.gray.opacity(0.18))
            Circle().fill(syncing ? Color.blue : Color.green).padding(size * 0.18)
            Image(systemName: syncing ? "arrow.triangle.2.circlepath" : "checkmark")
                .font(.system(size: size * 0.36, weight: .bold))
                .foregroundStyle(.white)
        }
        .frame(width: size, height: size)
    }
}

/// Small round badge on the icon of a file: a red trash can for deletions, a blue arrow for a copy saved from Photos.
private struct EventBadge: View {
    let symbol: String
    let color: Color

    var body: some View {
        Image(systemName: symbol)
            .font(.system(size: 7, weight: .bold))
            .foregroundStyle(.white)
            .frame(width: 14, height: 14)
            .background(Circle().fill(color))
            .offset(x: 4, y: 4)
    }
}

private struct ActivityRow: View {
    let file: ActivityFile
    let imported: Bool

    var body: some View {
        let exists = FileManager.default.fileExists(atPath: file.path)
        HStack(spacing: 10) {
            Image(nsImage: icon(exists: exists))
                .resizable().frame(width: 32, height: 32)
                .opacity(exists ? 1 : 0.4)
                .overlay(alignment: .bottomTrailing) {
                    switch file.event {
                    case .downloaded: EmptyView()
                    case .savedFromPhotos: EventBadge(symbol: "arrow.down", color: .blue)
                    default: EventBadge(symbol: "trash.fill", color: .red)
                    }
                }
            VStack(alignment: .leading, spacing: 2) {
                Text(file.name).lineLimit(1).truncationMode(.middle)
                Text(subtitle(exists: exists)).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Menu {
                Button("Open") { open() }.disabled(!exists)
                Button("Show in Finder") { reveal() }.disabled(!exists)
                Button("Copy path") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(file.path, forType: .string)
                }
            } label: { Image(systemName: "ellipsis") }
                .menuStyle(.button).buttonStyle(.plain).menuIndicator(.hidden).fixedSize()
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .contentShape(Rectangle())
        .onTapGesture { if exists { open() } }
    }

    /// A file that no longer exists has no icon of its own; use the one of its type.
    private func icon(exists: Bool) -> NSImage {
        if exists || file.event == .downloaded { return NSWorkspace.shared.icon(forFile: file.path) }
        let type = UTType(filenameExtension: URL(fileURLWithPath: file.path).pathExtension) ?? .data
        return NSWorkspace.shared.icon(for: type)
    }

    private func subtitle(exists: Bool) -> String {
        let time = Date(timeIntervalSince1970: file.time).formatted(date: .abbreviated, time: .shortened)
        switch file.event {
        case .deletedICloud: return "Deleted from iCloud · \(time)"
        case .deletedPhotos: return "Deleted from Photos · \(time)"
        case .trashedDisk: return "Moved to Trash · \(time)"
        case .savedFromPhotos: return "Saved from Photos · \(time)"
        case .downloaded: break
        }
        guard exists else { return "\(time) · file not found" }
        let marker = imported ? " · in Photos" : ""
        guard let size = file.size else { return time + marker }
        return "\(time) · \(ByteCountFormatter.string(fromByteCount: size, countStyle: .file))" + marker
    }

    private func open() { NSWorkspace.shared.open(URL(fileURLWithPath: file.path)) }
    private func reveal() { NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: file.path)]) }
}
