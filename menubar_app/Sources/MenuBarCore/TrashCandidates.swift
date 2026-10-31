import Foundation
import SQLite3

/// A photo that is in the Photos "Recently Deleted" and matches a file downloaded by icloudpd.
public struct TrashCandidate: Codable, Hashable, Identifiable {
    public var id: String { "\(name.uppercased())|\(size)" }
    public let name: String
    public let size: Int64
    public let createdUnix: Int64
    public let trashedUnix: Int64
    public let path: String

    public init(name: String, size: Int64, createdUnix: Int64, trashedUnix: Int64, path: String) {
        self.name = name
        self.size = size
        self.createdUnix = createdUnix
        self.trashedUnix = trashedUnix
        self.path = path
    }
}

public struct ScanOptions {
    public var libraryPath: String
    public var stagingPath: String
    /// Only photos that were trashed at least this many days ago are offered.
    public var minAgeDays: Double
    /// Refuse (throw) when more candidates than this are found.
    public var maxCandidates: Int

    public init(libraryPath: String, stagingPath: String, minAgeDays: Double = 0, maxCandidates: Int = 10) {
        self.libraryPath = libraryPath
        self.stagingPath = stagingPath
        self.minAgeDays = minAgeDays
        self.maxCandidates = maxCandidates
    }
}

public struct ScanResult {
    public var candidates: [TrashCandidate] = []
    public var trashedTotal = 0
    public var assetTotal = 0
    public var stagedFiles = 0
    public var skippedTooRecent = 0
    public var ambiguous = 0
}

public enum ScanError: LocalizedError {
    case stagingMissing(String)
    case libraryUnreadable(String)
    case tooManyCandidates(found: Int, max: Int)

    public var errorDescription: String? {
        switch self {
        case .stagingMissing(let p):
            return "Download folder not found: \(p). Is the disk mounted?"
        case .libraryUnreadable(let m):
            return "Cannot read the Photos library (\(m)). Give the app Full Disk Access."
        case .tooManyCandidates(let found, let max):
            return "\(found) photos match, more than the safety limit of \(max). Nothing will be offered for deletion."
        }
    }
}

private let appleEpoch: Double = 978_307_200  // 2001-01-01 in unix seconds

/// Read-only. Copies the Photos database to a temp folder, never writes to the library.
public func scanTrashCandidates(_ options: ScanOptions, now: Date = Date()) throws -> ScanResult {
    let fm = FileManager.default
    var result = ScanResult()

    // 1) index downloaded files by (NAME, size)
    var isDir: ObjCBool = false
    guard fm.fileExists(atPath: options.stagingPath, isDirectory: &isDir), isDir.boolValue else {
        throw ScanError.stagingMissing(options.stagingPath)
    }
    var staged: [String: [String]] = [:]
    let keys: [URLResourceKey] = [.fileSizeKey, .isRegularFileKey]
    if let walker = fm.enumerator(at: URL(fileURLWithPath: options.stagingPath), includingPropertiesForKeys: keys) {
        for case let url as URL in walker {
            guard let values = try? url.resourceValues(forKeys: Set(keys)),
                  values.isRegularFile == true, let size = values.fileSize else { continue }
            staged["\(url.lastPathComponent.uppercased())|\(size)", default: []].append(url.path)
            result.stagedFiles += 1
        }
    }

    // 2) copy the database (plus WAL) so we never touch the live files
    let tmp = fm.temporaryDirectory.appendingPathComponent("icloudpd-menubar-\(UUID().uuidString)")
    try fm.createDirectory(at: tmp, withIntermediateDirectories: true)
    defer { try? fm.removeItem(at: tmp) }
    let dbDir = URL(fileURLWithPath: options.libraryPath).appendingPathComponent("database")
    for name in ["Photos.sqlite", "Photos.sqlite-wal", "Photos.sqlite-shm"] {
        let src = dbDir.appendingPathComponent(name)
        guard fm.fileExists(atPath: src.path) else { continue }
        do { try fm.copyItem(at: src, to: tmp.appendingPathComponent(name)) } catch {
            throw ScanError.libraryUnreadable(error.localizedDescription)
        }
    }
    let dbPath = tmp.appendingPathComponent("Photos.sqlite").path
    guard fm.fileExists(atPath: dbPath) else { throw ScanError.libraryUnreadable("Photos.sqlite not found") }

    var db: OpaquePointer?
    guard sqlite3_open_v2(dbPath, &db, SQLITE_OPEN_READONLY, nil) == SQLITE_OK, let db else {
        throw ScanError.libraryUnreadable("cannot open database")
    }
    defer { sqlite3_close(db) }

    func scalar(_ sql: String) throws -> Int {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK, let stmt else {
            throw ScanError.libraryUnreadable(String(cString: sqlite3_errmsg(db)))
        }
        defer { sqlite3_finalize(stmt) }
        return sqlite3_step(stmt) == SQLITE_ROW ? Int(sqlite3_column_int64(stmt, 0)) : 0
    }
    result.assetTotal = try scalar("select count(*) from ZASSET")
    result.trashedTotal = try scalar("select count(*) from ZASSET where ZTRASHEDSTATE = 1")

    // 3) trashed assets matched against downloaded files
    let sql = """
        select aa.ZORIGINALFILENAME, aa.ZORIGINALFILESIZE, a.ZTRASHEDDATE, a.ZDATECREATED
        from ZASSET a join ZADDITIONALASSETATTRIBUTES aa on aa.ZASSET = a.Z_PK
        where a.ZTRASHEDSTATE = 1
        """
    var stmt: OpaquePointer?
    guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK, let stmt else {
        throw ScanError.libraryUnreadable(String(cString: sqlite3_errmsg(db)))
    }
    defer { sqlite3_finalize(stmt) }

    while sqlite3_step(stmt) == SQLITE_ROW {
        guard sqlite3_column_type(stmt, 0) != SQLITE_NULL, sqlite3_column_type(stmt, 1) != SQLITE_NULL,
              let cName = sqlite3_column_text(stmt, 0) else { continue }
        let name = String(cString: cName)
        let size = sqlite3_column_int64(stmt, 1)
        let trashed = sqlite3_column_double(stmt, 2) + appleEpoch
        let created = sqlite3_column_double(stmt, 3) + appleEpoch

        if (now.timeIntervalSince1970 - trashed) / 86_400 < options.minAgeDays {
            result.skippedTooRecent += 1
            continue
        }
        let hits = staged["\(name.uppercased())|\(size)"] ?? []
        if hits.count == 1 {
            result.candidates.append(TrashCandidate(
                name: name, size: size, createdUnix: Int64(created), trashedUnix: Int64(trashed), path: hits[0]))
        } else if hits.count > 1 {
            result.ambiguous += 1
        }
    }
    result.candidates.sort { $0.trashedUnix > $1.trashedUnix }

    if result.candidates.count > options.maxCandidates {
        throw ScanError.tooManyCandidates(found: result.candidates.count, max: options.maxCandidates)
    }
    return result
}
