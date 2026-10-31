import Foundation

public enum FailureKind: Equatable {
    /// the web UI port is taken, usually by an icloudpd left over from an earlier run
    case portInUse
    /// iCloud cannot be reached
    case network
    /// the Apple ID session or password is no longer valid; retrying will not help
    case authRequired
    case other
}

public struct Failure: Equatable {
    public let kind: FailureKind
    /// one sentence for a notification
    public let summary: String
    /// the most relevant log line
    public let detail: String

    public init(kind: FailureKind, summary: String, detail: String) {
        self.kind = kind
        self.summary = summary
        self.detail = detail
    }
}

/// Decides what went wrong from the last lines of the icloudpd log (or of a one-shot run's output).
public func classifyFailure(_ lines: [String]) -> Failure {
    let text = lines.joined(separator: "\n").lowercased()
    let detail = lines.last(where: { $0.contains(" ERROR ") })
        ?? lines.last(where: { !$0.trimmingCharacters(in: .whitespaces).isEmpty })
        ?? ""
    func has(_ needles: [String]) -> Bool { needles.contains { text.contains($0) } }

    if has(["address already in use", "errno 48"]) {
        return Failure(kind: .portInUse, summary: "Port 8080 is used by another program", detail: detail)
    }
    if has(["invalid email/password", "invalid apple id", "authentication required", "missing password",
            "incorrect password", "login failed", "password required", "two-factor code", "eoferror"]) {
        return Failure(kind: .authRequired, summary: "Sign-in to iCloud is needed", detail: detail)
    }
    if has(["cannot connect to apple icloud", "connectionerror", "max retries exceeded", "timed out",
            "name resolution", "network is unreachable", "connection reset", "connection aborted",
            "connection refused"]) {
        return Failure(kind: .network, summary: "Cannot reach iCloud (network problem)", detail: detail)
    }
    return Failure(kind: .other, summary: "Unexpected error while syncing", detail: detail)
}
