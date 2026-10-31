import Foundation
import MenuBarCore
import UserNotifications

/// Shared by the "Review iCloud deletions" window and the automatic deletion during sync.
enum Deletion {
    /// Deletes the photos in iCloud with `icloudpd --delete-list`. iCloud keeps them in "Recently Deleted"
    /// for about 30 days. A dry run only reports what would happen.
    static func deleteFromICloud(_ items: [TrashCandidate], dryRun: Bool) async -> (ok: Bool, output: String) {
        guard !items.isEmpty else { return (true, "") }
        let listURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("icloudpd-delete-\(UUID().uuidString).txt")
        defer { try? FileManager.default.removeItem(at: listURL) }
        do { try writeDeleteList(items, to: listURL) } catch {
            return (false, "Cannot write list: \(error.localizedDescription)")
        }
        var args = Launcher.commonArgs() + [
            "--password-provider", "keyring",
            "--delete-list", listURL.path,
            "--delete-list-max", "\(items.count)",  // the limit is enforced by the app before this point
        ]
        if dryRun { args.append("--dry-run") }
        appendAudit(mode: dryRun ? "DRY-RUN" : "DELETE", items: items)
        let (code, text) = await Launcher.runOnce(args: args)
        return (code == 0, text + (code == 0 ? "" : "\n(exit code \(code))"))
    }

    /// Local files of photos that were deleted in iCloud. icloudpd's own auto-delete finds them (it knows the
    /// folder structure and file names); in a dry run it only reports them, so the app can move them to the
    /// Trash instead of deleting them for good. Looks at the whole iCloud "Recently Deleted".
    static func findDeletedInICloud() async -> (ok: Bool, items: [TrashCandidate], output: String) {
        let args = Launcher.commonArgs() + Launcher.downloadArgs(includeRecent: false) + [
            "--recent", "1", "--auto-delete", "--dry-run", "--password-provider", "keyring",
        ]
        let (code, text) = await Launcher.runOnce(args: args, timeout: 300)
        guard code == 0 else { return (false, [], text) }
        let items = parseWouldDelete(text).map { path -> TrashCandidate in
            let attributes = try? FileManager.default.attributesOfItem(atPath: path)
            let size = (attributes?[.size] as? NSNumber)?.int64Value ?? 0
            // icloudpd sets the modification date of a file to the date the photo was taken
            let date = (attributes?[.modificationDate] as? Date)?.timeIntervalSince1970 ?? 0
            return TrashCandidate(name: URL(fileURLWithPath: path).lastPathComponent, size: size,
                                  createdUnix: Int64(date), trashedUnix: 0, path: path)
        }
        return (true, items, text)
    }

    /// Moves the downloaded files to the Trash, so they can still be restored from there.
    static func moveToTrash(_ items: [TrashCandidate]) -> (moved: Int, failures: [String], items: [TrashCandidate]) {
        var moved = 0
        var movedItems: [TrashCandidate] = []
        var failures: [String] = []
        for item in items {
            guard FileManager.default.fileExists(atPath: item.path) else { continue }  // already gone: nothing to do
            do {
                try FileManager.default.trashItem(at: URL(fileURLWithPath: item.path), resultingItemURL: nil)
                moved += 1
                movedItems.append(item)
            } catch {
                failures.append("\(item.name): \(error.localizedDescription)")
            }
        }
        appendAudit(mode: "TRASH", items: items)
        return (moved, failures, movedItems)
    }
}

/// Receives the buttons of a notification ("Delete" / "Not now").
final class NotificationDelegate: NSObject, UNUserNotificationCenterDelegate {
    var onAction: ((String) -> Void)?

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        onAction?(response.actionIdentifier)
        completionHandler()
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .list])
    }
}
