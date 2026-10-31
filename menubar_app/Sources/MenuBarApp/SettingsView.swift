import AppKit
import ServiceManagement
import SwiftUI

// NOTE: `@State` is a macro that needs Xcode's SwiftUIMacros plugin, which Command Line Tools lack.
// Local UI state therefore lives in small ObservableObjects.

enum SettingsCategory: String, CaseIterable, Identifiable {
    case general = "General"
    case download = "Download"
    case files = "Files & folders"
    case photos = "Apple Photos"
    case deletions = "iCloud deletions"
    case notifications = "Notifications"
    case advanced = "Advanced"

    var id: String { rawValue }
    var icon: String {
        switch self {
        case .general: return "gearshape"
        case .download: return "icloud.and.arrow.down"
        case .files: return "folder"
        case .photos: return "photo.on.rectangle"
        case .deletions: return "trash"
        case .notifications: return "bell"
        case .advanced: return "wrench.and.screwdriver"
        }
    }
}

@MainActor
final class SettingsNav: ObservableObject {
    @Published var selection: SettingsCategory? = SettingsNav.initialSelection()

    private static func initialSelection() -> SettingsCategory {
        let keys: [String: SettingsCategory] = [
            "general": .general, "download": .download, "files": .files, "photos": .photos,
            "deletions": .deletions, "notifications": .notifications, "advanced": .advanced,
        ]
        let doc = DocMode.value
        guard doc.hasPrefix("settings:") else { return .general }
        return keys[String(doc.dropFirst("settings:".count))] ?? .general
    }
}

@MainActor
final class LoginItemState: ObservableObject {
    @Published var enabled = SMAppService.mainApp.status == .enabled
    @Published var error: String?
}

struct SettingsView: View {
    @StateObject private var nav = SettingsNav()

    var body: some View {
        NavigationSplitView {
            List(SettingsCategory.allCases, selection: $nav.selection) { category in
                Label(category.rawValue, systemImage: category.icon).tag(category)
            }
            .navigationSplitViewColumnWidth(min: 170, ideal: 190, max: 220)
        } detail: {
            ScrollView {
                switch nav.selection ?? .general {
                case .general: GeneralPane()
                case .download: DownloadPane()
                case .files: FilesPane()
                case .photos: PhotosPane()
                case .deletions: DeletionsPane()
                case .notifications: NotificationsPane()
                case .advanced: AdvancedPane()
                }
            }
            .navigationTitle((nav.selection ?? .general).rawValue)
        }
        .frame(minWidth: 780, minHeight: 540)
    }
}

// MARK: - Controls

/// Fixed label on the left, value chosen from a menu on the right. A stored value that is not in
/// `options` (e.g. set by an older version) is kept as an extra entry instead of showing blank.
private struct IntPicker: View {
    let title: String
    @Binding var value: Int
    let options: [(Int, String)]
    var custom: (Int) -> String = { "\($0)" }

    var body: some View {
        let all = options.contains { $0.0 == value } ? options : options + [(value, custom(value))]
        Picker(title, selection: $value) {
            ForEach(all, id: \.0) { option in Text(option.1).tag(option.0) }
        }
    }
}

private func minutes(_ seconds: Int) -> String { "\(seconds / 60) min" }

// MARK: - Panes

private struct GeneralPane: View {
    @AppStorage(Prefs.intervalSeconds) private var interval = 3600
    @AppStorage(Prefs.recent) private var recent = 20
    @AppStorage(Prefs.startWatchingAtLaunch) private var startAtLaunch = true
    @StateObject private var login = LoginItemState()

    var body: some View {
        Form {
            AccountSection()
            Section("Sync") {
                IntPicker(title: "Check iCloud every", value: $interval, options: [
                    (300, "5 minutes"), (900, "15 minutes"), (1800, "30 minutes"), (3600, "1 hour"),
                    (7200, "2 hours"), (14_400, "4 hours"), (21_600, "6 hours"), (43_200, "12 hours"),
                    (86_400, "24 hours"),
                ], custom: minutes)
                IntPicker(title: "Each sync checks the newest", value: $recent, options: [
                    (10, "10 photos"), (20, "20 photos"), (50, "50 photos"), (100, "100 photos"),
                    (200, "200 photos"), (500, "500 photos"), (1000, "1,000 photos"),
                    (0, "All photos (slow)"),
                ], custom: { "\($0) photos" })
                Text("Only photos that are not downloaded yet are fetched, so after taking pictures use “Sync now”. Pick a number at least as high as the pictures you take between syncs. “All photos” downloads the whole library.")
                    .font(.caption).foregroundStyle(.secondary)
                Toggle("Start syncing when the app opens", isOn: $startAtLaunch)
            }
            Section("App") {
                Toggle("Open at login", isOn: $login.enabled)
                    .onChange(of: login.enabled) { enabled in
                        do {
                            if enabled { try SMAppService.mainApp.register() } else { try SMAppService.mainApp.unregister() }
                            login.error = nil
                        } catch {
                            login.error = error.localizedDescription
                            login.enabled = SMAppService.mainApp.status == .enabled
                        }
                    }
                if let message = login.error { Text(message).foregroundStyle(.red).font(.caption) }
                Text("Sync changes apply after Stop and Start syncing.").font(.caption).foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
    }
}

private struct DownloadPane: View {
    @AppStorage(Prefs.size) private var size = "original"
    @AppStorage(Prefs.forceSize) private var forceSize = false
    @AppStorage(Prefs.livePhotoSize) private var livePhotoSize = "original"
    @AppStorage(Prefs.skipPhotos) private var skipPhotos = false
    @AppStorage(Prefs.skipVideos) private var skipVideos = false
    @AppStorage(Prefs.skipLivePhotos) private var skipLivePhotos = true
    @AppStorage(Prefs.albums) private var albums = ""
    @AppStorage(Prefs.library) private var library = ""
    @AppStorage(Prefs.skipCreatedBefore) private var before = ""
    @AppStorage(Prefs.skipCreatedAfter) private var after = ""

    var body: some View {
        Form {
            Section("What to download") {
                Toggle("Photos", isOn: Binding(get: { !skipPhotos }, set: { skipPhotos = !$0 }))
                Toggle("Videos", isOn: Binding(get: { !skipVideos }, set: { skipVideos = !$0 }))
                Toggle("Live Photos", isOn: Binding(get: { !skipLivePhotos }, set: { skipLivePhotos = !$0 }))
            }
            Section("Size") {
                Picker("Photo size", selection: $size) {
                    Text("Original").tag("original")
                    Text("Adjusted (edited)").tag("adjusted")
                    Text("Alternative").tag("alternative")
                    Text("Medium").tag("medium")
                    Text("Thumbnail").tag("thumb")
                }
                Toggle("Only the chosen size, never fall back to original", isOn: $forceSize)
                Picker("Live Photo video", selection: $livePhotoSize) {
                    Text("Original").tag("original")
                    Text("Medium").tag("medium")
                    Text("Thumbnail").tag("thumb")
                }
            }
            Section("Where from") {
                TextField("Albums (comma separated, empty = everything)", text: $albums)
                TextField("Library (empty = primary)", text: $library)
            }
            Section("Date range") {
                TextField("Skip photos created before (2025-01-02 or 20d)", text: $before)
                TextField("Skip photos created after (2025-01-02 or 20d)", text: $after)
            }
        }
        .formStyle(.grouped)
    }
}

private struct FilesPane: View {
    @AppStorage(Prefs.directory) private var directory = ""
    @AppStorage(Prefs.folderStructure) private var folderStructure = "{:%Y/%m/%d}"
    @AppStorage(Prefs.fileMatchPolicy) private var matchPolicy = "name-size-dedup-with-suffix"
    @AppStorage(Prefs.livePhotoMovPolicy) private var movPolicy = "suffix"
    @AppStorage(Prefs.alignRaw) private var alignRaw = "as-is"
    @AppStorage(Prefs.keepUnicode) private var keepUnicode = false
    @AppStorage(Prefs.xmpSidecar) private var xmpSidecar = false
    @AppStorage(Prefs.setExifDatetime) private var setExif = false

    var body: some View {
        Form {
            Section("Folder") {
                HStack {
                    TextField("Download folder", text: $directory)
                    Button("Choose…") { chooseFolder() }
                }
                Picker("Folder structure", selection: $folderStructure) {
                    Text("Year / month / day").tag("{:%Y/%m/%d}")
                    Text("Year / month").tag("{:%Y/%m}")
                    Text("Year").tag("{:%Y}")
                    Text("Everything in one folder").tag("none")
                }
            }
            Section("File names") {
                Picker("Identify existing files", selection: $matchPolicy) {
                    Text("Name and size (suffix for duplicates)").tag("name-size-dedup-with-suffix")
                    Text("Name plus iCloud ID").tag("name-id7")
                }
                Picker("Live Photo video name", selection: $movPolicy) {
                    Text("Add _HEVC suffix").tag("suffix")
                    Text("Same as photo (pairs in Photos)").tag("original")
                }
                Picker("RAW + JPEG", selection: $alignRaw) {
                    Text("As is").tag("as-is")
                    Text("RAW is the original").tag("original")
                    Text("RAW is the alternative").tag("alternative")
                }
                Toggle("Keep Unicode characters in file names", isOn: $keepUnicode)
            }
            Section("Metadata") {
                Toggle("Write XMP sidecar files", isOn: $xmpSidecar)
                Toggle("Write EXIF date when missing", isOn: $setExif)
            }
        }
        .formStyle(.grouped)
    }

    private func chooseFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        if panel.runModal() == .OK, let url = panel.url { directory = url.path }
    }
}

@MainActor
final class PhotosPaneState: ObservableObject {
    @Published var pendingCount: Int?
    @Published var confirming = false
}

private struct PhotosPane: View {
    @EnvironmentObject var app: AppModel
    @AppStorage(Prefs.autoImportToPhotos) private var autoImport = false
    @AppStorage(Prefs.autoDeleteICloud) private var autoDeleteICloud = false
    @AppStorage(Prefs.autoDeleteDisk) private var autoDeleteDisk = false
    @AppStorage(Prefs.confirmLargeDeletes) private var confirmLarge = true
    @AppStorage(Prefs.confirmThreshold) private var threshold = 20
    @AppStorage(Prefs.mirrorDisk) private var mirrorDisk = false
    @AppStorage(Prefs.mirrorPhotos) private var mirrorPhotos = false
    @StateObject private var state = PhotosPaneState()

    var body: some View {
        Form {
            Section("Import") {
                Toggle("Import new downloads into Photos automatically", isOn: $autoImport)
                if !app.importStatus.isEmpty {
                    Text(app.importStatus).font(.callout).foregroundStyle(.secondary)
                }
                Text("Off by default. Photos imports into the library it has open (normally the System Photo Library) and skips photos it already has. The Photos app opens when something is imported.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("When you delete photos in Photos") {
                Toggle("Delete them from iCloud automatically", isOn: $autoDeleteICloud)
                Toggle("Delete them from the disk automatically (moves the files to the Trash)", isOn: $autoDeleteDisk)
                Text("Both switches are off by default and work separately. They run after every sync, for photos that are in Photos “Recently Deleted” and match a downloaded file. A photo deleted only from the disk can be downloaded again while it is among the newest photos in iCloud.")
                    .font(.caption).foregroundStyle(.secondary)
                if !app.deletionStatus.isEmpty {
                    Text(app.deletionStatus).font(.callout).foregroundStyle(.secondary)
                }
            }
            Section("When you delete photos in iCloud") {
                Toggle("Delete them from the disk automatically (moves the files to the Trash)", isOn: $mirrorDisk)
                Toggle("Delete them from Photos automatically (macOS asks you to confirm)", isOn: $mirrorPhotos)
                Text("Both switches are off by default and work separately. After every sync, the photos in iCloud's “Recently Deleted” that you downloaded are removed here. Photos always shows its own confirmation, so that part is never silent. Photos you delete from iCloud with the review window land there too, so with these switches on they disappear from the disk and Photos as well.")
                    .font(.caption).foregroundStyle(.secondary)
                if !app.mirrorStatus.isEmpty {
                    Text(app.mirrorStatus).font(.callout).foregroundStyle(.secondary)
                }
            }
            Section("Safety") {
                Toggle("Ask for confirmation when many photos are deleted at once (both directions)", isOn: $confirmLarge)
                IntPicker(title: "Ask when more than", value: $threshold, options: [
                    (5, "5 photos"), (10, "10 photos"), (20, "20 photos"), (50, "50 photos"), (100, "100 photos"),
                ], custom: { "\($0) photos" })
                .disabled(!confirmLarge)
                Text(confirmLarge
                     ? "You get a notification with a Delete button, and the panel shows the waiting photos. Set notifications for Photos Sync to “Alerts” in System Settings so the buttons stay visible."
                     : "Confirmation is off: any number of photos is deleted without asking.")
                    .font(.caption).foregroundStyle(confirmLarge ? Color.secondary : Color.orange)
            }
            Section("Files downloaded so far") {
                HStack {
                    Text(state.pendingCount.map { "\($0) not in Photos yet" } ?? "Not counted yet")
                    Spacer()
                    Button("Count") { state.pendingCount = app.notImportedFiles().count }
                    Button("Import them…") {
                        state.pendingCount = app.notImportedFiles().count
                        state.confirming = true
                    }
                }
                Text("The first import asks for permission to control Photos (System Settings, Privacy & Security, Automation).")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
        .confirmationDialog(
            "Import \(state.pendingCount ?? 0) file(s) into Photos?",
            isPresented: $state.confirming, titleVisibility: .visible
        ) {
            Button("Import") { app.importExistingFiles() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("They are added to the library that Photos has open.")
        }
        .onAppear { state.pendingCount = app.notImportedFiles().count }
    }
}

private struct DeletionsPane: View {
    @AppStorage(Prefs.photosLibrary) private var photosLibrary = ""
    @AppStorage(Prefs.minAgeDays) private var minAgeDays = 0.0
    @AppStorage(Prefs.maxCandidates) private var maxCandidates = 10

    var body: some View {
        Form {
            Section("Safeguards") {
                Text("Photos you delete in the Photos app are offered for deletion from iCloud when they are still in “Recently Deleted” and match a downloaded file. In the review window you confirm every deletion yourself; automatic deletion is set under Apple Photos.")
                    .font(.callout).foregroundStyle(.secondary)
                IntPicker(title: "Offer photos deleted", value: Binding(
                    get: { Int(minAgeDays) }, set: { minAgeDays = Double($0) }
                ), options: [
                    (0, "Immediately"), (1, "At least 1 day ago"), (3, "At least 3 days ago"),
                    (7, "At least 7 days ago"), (14, "At least 14 days ago"), (30, "At least 30 days ago"),
                ], custom: { "At least \($0) days ago" })
                IntPicker(title: "Hard limit", value: $maxCandidates, options: [
                    (10, "10 photos at once"), (25, "25 photos at once"), (50, "50 photos at once"),
                    (100, "100 photos at once"), (250, "250 photos at once"), (1000, "1,000 photos at once"),
                ], custom: { "\($0) photos at once" })
                Text("The review window offers no more than this many photos. The confirmation limit under Apple Photos applies to automatic deletion.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("Photos library") {
                TextField("Library path", text: $photosLibrary)
                Text("The app needs Full Disk Access to read it. The library is only read, never modified.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section {
                Button("Open audit log") { NSWorkspace.shared.open(URL(fileURLWithPath: auditLogPath())) }
            }
        }
        .formStyle(.grouped)
    }
}

private func auditLogPath() -> String {
    NSHomeDirectory() + "/Library/Logs/icloudpd-menubar/deletions.log"
}

private struct NotificationsPane: View {
    @AppStorage(Prefs.notifyOnInput) private var onInput = true
    @AppStorage(Prefs.notifyOnError) private var onError = true

    var body: some View {
        Form {
            Section("Notify me when") {
                Toggle("A two-factor code or password is needed", isOn: $onInput)
                Toggle("Syncing fails", isOn: $onError)
            }
        }
        .formStyle(.grouped)
    }
}

private struct AdvancedPane: View {
    @AppStorage(Prefs.pythonPath) private var pythonPath = ""
    @AppStorage(Prefs.sourcePath) private var sourcePath = ""
    @AppStorage(Prefs.logLevel) private var logLevel = "info"
    @AppStorage(Prefs.untilFound) private var untilFound = 0

    var body: some View {
        Form {
            Section("Early stop") {
                IntPicker(title: "Stop after", value: $untilFound, options: [
                    (0, "Off"), (10, "10 known photos in a row"), (50, "50 known photos in a row"),
                    (200, "200 known photos in a row"),
                ], custom: { "\($0) known photos in a row" })
                Text("Extra shortcut on top of the newest-photos limit: stop as soon as this many photos in a row are already downloaded.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("icloudpd") {
                TextField("Python", text: $pythonPath)
                TextField("icloudpd sources (src folder)", text: $sourcePath)
                Text("The progress icon needs the repository version of icloudpd (it adds /api/status).")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("Logging") {
                Picker("Log level", selection: $logLevel) {
                    Text("Info").tag("info")
                    Text("Debug").tag("debug")
                    Text("Errors only").tag("error")
                }
                Button("Open log folder") { NSWorkspace.shared.open(logDirectory()) }
            }
        }
        .formStyle(.grouped)
    }
}
