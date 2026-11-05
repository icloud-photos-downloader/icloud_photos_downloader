import Foundation

/// The app's own events (restarts, recovery attempts, problems), written into the same log file as
/// icloudpd's output so the whole story is in one readable place.
///
/// Everybody that writes to the file does it in append mode: every write goes to the current end of the file.
/// Without that, icloudpd (which keeps its own position in the file) overwrote the lines the app had added
/// since its last output.
enum AppLog {
    static var url: URL { logDirectory().appendingPathComponent("icloudpd.log") }

    /// A handle that appends. Also what icloudpd gets as its output.
    static func appendHandle() -> FileHandle? {
        let descriptor = open(url.path, O_WRONLY | O_APPEND | O_CREAT, 0o644)
        guard descriptor >= 0 else { return nil }
        return FileHandle(fileDescriptor: descriptor, closeOnDealloc: true)
    }

    static func write(_ message: String) {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        let line = "\(formatter.string(from: Date())) APP      \(message)\n"
        guard let data = line.data(using: .utf8), let handle = appendHandle() else { return }
        try? handle.write(contentsOf: data)
        try? handle.close()
    }
}
