import Foundation
import MenuBarCore

// Usage: candidates-cli [--library PATH] [--staging PATH] [--min-age-days N] [--max-candidates N]
let home = NSHomeDirectory()
var options = ScanOptions(
    libraryPath: "\(home)/Pictures/Photos Library.photoslibrary",
    stagingPath: "\(home)/Pictures/iCloud")

// candidates-cli --classify LOGFILE: what would the app think went wrong, judging by the end of that file
if CommandLine.arguments.count == 3, CommandLine.arguments[1] == "--classify" {
    let text = (try? String(contentsOfFile: CommandLine.arguments[2], encoding: .utf8)) ?? ""
    let lines = text.split(separator: "\n").map(String.init)
    let f = classifyFailure(Array(lines.suffix(40)))
    print("\(f.kind): \(f.summary) | \(f.detail)")
    exit(0)
}

// candidates-cli --parse-would-delete FILE: the local paths found in the output of an auto-delete dry run
if CommandLine.arguments.count == 3, CommandLine.arguments[1] == "--parse-would-delete" {
    let text = (try? String(contentsOfFile: CommandLine.arguments[2], encoding: .utf8)) ?? ""
    for path in parseWouldDelete(text) { print(isSidecar(path) ? "sidecar \(path)" : "photo   \(path)") }
    exit(0)
}

// candidates-cli --export-path UNIX_DATE STRUCTURE NAME TAKEN...: where a photo from Photos would be saved
if CommandLine.arguments.count >= 5, CommandLine.arguments[1] == "--export-path" {
    let date = Date(timeIntervalSince1970: Double(CommandLine.arguments[2]) ?? 0)
    let folder = exportSubfolder(structure: CommandLine.arguments[3], date: date, timeZone: TimeZone(identifier: "UTC")!)
    let taken = Set(CommandLine.arguments.dropFirst(5))
    let name = uniqueFileName(CommandLine.arguments[4], in: "", exists: { taken.contains(($0 as NSString).lastPathComponent) })
    print("folder=\(folder.isEmpty ? "(root)" : folder) name=\(name)")
    exit(0)
}

var args = CommandLine.arguments.dropFirst().makeIterator()
while let arg = args.next() {
    switch arg {
    case "--library": options.libraryPath = args.next() ?? options.libraryPath
    case "--staging": options.stagingPath = args.next() ?? options.stagingPath
    case "--min-age-days": options.minAgeDays = Double(args.next() ?? "") ?? options.minAgeDays
    case "--max-candidates": options.maxCandidates = Int(args.next() ?? "") ?? options.maxCandidates
    default:
        FileHandle.standardError.write(Data("unknown option \(arg)\n".utf8))
        exit(64)
    }
}

do {
    let r = try scanTrashCandidates(options)
    print("trashed in Photos: \(r.trashedTotal) of \(r.assetTotal); staged files: \(r.stagedFiles)")
    print("skipped (too recent): \(r.skippedTooRecent); ambiguous: \(r.ambiguous)")
    print("candidates for iCloud deletion: \(r.candidates.count)")
    for c in r.candidates {
        print("  \(c.name)\t\(c.size)\ttrashed \(Date(timeIntervalSince1970: TimeInterval(c.trashedUnix)))\t\(c.path)")
    }
} catch {
    FileHandle.standardError.write(Data("ERROR: \(error.localizedDescription)\n".utf8))
    exit(2)
}
