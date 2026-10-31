import AppKit
import MenuBarCore
import Photos

/// Deletes photos from the Photos library with PhotoKit. macOS shows its own confirmation dialog every
/// time, so this can never happen silently. Deleted photos go to "Recently Deleted" in Photos.
/// PhotoKit only sees the System Photo Library.
enum PhotosDelete {
    enum Outcome {
        case deleted(count: Int, notInPhotos: Int, items: [TrashCandidate])
        case cancelled
        case denied
        case failed(String)
    }

    /// How far a photo's date in Photos may differ from the modification date of the downloaded file.
    static let dateTolerance: TimeInterval = 120

    /// Nothing here runs on the main thread: the first access to the Photos library can take a long time, and
    /// the permission prompt must not freeze the app while it waits for an answer.
    static func delete(_ items: [TrashCandidate]) async -> Outcome {
        await MainActor.run { NSApp.activate(ignoringOtherApps: true) }  // so that the permission prompt is seen
        guard await PHPhotoLibrary.requestAuthorization(for: .readWrite) == .authorized else { return .denied }

        let photoItems = items.filter { !isSidecar($0.path) }
        let (assets, matched, missing) = await Task.detached(priority: .userInitiated) {
            () -> ([PHAsset], [TrashCandidate], Int) in
            var assets: [PHAsset] = []
            var matched: [TrashCandidate] = []
            var missing = 0
            for item in photoItems {
                let found = assetsNamed(item.name, around: TimeInterval(item.createdUnix))
                if found.isEmpty { missing += 1 } else { assets += found; matched.append(item) }
            }
            return (assets, matched, missing)
        }.value
        guard !assets.isEmpty else { return .deleted(count: 0, notInPhotos: missing, items: []) }

        await MainActor.run { NSApp.activate(ignoringOtherApps: true) }  // so that the confirmation dialog is seen
        do {
            try await PHPhotoLibrary.shared().performChanges {
                PHAssetChangeRequest.deleteAssets(assets as NSArray)
            }
            return .deleted(count: assets.count, notInPhotos: missing, items: matched)
        } catch {
            let ns = error as NSError
            if ns.domain == PHPhotosErrorDomain, ns.code == PHPhotosError.userCancelled.rawValue { return .cancelled }
            return .failed(error.localizedDescription)
        }
    }

    /// Photos whose original file name is `name` and whose date is close to `unix`.
    private static func assetsNamed(_ name: String, around unix: TimeInterval) -> [PHAsset] {
        let options = PHFetchOptions()
        options.predicate = NSPredicate(
            format: "creationDate >= %@ AND creationDate <= %@",
            Date(timeIntervalSince1970: unix - dateTolerance) as NSDate,
            Date(timeIntervalSince1970: unix + dateTolerance) as NSDate)
        var found: [PHAsset] = []
        PHAsset.fetchAssets(with: options).enumerateObjects { asset, _, _ in
            let names = PHAssetResource.assetResources(for: asset).map { $0.originalFilename.uppercased() }
            if names.contains(name.uppercased()) { found.append(asset) }
        }
        return found
    }
}
