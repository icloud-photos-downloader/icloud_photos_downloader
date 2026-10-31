import Foundation

/// Imports files into the Apple Photos app through AppleScript (`osascript`).
/// Photos imports into the library it has open (normally the System Photo Library) and skips files it
/// already has. The first run asks for permission to control Photos (System Settings, Privacy &
/// Security, Automation).
enum PhotosImport {
    static let fileExtensions: Set<String> = [
        "heic", "heif", "jpg", "jpeg", "png", "gif", "tif", "tiff", "dng", "cr2", "cr3", "nef", "arw",
        "raf", "orf", "rw2", "mov", "mp4", "m4v",
    ]

    /// File paths are passed as arguments, never pasted into the script text.
    static let script = """
        on run argv
            set theFiles to {}
            repeat with p in argv
                set end of theFiles to POSIX file (contents of p)
            end repeat
            tell application "Photos" to import theFiles
        end run
        """

    static func run(paths: [String], script: String = script) async -> (ok: Bool, message: String) {
        guard !paths.isEmpty else { return (true, "") }
        return await withCheckedContinuation { continuation in
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
            process.arguments = ["-e", script] + paths
            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe
            process.standardInput = FileHandle.nullDevice
            let output = OutputBuffer()
            pipe.fileHandleForReading.readabilityHandler = { output.append($0.availableData) }
            process.terminationHandler = { p in
                pipe.fileHandleForReading.readabilityHandler = nil
                output.append(pipe.fileHandleForReading.readDataToEndOfFile())
                continuation.resume(returning: (p.terminationStatus == 0, describe(output.text, status: p.terminationStatus)))
            }
            DispatchQueue.global().asyncAfter(deadline: .now() + 600) {
                if process.isRunning { process.terminate() }
            }
            do { try process.run() } catch {
                continuation.resume(returning: (false, "Cannot start osascript: \(error.localizedDescription)"))
            }
        }
    }

    private static func describe(_ output: String, status: Int32) -> String {
        if status == 0 { return output.trimmingCharacters(in: .whitespacesAndNewlines) }
        if output.contains("-1743") {
            return "Not allowed to control Photos. Allow Photos Sync in System Settings, Privacy & Security, Automation."
        }
        let text = output.trimmingCharacters(in: .whitespacesAndNewlines)
        return text.isEmpty ? "osascript failed (exit code \(status))" : String(text.suffix(200))
    }
}
