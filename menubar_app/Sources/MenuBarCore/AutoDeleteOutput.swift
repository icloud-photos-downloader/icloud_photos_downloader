import Foundation

/// The local files that `icloudpd --auto-delete --dry-run` says it would delete: the files of photos that
/// were deleted in iCloud. Nothing is deleted by that run, so the app can move them to the Trash itself.
public func parseWouldDelete(_ output: String) -> [String] {
    let marker = "[DRY RUN] Would delete "
    var paths: [String] = []
    for line in output.split(whereSeparator: \.isNewline) {
        guard let range = line.range(of: marker) else { continue }
        let rest = String(line[range.upperBound...]).trimmingCharacters(in: .whitespaces)
        // "… in iCloud library …" is the message of --delete-list, not a local file
        if rest.isEmpty || rest.contains(" in iCloud library") { continue }
        if !paths.contains(rest) { paths.append(rest) }
    }
    return paths
}

/// Sidecar files go to the Trash with their photo, but they are not photos for Photos.
public func isSidecar(_ path: String) -> Bool {
    path.lowercased().hasSuffix(".xmp")
}
