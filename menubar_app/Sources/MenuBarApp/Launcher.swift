import Foundation

/// Thread-safe collector for process output.
final class OutputBuffer: @unchecked Sendable {
    private var data = Data()
    private let lock = NSLock()
    func append(_ chunk: Data) { lock.lock(); data.append(chunk); lock.unlock() }
    var text: String { lock.lock(); defer { lock.unlock() }; return String(decoding: data, as: UTF8.self) }
}

enum Launcher {
    /// Process that runs icloudpd from the configured Python and source folder.
    static func makeProcess(args: [String]) -> Process {
        let d = UserDefaults.standard
        let process = Process()
        process.executableURL = URL(fileURLWithPath: d.string(forKey: Prefs.pythonPath) ?? "")
        process.arguments = ["-W", "ignore", "-c", "import sys; from icloudpd.cli import cli; sys.exit(cli())"] + args
        var env = ProcessInfo.processInfo.environment
        if let src = d.string(forKey: Prefs.sourcePath), !src.isEmpty { env["PYTHONPATH"] = src }
        process.environment = env
        return process
    }

    static func commonArgs() -> [String] {
        let d = UserDefaults.standard
        return ["-d", d.string(forKey: Prefs.directory) ?? "", "-u", d.string(forKey: Prefs.username) ?? "",
                "--log-level", d.string(forKey: Prefs.logLevel) ?? "info", "--no-progress-bar"]
    }

    /// What and how to download. A flag is only passed when it differs from icloudpd's own default.
    static func downloadArgs(includeRecent: Bool = true) -> [String] {
        let d = UserDefaults.standard
        func text(_ key: String) -> String { (d.string(forKey: key) ?? "").trimmingCharacters(in: .whitespaces) }
        var args: [String] = []
        func option(_ key: String, _ flag: String, default def: String) {
            let value = text(key)
            if !value.isEmpty && value != def { args += [flag, value] }
        }
        func toggle(_ key: String, _ flag: String) { if d.bool(forKey: key) { args.append(flag) } }

        option(Prefs.size, "--size", default: "original")
        option(Prefs.livePhotoSize, "--live-photo-size", default: "original")
        toggle(Prefs.forceSize, "--force-size")
        toggle(Prefs.skipVideos, "--skip-videos")
        toggle(Prefs.skipPhotos, "--skip-photos")
        toggle(Prefs.skipLivePhotos, "--skip-live-photos")
        if includeRecent, d.integer(forKey: Prefs.recent) > 0 { args += ["--recent", "\(d.integer(forKey: Prefs.recent))"] }
        for album in text(Prefs.albums).split(separator: ",") {
            let name = album.trimmingCharacters(in: .whitespaces)
            if !name.isEmpty { args += ["-a", name] }
        }
        option(Prefs.library, "--library", default: "")
        option(Prefs.skipCreatedBefore, "--skip-created-before", default: "")
        option(Prefs.skipCreatedAfter, "--skip-created-after", default: "")
        option(Prefs.folderStructure, "--folder-structure", default: "{:%Y/%m/%d}")
        option(Prefs.fileMatchPolicy, "--file-match-policy", default: "name-size-dedup-with-suffix")
        option(Prefs.livePhotoMovPolicy, "--live-photo-mov-filename-policy", default: "suffix")
        option(Prefs.alignRaw, "--align-raw", default: "as-is")
        toggle(Prefs.keepUnicode, "--keep-unicode-in-filenames")
        toggle(Prefs.xmpSidecar, "--xmp-sidecar")
        toggle(Prefs.setExifDatetime, "--set-exif-datetime")
        return args
    }

    /// Long-running watcher: periodic sync plus web UI (2FA / password) and /api/status on 127.0.0.1.
    static func watchArgs() -> [String] {
        let d = UserDefaults.standard
        var args = commonArgs() + downloadArgs() + [
            "--watch-with-interval", "\(max(5, d.integer(forKey: Prefs.intervalSeconds)))",
            "--password-provider", "keyring", "--password-provider", "webui",
            "--mfa-provider", "webui", "--webui-host", "127.0.0.1",
        ]
        let untilFound = d.integer(forKey: Prefs.untilFound)
        if untilFound > 0 { args += ["--until-found", "\(untilFound)"] }
        return args
    }

    /// One-shot run (used for --delete-list). Returns exit code and combined output.
    static func runOnce(args: [String], timeout: TimeInterval = 600,
                        onStart: ((Process) -> Void)? = nil) async -> (Int32, String) {
        await withCheckedContinuation { continuation in
            let process = makeProcess(args: args)
            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe
            process.standardInput = FileHandle.nullDevice
            let output = OutputBuffer()
            pipe.fileHandleForReading.readabilityHandler = { handle in
                output.append(handle.availableData)
            }
            process.terminationHandler = { p in
                pipe.fileHandleForReading.readabilityHandler = nil
                output.append(pipe.fileHandleForReading.readDataToEndOfFile())
                continuation.resume(returning: (p.terminationStatus, output.text))
            }
            DispatchQueue.global().asyncAfter(deadline: .now() + timeout) {
                if process.isRunning { process.terminate() }
            }
            do { try process.run(); onStart?(process) } catch {
                continuation.resume(returning: (-1, "Cannot start icloudpd: \(error.localizedDescription)"))
            }
        }
    }
}
