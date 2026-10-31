import Foundation

/// The app's own events (restarts, recovery attempts, problems), written into the same log file as
/// icloudpd's output so the whole story is in one readable place.
enum AppLog {
    static var url: URL { logDirectory().appendingPathComponent("icloudpd.log") }

    static func write(_ message: String) {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        let line = "\(formatter.string(from: Date())) APP      \(message)\n"
        guard let data = line.data(using: .utf8) else { return }
        if let handle = try? FileHandle(forWritingTo: url) {
            defer { try? handle.close() }
            _ = try? handle.seekToEnd()
            try? handle.write(contentsOf: data)
        } else {
            try? data.write(to: url)
        }
    }
}
