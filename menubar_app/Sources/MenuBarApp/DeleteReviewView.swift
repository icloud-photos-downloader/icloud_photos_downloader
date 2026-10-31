import MenuBarCore
import SwiftUI

enum DeleteMode {
    case dryRun
    case iCloud
    case iCloudAndDisk
}

@MainActor
final class ReviewModel: ObservableObject {
    @Published var scanning = false
    @Published var result: ScanResult?
    @Published var error: String?
    @Published var output = ""
    @Published var working = false
    @Published var confirmMode: DeleteMode?

    func scan() {
        scanning = true
        error = nil
        let options = Prefs.scanOptions
        Task {
            do {
                let r = try await Task.detached { try scanTrashCandidates(options) }.value
                result = r
            } catch {
                result = nil
                self.error = error.localizedDescription
            }
            scanning = false
        }
    }

    /// Dry run, delete from iCloud, or delete from iCloud and move the downloaded files to the Trash.
    func run(_ mode: DeleteMode, app: AppModel) {
        guard let items = result?.candidates, !items.isEmpty else { return }
        working = true
        output = ""
        Task {
            let (ok, text) = await Deletion.deleteFromICloud(items, dryRun: mode == .dryRun)
            var report = text
            if ok, mode != .dryRun { app.recordEvents(.deletedICloud, items) }
            if ok, mode == .iCloudAndDisk {
                let trashed = Deletion.moveToTrash(items)
                app.recordEvents(.trashedDisk, trashed.items)
                report += "\nMoved \(trashed.moved) file(s) to the Trash."
                if !trashed.failures.isEmpty { report += "\nNot moved: " + trashed.failures.joined(separator: "; ") }
            }
            output = report
            working = false
            if ok && mode != .dryRun { scan() }
        }
    }
}

struct DeleteReviewView: View {
    @StateObject private var model = ReviewModel()
    @EnvironmentObject var app: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Photos deleted in the Photos app that are still in iCloud")
                .font(.headline)
            Text("Only photos that are in Photos “Recently Deleted” and match a file downloaded by icloudpd are listed. Nothing is deleted without your click, and iCloud keeps deleted photos in “Recently Deleted” for about 30 days.")
                .font(.callout).foregroundStyle(.secondary)

            HStack {
                Button("Scan Photos library") { model.scan() }.disabled(model.scanning || model.working)
                if model.scanning { ProgressView().controlSize(.small) }
            }

            if let error = model.error {
                Text(error).foregroundStyle(.red)
            }
            if let r = model.result {
                Text("Photos trash: \(r.trashedTotal) of \(r.assetTotal) items · downloaded files: \(r.stagedFiles) · matches: \(r.candidates.count)")
                    .font(.caption).foregroundStyle(.secondary)
                if r.candidates.isEmpty {
                    Text("Nothing to delete.")
                } else {
                    List(r.candidates) { c in
                        HStack {
                            Text(c.name).monospaced()
                            Spacer()
                            Text(Date(timeIntervalSince1970: TimeInterval(c.trashedUnix)).formatted(date: .abbreviated, time: .shortened))
                                .foregroundStyle(.secondary)
                        }
                    }
                    .frame(minHeight: 120)
                    HStack {
                        Button("Dry run") { model.run(.dryRun, app: app) }
                        Button("Delete from iCloud…", role: .destructive) { model.confirmMode = .iCloud }
                        Button("Delete from iCloud & Disk…", role: .destructive) { model.confirmMode = .iCloudAndDisk }
                        if model.working { ProgressView().controlSize(.small) }
                    }
                    .disabled(model.working)
                }
            }
            if !model.output.isEmpty {
                ScrollView { Text(model.output).font(.caption.monospaced()).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading) }
                    .frame(height: 110)
            }
        }
        .padding()
        .frame(width: 600, height: 520)
        .confirmationDialog(
            "Delete \(model.result?.candidates.count ?? 0) photo(s)?",
            isPresented: Binding(get: { model.confirmMode != nil }, set: { if !$0 { model.confirmMode = nil } }),
            titleVisibility: .visible
        ) {
            if model.confirmMode == .iCloudAndDisk {
                Button("Delete from iCloud and move files to Trash", role: .destructive) { model.run(.iCloudAndDisk, app: app) }
            } else {
                Button("Delete from iCloud", role: .destructive) { model.run(.iCloud, app: app) }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text(model.confirmMode == .iCloudAndDisk
                 ? "They disappear on all your devices and stay in iCloud “Recently Deleted” for about 30 days. The downloaded files go to the Trash on this Mac."
                 : "They disappear on all your devices and stay in iCloud “Recently Deleted” for about 30 days. The downloaded files stay on this Mac.")
        }
        .onAppear { model.scan() }
    }
}
