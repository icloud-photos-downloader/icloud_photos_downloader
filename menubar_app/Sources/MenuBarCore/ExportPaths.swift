import Foundation

/// The sub folder icloudpd's `--folder-structure` would use for a photo taken at `date`
/// (empty for "everything in one folder").
public func exportSubfolder(structure: String, date: Date, timeZone: TimeZone = .current) -> String {
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.timeZone = timeZone
    switch structure {
    case "{:%Y/%m/%d}": formatter.dateFormat = "yyyy/MM/dd"
    case "{:%Y/%m}": formatter.dateFormat = "yyyy/MM"
    case "{:%Y}": formatter.dateFormat = "yyyy"
    default: return ""
    }
    return formatter.string(from: date)
}

/// A file name that is not taken yet in `folder`: IMG_1.HEIC, then IMG_1_Photos.HEIC, IMG_1_Photos2.HEIC, ...
public func uniqueFileName(
    _ name: String, in folder: String,
    exists: (String) -> Bool = { FileManager.default.fileExists(atPath: $0) }
) -> String {
    func path(_ candidate: String) -> String { (folder as NSString).appendingPathComponent(candidate) }
    guard exists(path(name)) else { return name }
    let ext = (name as NSString).pathExtension
    let stem = (name as NSString).deletingPathExtension
    var counter = 1
    while true {
        let tag = counter == 1 ? "_Photos" : "_Photos\(counter)"
        let candidate = ext.isEmpty ? stem + tag : "\(stem)\(tag).\(ext)"
        if !exists(path(candidate)) { return candidate }
        counter += 1
    }
}
