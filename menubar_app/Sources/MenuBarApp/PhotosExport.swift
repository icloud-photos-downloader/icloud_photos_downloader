import AppKit
import MenuBarCore
import Photos

/// Saves a copy of the photos that were added to the Photos app (not by this app) to the download folder.
///
/// PhotoKit's change history says which photos are new since the last look, so nothing is guessed from dates.
/// Photos that came from the download folder in the first place are recognised by their file name and date
/// and skipped. PhotoKit only sees the System Photo Library.
enum PhotosExport {
    enum Outcome {
        case baselineSet
        case saved([TrashCandidate], skipped: Int)
        case denied
        case failed(String)
    }

    /// How far a photo's date may differ from the modification date of a file with the same name.
    static let dateTolerance: TimeInterval = 120

    static func run(directory: String, folderStructure: String, tokenURL: URL) async -> Outcome {
        guard await PHPhotoLibrary.requestAuthorization(for: .readWrite) == .authorized else { return .denied }
        let library = PHPhotoLibrary.shared()
        let current = library.currentChangeToken

        // the first look only sets the starting point: what is in Photos already is not exported
        guard let saved = loadToken(tokenURL) else {
            saveToken(current, to: tokenURL)
            return .baselineSet
        }
        let changes: PHPersistentChangeFetchResult
        do { changes = try library.fetchPersistentChanges(since: saved) } catch {
            saveToken(current, to: tokenURL)  // the history of that token is gone: start over from now
            return .failed("Photos could not tell what changed (\(error.localizedDescription)); watching from now on")
        }
        var inserted = Set<String>()
        for change in changes {
            if let details = try? change.changeDetails(for: .asset) { inserted.formUnion(details.insertedLocalIdentifiers) }
        }

        var items: [TrashCandidate] = []
        var skipped = 0
        if !inserted.isEmpty {
            let known = fileIndex(in: directory)
            let assets = PHAsset.fetchAssets(withLocalIdentifiers: Array(inserted), options: nil)
            var list: [PHAsset] = []
            assets.enumerateObjects { asset, _, _ in list.append(asset) }
            for asset in list {
                let created = asset.creationDate ?? Date()
                let resources = PHAssetResource.assetResources(for: asset).filter {
                    [.photo, .video, .pairedVideo, .alternatePhoto].contains($0.type)
                }
                if resources.isEmpty { continue }
                if resources.contains(where: { cameFromFolder($0.originalFilename, created: created, index: known) }) {
                    skipped += 1
                    continue
                }
                do {
                    items += try await save(resources, created: created, directory: directory, folderStructure: folderStructure)
                } catch {
                    return .failed("Saving a photo from Photos failed: \(error.localizedDescription)")  // token kept: tried again
                }
            }
        }
        saveToken(current, to: tokenURL)
        return .saved(items, skipped: skipped)
    }

    // MARK: - Saving

    private static func save(_ resources: [PHAssetResource], created: Date, directory: String,
                             folderStructure: String) async throws -> [TrashCandidate] {
        let folder = (directory as NSString).appendingPathComponent(exportSubfolder(structure: folderStructure, date: created))
        try FileManager.default.createDirectory(atPath: folder, withIntermediateDirectories: true)
        var saved: [TrashCandidate] = []
        for resource in resources {
            let name = uniqueFileName(resource.originalFilename, in: folder)
            let path = (folder as NSString).appendingPathComponent(name)
            let options = PHAssetResourceRequestOptions()
            options.isNetworkAccessAllowed = true
            try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
                PHAssetResourceManager.default().writeData(for: resource, toFile: URL(fileURLWithPath: path), options: options) { error in
                    if let error { continuation.resume(throwing: error) } else { continuation.resume() }
                }
            }
            // like icloudpd: the modification date is the date the photo was taken
            try? FileManager.default.setAttributes([.modificationDate: created], ofItemAtPath: path)
            let size = (try? FileManager.default.attributesOfItem(atPath: path)[.size] as? NSNumber)??.int64Value ?? 0
            saved.append(TrashCandidate(name: name, size: size, createdUnix: Int64(created.timeIntervalSince1970),
                                        trashedUnix: 0, path: path))
        }
        return saved
    }

    // MARK: - Photos that came from the folder

    /// file name (upper case) -> modification dates of the files with that name in the download folder
    private static func fileIndex(in directory: String) -> [String: [Date]] {
        var index: [String: [Date]] = [:]
        let keys: [URLResourceKey] = [.contentModificationDateKey, .isRegularFileKey]
        guard let walker = FileManager.default.enumerator(at: URL(fileURLWithPath: directory), includingPropertiesForKeys: keys)
        else { return index }
        for case let url as URL in walker {
            guard let values = try? url.resourceValues(forKeys: Set(keys)), values.isRegularFile == true,
                  let date = values.contentModificationDate else { continue }
            index[url.lastPathComponent.uppercased(), default: []].append(date)
        }
        return index
    }

    private static func cameFromFolder(_ name: String, created: Date, index: [String: [Date]]) -> Bool {
        (index[name.uppercased()] ?? []).contains { abs($0.timeIntervalSince(created)) <= dateTolerance }
    }

    // MARK: - Starting point

    private static func loadToken(_ url: URL) -> PHPersistentChangeToken? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        return try? NSKeyedUnarchiver.unarchivedObject(ofClass: PHPersistentChangeToken.self, from: data)
    }

    private static func saveToken(_ token: PHPersistentChangeToken, to url: URL) {
        if let data = try? NSKeyedArchiver.archivedData(withRootObject: token, requiringSecureCoding: true) {
            try? data.write(to: url)
        }
    }
}
