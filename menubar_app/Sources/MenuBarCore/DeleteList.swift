import Foundation

/// File format read by `icloudpd --delete-list`: NAME<TAB>SIZE<TAB>UNIX_DATE per line.
public func writeDeleteList(_ items: [TrashCandidate], to url: URL) throws {
    let text = items.map { "\($0.name)\t\($0.size)\t\($0.createdUnix)\n" }.joined()
    try text.write(to: url, atomically: true, encoding: .utf8)
}

public func auditLogURL() -> URL {
    let dir = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Logs/icloudpd-menubar", isDirectory: true)
    try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    return dir.appendingPathComponent("deletions.log")
}

/// Append-only record of every dry run and real deletion request sent to iCloud.
public func appendAudit(mode: String, items: [TrashCandidate]) {
    let stamp = ISO8601DateFormatter().string(from: Date())
    let lines = items.map { "\(stamp)\t\(mode)\t\($0.name)\t\($0.size)\t\($0.createdUnix)\n" }.joined()
    guard let data = lines.data(using: .utf8) else { return }
    let url = auditLogURL()
    if let handle = try? FileHandle(forWritingTo: url) {
        defer { try? handle.close() }
        _ = try? handle.seekToEnd()
        try? handle.write(contentsOf: data)
    } else {
        try? data.write(to: url)
    }
}
