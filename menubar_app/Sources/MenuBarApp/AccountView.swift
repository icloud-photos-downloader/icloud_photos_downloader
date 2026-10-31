import AppKit
import MenuBarCore
import SwiftUI

/// Links the Apple ID: a sign-in in the browser (password and two-factor code) through icloudpd's web UI.
@MainActor
final class AccountModel: ObservableObject {
    @Published var busy = false
    @Published var confirmingUnlink = false
    /// why the last attempt did not work
    @Published var failure: String?

    private var signInProcess: Process?

    private var username: String {
        (UserDefaults.standard.string(forKey: Prefs.username) ?? "").trimmingCharacters(in: .whitespaces)
    }

    /// The sync is paused meanwhile because the sign-in page needs the same port (8080).
    func link(_ app: AppModel) async {
        guard !username.isEmpty else { return }
        busy = true
        failure = nil
        defer { busy = false; signInProcess = nil }
        let wasRunning = app.isRunning
        if wasRunning { await app.stopWatchingAndWait() }

        Task {
            try? await Task.sleep(nanoseconds: 4_000_000_000)
            if busy { NSWorkspace.shared.open(webUIURL) }
        }
        let args = Launcher.commonArgs() + [
            "--auth-only", "--password-provider", "keyring", "--password-provider", "webui",
            "--mfa-provider", "webui", "--webui-host", "127.0.0.1",
        ]
        let (code, output) = await Launcher.runOnce(args: args, timeout: 600) { [weak self] process in
            Task { @MainActor in self?.signInProcess = process }
        }
        if code == 0 {
            UserDefaults.standard.set(username, forKey: Prefs.linkedAccount)
            AppLog.write("account linked")
        } else {
            failure = cancelled ? "Cancelled" : describe(output)
            AppLog.write("linking the account failed: \(failure ?? "")")
        }
        cancelled = false
        if wasRunning { app.startWatching() }
    }

    private var cancelled = false

    /// Signs out: stops the sync, removes the saved iCloud session of this Apple ID and clears the account
    /// from the settings, so another Apple ID can be entered. The password in the keychain is left alone.
    func unlink(_ app: AppModel) async {
        let user = username
        busy = true
        defer { busy = false }
        await app.stopWatchingAndWait()
        // icloudpd names its session files after the Apple ID without punctuation
        let base = String(user.filter { $0.isLetter || $0.isNumber })
        let folder = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".pyicloud")
        if !base.isEmpty {
            for name in [base, base + ".session"] {
                try? FileManager.default.removeItem(at: folder.appendingPathComponent(name))
            }
        }
        UserDefaults.standard.removeObject(forKey: Prefs.linkedAccount)
        UserDefaults.standard.set("", forKey: Prefs.username)
        failure = nil
        AppLog.write("account unlinked")
    }

    func cancel() {
        cancelled = true
        signInProcess?.terminate()
    }

    private func describe(_ output: String) -> String {
        let failure = classifyFailure(output.split(separator: "\n").map(String.init))
        switch failure.kind {
        case .authRequired: return "Sign-in did not complete (wrong password or code?)"
        case .network: return failure.summary
        case .portInUse: return "Port 8080 is busy, stop the sync and try again"
        case .other: return failure.detail.isEmpty ? "Sign-in did not complete" : String(failure.detail.suffix(120))
        }
    }
}

/// Apple ID field and, only while the account is not linked, a "Link Account" button.
struct AccountSection: View {
    @EnvironmentObject var app: AppModel
    @AppStorage(Prefs.username) private var username = ""
    @AppStorage(Prefs.linkedAccount) private var linkedAccount = ""
    @StateObject private var account = AccountModel()

    private var email: String { username.trimmingCharacters(in: .whitespaces) }

    /// Linked means this Apple ID was signed in successfully (or the sync is running with it) and
    /// the session has not been asked to sign in again.
    private var isLinked: Bool {
        guard !email.isEmpty, linkedAccount.caseInsensitiveCompare(email) == .orderedSame else { return false }
        return app.state != .needsMFA && app.state != .needsPassword
    }

    var body: some View {
        Section("Account") {
            TextField("Apple ID (email)", text: $username)
            HStack(spacing: 8) {
                Circle().fill(dotColor).frame(width: 9, height: 9)
                Text(statusText).lineLimit(2)
                Spacer()
                if account.busy {
                    ProgressView().controlSize(.small)
                    Button("Cancel") { account.cancel() }
                } else if isLinked {
                    Button("Unlink") { account.confirmingUnlink = true }
                } else {
                    Button("Link Account") { Task { await account.link(app) } }
                        .disabled(!email.contains("@"))
                }
            }
            if let reason = account.failure, !isLinked {
                Text(reason).font(.caption).foregroundStyle(.red)
            }
            Text(helpText).font(.caption).foregroundStyle(.secondary)
        }
        .confirmationDialog("Unlink \(email)?", isPresented: $account.confirmingUnlink, titleVisibility: .visible) {
            Button("Unlink", role: .destructive) { Task { await account.unlink(app) } }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Syncing stops and the saved sign-in is removed. Photos you already downloaded stay where they are. You can then link another Apple ID, or the same one again.")
        }
    }

    private var statusText: String {
        if account.busy { return "Waiting for you to sign in in the browser…" }
        if isLinked { return "Linked: \(email)" }
        if email.isEmpty { return "Enter your Apple ID" }
        if app.needsInput { return "Disconnected: sign-in needed" }
        return "Not linked"
    }

    private var dotColor: Color {
        if account.busy { return .blue }
        if isLinked { return .green }
        return app.needsInput ? .orange : .gray
    }

    private var helpText: String {
        isLinked
            ? "Unlink to use another Apple ID."
            : "“Link Account” opens a page in your browser for the password and the two-factor code. The password is stored in the macOS keychain."
    }
}
