import Foundation
import MenuBarCore

enum Prefs {
    static let username = "username"
    static let directory = "directory"
    static let intervalSeconds = "intervalSeconds"
    static let untilFound = "untilFound"
    static let pythonPath = "pythonPath"
    static let sourcePath = "sourcePath"
    static let photosLibrary = "photosLibrary"
    static let minAgeDays = "minAgeDays"
    static let startWatchingAtLaunch = "startWatchingAtLaunch"
    // download
    static let size = "size"
    static let livePhotoSize = "livePhotoSize"
    static let skipVideos = "skipVideos"
    static let skipPhotos = "skipPhotos"
    static let skipLivePhotos = "skipLivePhotos"
    static let forceSize = "forceSize"
    static let recent = "recent"
    static let albums = "albums"
    static let library = "library"
    static let skipCreatedBefore = "skipCreatedBefore"
    static let skipCreatedAfter = "skipCreatedAfter"
    // files and folders
    static let folderStructure = "folderStructure"
    static let fileMatchPolicy = "fileMatchPolicy"
    static let livePhotoMovPolicy = "livePhotoMovPolicy"
    static let keepUnicode = "keepUnicode"
    static let alignRaw = "alignRaw"
    static let xmpSidecar = "xmpSidecar"
    static let setExifDatetime = "setExifDatetime"
    // notifications / advanced
    static let notifyOnInput = "notifyOnInput"
    static let notifyOnError = "notifyOnError"
    static let logLevel = "logLevel"
    static let autoImportToPhotos = "autoImportToPhotos"
    static let autoDeleteICloud = "autoDeleteICloud"
    static let autoDeleteDisk = "autoDeleteDisk"
    static let confirmLargeDeletes = "confirmLargeDeletes"
    static let confirmThreshold = "confirmThreshold"
    static let mirrorDisk = "mirrorDiskFromICloud"
    static let mirrorPhotos = "mirrorPhotosFromICloud"
    static let exportNewToDisk = "exportNewToDisk"
    /// the Apple ID that was signed in successfully (no default)
    static let linkedAccount = "linkedAccount"

    /// The icloudpd sources copied into the app when it was built; empty when this build has none.
    static func bundledSource() -> String {
        guard let url = Bundle.main.resourceURL?.appendingPathComponent("icloudpd-src"),
              FileManager.default.fileExists(atPath: url.appendingPathComponent("icloudpd").path) else { return "" }
        return url.path
    }

    /// The Python that runs the installed `icloudpd` (read from its launcher script), or the system one.
    static func detectPython() -> String {
        let home = NSHomeDirectory()
        for launcher in ["/opt/homebrew/bin/icloudpd", "/usr/local/bin/icloudpd", "\(home)/.local/bin/icloudpd"] {
            guard let text = try? String(contentsOfFile: launcher, encoding: .utf8), text.hasPrefix("#!"),
                  let first = text.split(separator: "\n").first else { continue }
            let interpreter = String(first.dropFirst(2)).trimmingCharacters(in: .whitespaces)
            if FileManager.default.isExecutableFile(atPath: interpreter) { return interpreter }
        }
        return "/usr/bin/python3"
    }

    static func registerDefaults() {
        let home = NSHomeDirectory()
        UserDefaults.standard.register(defaults: [
            username: "",
            directory: "\(home)/Pictures/iCloud",
            intervalSeconds: 3600,
            untilFound: 0,  // extra early stop after N known photos; 0 = off
            pythonPath: detectPython(),
            sourcePath: bundledSource(),  // the icloudpd that comes with the app
            photosLibrary: "\(home)/Pictures/Photos Library.photoslibrary",
            minAgeDays: 0,
            startWatchingAtLaunch: true,
            size: "original", livePhotoSize: "original",
            skipVideos: false, skipPhotos: false, skipLivePhotos: true, forceSize: false,
            recent: 20,  // each sync only looks at the N newest photos; 0 = whole library
            albums: "", library: "", skipCreatedBefore: "", skipCreatedAfter: "",
            folderStructure: "{:%Y/%m/%d}", fileMatchPolicy: "name-size-dedup-with-suffix",
            livePhotoMovPolicy: "original", keepUnicode: false, alignRaw: "as-is",
            xmpSidecar: false, setExifDatetime: false,
            notifyOnInput: true, notifyOnError: true, logLevel: "info",
            autoImportToPhotos: false,
            autoDeleteICloud: false, autoDeleteDisk: false,
            confirmLargeDeletes: true, confirmThreshold: 20,
            mirrorDisk: false, mirrorPhotos: false, exportNewToDisk: false,
        ])
    }

    static var d: UserDefaults { .standard }
    static var scanOptions: ScanOptions {
        ScanOptions(
            libraryPath: d.string(forKey: photosLibrary) ?? "",
            stagingPath: d.string(forKey: directory) ?? "",
            minAgeDays: d.double(forKey: minAgeDays),
            maxCandidates: 10_000)  // no extra hard limit: the review window asks for every deletion
    }
}

let webUIURL = URL(string: "http://127.0.0.1:8080")!

/// PHOTOSSYNC_DOC lets the documentation screenshots open a window straight away:
/// "settings:general|download|files|photos|deletions|notifications|advanced", "review", or "activity"
/// (the panel then opens on the Sync Activity view). Unset in normal use.
enum DocMode {
    static var value: String { ProcessInfo.processInfo.environment["PHOTOSSYNC_DOC"] ?? "" }
}

/// Home folder for the app's own data (log, history). The environment variable PHOTOSSYNC_HOME replaces it;
/// that is how the demo instance for the documentation screenshots runs without touching real data.
func dataHome() -> URL {
    if let custom = ProcessInfo.processInfo.environment["PHOTOSSYNC_HOME"], !custom.isEmpty {
        return URL(fileURLWithPath: custom, isDirectory: true)
    }
    return FileManager.default.homeDirectoryForCurrentUser
}

func logDirectory() -> URL {
    let dir = dataHome().appendingPathComponent("Library/Logs/icloudpd-menubar", isDirectory: true)
    try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    return dir
}
