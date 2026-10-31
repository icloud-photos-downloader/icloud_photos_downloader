import AppKit
import Foundation
import MenuBarCore
import UserNotifications

@MainActor
final class AppModel: ObservableObject {
    enum State: Equatable {
        case stopped
        case starting
        case idle
        case syncing(percent: Int, done: Int, total: Int)
        case waiting(seconds: Int)
        /// "Sync now" was pressed; icloudpd needs a moment to wake up
        case syncRequested
        case needsMFA
        case needsPassword
        /// a problem was found and the app is fixing it by itself
        case recovering
        /// automatic recovery did not help; details are in the log
        case error(String)
    }

    @Published private(set) var state: State = .stopped
    @Published private(set) var activity: [ActivityFile] = AppModel.loadActivity()
    @Published var showActivity = DocMode.value == "activity"
    @Published private(set) var importedPaths: Set<String> = AppModel.loadImported()
    @Published private(set) var importStatus = ""
    /// photos deleted in Photos that wait for the user's confirmation (more than the limit at once)
    @Published private(set) var pendingDeletion: [TrashCandidate] = []
    @Published private(set) var deletionStatus = ""
    /// photos deleted in iCloud whose files / Photos copies wait for the user's confirmation
    @Published private(set) var pendingMirror: [TrashCandidate] = []
    @Published private(set) var mirrorStatus = ""
    @Published private(set) var exportStatus = ""

    private var process: Process?
    private var stoppedByUser = false
    private var timer: Timer?
    private var lastDownloadedTotal = -1
    private var syncRequestedAt: Date?
    private var waitingAtRequest = 0
    private var termSource: DispatchSourceSignal?

    // automatic deletion (what was deleted in Photos is deleted from iCloud and/or the disk)
    private var autoDeleting = false
    private var mirroring = false
    private var lastMirrorSignature = ""
    private var mirroredPaths: Set<String> = AppModel.loadMirrored()
    private var lastPendingSignature = ""
    private var deletedFromICloud: Set<String> = AppModel.loadDeletedFromICloud()
    private let notificationDelegate = NotificationDelegate()

    // import into Apple Photos
    private var importQueue: [String] = []
    private var importing = false
    private var importFailureNotified = false

    // automatic recovery
    private var logOffset: UInt64 = 0
    private var retries = 0
    private var lastFailureAt: Date?
    /// the arguments the running icloudpd was started with; when the settings no longer give the same, it restarts
    private var launchedArgs: [String] = []
    private var restartTask: Task<Void, Never>?
    /// false from the moment a problem is shown until a sync pass ends without an error; until then the
    /// problem stays in the header (icloudpd itself just reports "waiting" again after a failed pass)
    private var problemCleared = true
    private var lastLogTriggerAt = Date.distantPast
    private var recoveryTask: Task<Void, Never>?
    private let retryDelays: [UInt64] = [30, 120, 300]

    init() {
        Prefs.registerDefaults()
        if Bundle.main.bundleIdentifier != nil {
            let center = UNUserNotificationCenter.current()
            center.requestAuthorization(options: [.alert]) { _, _ in }
            center.delegate = notificationDelegate
            notificationDelegate.onAction = { [weak self] action in
                Task { @MainActor in self?.handleNotificationAction(action) }
            }
            center.setNotificationCategories([
                UNNotificationCategory(
                    identifier: "CONFIRM_DELETE",
                    actions: [
                        UNNotificationAction(identifier: "confirmDelete", title: "Delete", options: [.destructive]),
                        UNNotificationAction(identifier: "skipDelete", title: "Not now", options: []),
                    ],
                    intentIdentifiers: [], options: []),
                UNNotificationCategory(
                    identifier: "CONFIRM_MIRROR",
                    actions: [
                        UNNotificationAction(identifier: "confirmMirror", title: "Delete", options: [.destructive]),
                        UNNotificationAction(identifier: "skipMirror", title: "Not now", options: []),
                    ],
                    intentIdentifiers: [], options: []),
            ])
        }
        // Never leave icloudpd running (it would keep port 8080) when the app goes away.
        NotificationCenter.default.addObserver(
            forName: NSApplication.willTerminateNotification, object: nil, queue: .main
        ) { [weak self] _ in MainActor.assumeIsolated { self?.terminateChild() } }
        signal(SIGTERM, SIG_IGN)
        let source = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
        source.setEventHandler { [weak self] in
            MainActor.assumeIsolated { self?.terminateChild() }
            exit(0)
        }
        source.resume()
        termSource = source
        NotificationCenter.default.addObserver(
            forName: UserDefaults.didChangeNotification, object: nil, queue: .main
        ) { [weak self] _ in MainActor.assumeIsolated { self?.settingsMayHaveChanged() } }
        startLibraryWatch()
        if UserDefaults.standard.bool(forKey: Prefs.startWatchingAtLaunch) {
            DispatchQueue.main.async { self.startWatching() }
        }
    }

    var isRunning: Bool { process?.isRunning == true }

    var iconName: String {
        switch state {
        case .stopped: return "icloud.slash"
        case .starting, .idle, .waiting: return "icloud"
        case .syncing, .syncRequested: return "arrow.triangle.2.circlepath.icloud"
        case .needsMFA, .needsPassword, .recovering: return "exclamationmark.icloud"
        case .error: return "xmark.icloud"
        }
    }

    /// Short on purpose; the full story is in the log.
    var statusLine: String {
        switch state {
        case .stopped:
            let user = UserDefaults.standard.string(forKey: Prefs.username) ?? ""
            return user.trimmingCharacters(in: .whitespaces).isEmpty ? "No account linked" : "Stopped"
        case .starting: return "Starting…"
        case .idle: return "Idle"
        case .syncing(let percent, let done, let total):
            return total > 0 ? "Syncing \(done)/\(total) (\(percent) %)" : "Syncing…"
        case .waiting(let seconds):
            return "Up to date, next sync in \(seconds / 60) min"
        case .syncRequested: return "Syncing now…"
        case .needsMFA: return "Two-factor code needed"
        case .needsPassword: return "Password needed"
        case .recovering: return "Problem, fixing it…"
        case .error: return "Sync problem"
        }
    }

    var hasProblem: Bool {
        switch state {
        case .recovering, .error: return true
        default: return false
        }
    }

    var needsInput: Bool { state == .needsMFA || state == .needsPassword }

    var isSyncing: Bool {
        switch state {
        case .syncing, .syncRequested: return true
        default: return false
        }
    }

    /// Adds the deletions the app carries out to the history (Sync Activity), next to the downloads.
    func recordEvents(_ kind: ActivityFile.Kind, _ items: [TrashCandidate]) {
        guard !items.isEmpty else { return }
        let now = Date().timeIntervalSince1970
        let events = items.enumerated().map { index, item in
            ActivityFile(name: item.name, path: item.path, size: item.size > 0 ? item.size : nil,
                         time: now + Double(index) * 0.001, kind: kind.rawValue)
        }
        activity = (events + activity).sorted { $0.time > $1.time }.prefix(200).map { $0 }
        saveActivity()
    }

    private var downloadCount: Int { activity.filter { $0.event == .downloaded }.count }

    var activitySummary: String {
        if case .syncing(_, let done, let total) = state {
            return total > 0 ? "Syncing \(done) of \(total) files" : "Syncing…"
        }
        if state == .syncRequested { return "Syncing…" }
        return downloadCount == 0 ? "No files synced yet" : "\(downloadCount) files synced recently"
    }

    // MARK: - Start / stop

    func startWatching() {
        guard !isRunning else { return }
        Task {
            // something already answers on 8080: usually an icloudpd left over from another run
            if await StatusClient.fetch() != nil {
                if freePort() {
                    AppLog.write("stopped a leftover icloudpd that was holding port 8080")
                    try? await Task.sleep(nanoseconds: 1_500_000_000)
                    launch()
                } else {
                    giveUp(Failure(kind: .portInUse, summary: "Port 8080 is used by another program", detail: ""))
                }
            } else {
                launch()
            }
        }
    }

    func stopWatching() {
        recoveryTask?.cancel()
        retries = 0
        stoppedByUser = true
        process?.terminate()
    }

    func stopWatchingAndWait() async {
        stopWatching()
        for _ in 0..<50 where isRunning { try? await Task.sleep(nanoseconds: 100_000_000) }
    }

    private func terminateChild() {
        stoppedByUser = true
        if let p = process, p.isRunning {
            p.terminate()
            p.waitUntilExit()
        }
    }

    private func launch() {
        guard !isRunning else { return }
        lastDownloadedTotal = -1
        let d = UserDefaults.standard
        guard !(d.string(forKey: Prefs.username) ?? "").trimmingCharacters(in: .whitespaces).isEmpty else {
            AppLog.write("no Apple ID is linked yet")
            set(.stopped)  // a normal state, not an error
            return
        }
        let args = Launcher.watchArgs()
        launchedArgs = args
        let p = Launcher.makeProcess(args: args)
        let logURL = AppLog.url
        if !FileManager.default.fileExists(atPath: logURL.path) {
            FileManager.default.createFile(atPath: logURL.path, contents: nil)
        }
        AppLog.write("starting sync")
        if let handle = try? FileHandle(forWritingTo: logURL) {
            _ = try? handle.seekToEnd()
            p.standardOutput = handle
            p.standardError = handle
        }
        logOffset = (try? FileManager.default.attributesOfItem(atPath: logURL.path)[.size] as? UInt64) ?? 0
        p.standardInput = FileHandle.nullDevice
        p.terminationHandler = { [weak self] proc in
            Task { @MainActor in self?.processEnded(proc) }
        }
        stoppedByUser = false
        do {
            try p.run()
            process = p
            set(.starting)
            startPolling()
        } catch {
            giveUp(Failure(kind: .other, summary: "Cannot start icloudpd", detail: error.localizedDescription))
        }
    }

    /// A sync setting was changed while icloudpd runs: it only knows the values it was started with, so it is
    /// restarted (after a pause, so that a few changes in a row cost one restart).
    private func settingsMayHaveChanged() {
        guard isRunning, Launcher.watchArgs() != launchedArgs else { return }
        restartTask?.cancel()
        restartTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            guard !Task.isCancelled, let self, self.isRunning, Launcher.watchArgs() != self.launchedArgs else { return }
            AppLog.write("settings changed, restarting the sync")
            await self.stopWatchingAndWait()
            self.startWatching()
        }
    }

    func syncNow() {
        guard isRunning else { return }
        if case .waiting(let seconds) = state { waitingAtRequest = seconds } else { waitingAtRequest = 0 }
        syncRequestedAt = Date()
        set(.syncRequested)  // show it at once instead of "Idle" until icloudpd has woken up
        Task { await StatusClient.resume() }
    }

    func openWebUI() { NSWorkspace.shared.open(webUIURL) }

    func openPhotosApp() {
        guard let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.apple.Photos") else { return }
        NSWorkspace.shared.openApplication(at: url, configuration: NSWorkspace.OpenConfiguration())
    }
    func openLog() { NSWorkspace.shared.open(AppLog.url) }

    // MARK: - Process end and polling

    private func processEnded(_ proc: Process) {
        guard process === proc else { return }  // an older process that was already replaced
        timer?.invalidate()
        timer = nil
        process = nil
        let status = proc.terminationStatus
        let signalled = proc.terminationReason == .uncaughtSignal
        if stoppedByUser || status == 0 {
            set(.stopped)
        } else if signalled && [SIGTERM, SIGINT, SIGHUP, SIGKILL].contains(status) {
            AppLog.write("icloudpd was stopped from outside (signal \(status))")
            set(.stopped)
        } else {
            AppLog.write("icloudpd exited with code \(status)")
            handleFailure(classifyFailure(tailLines(40)), processExited: true)
        }
    }

    private func startPolling() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 3, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.poll() }
        }
    }

    private func poll() async {
        guard isRunning else { return }
        settingsMayHaveChanged()  // also catches changes made outside the app, which send no notification
        checkLogForFailure()
        guard let status = await StatusClient.fetch() else { return }  // web server not up yet
        if let total = status.downloadedTotal, total != lastDownloadedTotal {
            lastDownloadedTotal = total
            if let response = await StatusClient.fetchActivity() { merge(response.files) }
        }
        let progress = status.progress
        if state == .syncRequested, let requested = syncRequestedAt {
            // keep "Syncing now…" until the pass really started, or finished (the countdown restarted)
            let finished = status.state == "waiting" && progress.waitingSeconds > waitingAtRequest
            if status.state != "syncing", !finished, Date().timeIntervalSince(requested) < 90 { return }
        }
        switch state {
        case .recovering, .error:
            // keep showing the problem until a pass has worked
            if !problemCleared, status.state == "waiting" || status.state == "idle" { return }
        default: break
        }
        switch status.state {
        case "idle": set(.idle)
        case "syncing":
            set(.syncing(percent: progress.photosPercent, done: progress.photosCounter, total: progress.photosCount))
        case "waiting": set(.waiting(seconds: progress.waitingSeconds))
        case "need_mfa": set(.needsMFA)
        case "need_password": set(.needsPassword)
        default: set(.idle)  // supplied_* / checking_*: input accepted, being verified
        }
    }

    // MARK: - Automatic recovery

    /// icloudpd keeps running after a failed pass ("Error processing user …" and then waits for the
    /// next interval), so the log is the only place where such failures show up.
    private func checkLogForFailure() {
        let text = newLogText()
        if text.contains("have been downloaded") {  // a pass that ended without an error
            problemCleared = true
            retries = 0
        }
        guard text.contains("Error processing user") || text.contains("Traceback (most recent call last)"),
              Date().timeIntervalSince(lastLogTriggerAt) > 20 else { return }
        lastLogTriggerAt = Date()
        handleFailure(classifyFailure(tailLines(40)), processExited: false)
    }

    private func handleFailure(_ failure: Failure, processExited: Bool) {
        if let last = lastFailureAt, Date().timeIntervalSince(last) > 600 { retries = 0 }
        lastFailureAt = Date()
        AppLog.write("problem: \(failure.summary). \(failure.detail)")

        switch failure.kind {
        case .authRequired:
            giveUp(failure)
        case .portInUse:
            if retries < 3, freePort() {
                retries += 1
                AppLog.write("freed port 8080, restarting sync (\(retries)/3)")
                set(.recovering)
                scheduleRecovery(after: 2) { [weak self] in
                    guard let self else { return }
                    await self.stopWatchingAndWait()
                    self.startWatching()
                }
            } else {
                giveUp(failure)
            }
        case .network, .other:
            guard retries < retryDelays.count else { giveUp(failure); return }
            let delay = retryDelays[retries]
            retries += 1
            AppLog.write("trying again in \(delay) s (\(retries)/\(retryDelays.count))")
            set(.recovering)
            scheduleRecovery(after: delay) { [weak self] in
                guard let self else { return }
                if processExited { self.startWatching() } else { self.syncNow() }
            }
        }
    }

    private func scheduleRecovery(after seconds: UInt64, _ action: @escaping @MainActor () async -> Void) {
        recoveryTask?.cancel()
        recoveryTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: seconds * 1_000_000_000)
            guard !Task.isCancelled, self?.stoppedByUser == false || self?.process == nil else { return }
            await action()
        }
    }

    /// Automatic recovery is exhausted (or pointless): show a short error and explain in a notification.
    private func giveUp(_ failure: Failure) {
        AppLog.write("giving up: \(failure.summary). See the lines above for details.")
        if failure.kind == .authRequired { UserDefaults.standard.removeObject(forKey: Prefs.linkedAccount) }
        set(.error(failure.summary))
        guard UserDefaults.standard.bool(forKey: Prefs.notifyOnError) else { return }
        var body = failure.summary + "."
        switch failure.kind {
        case .authRequired: body += " Open Settings, General and choose “Sign in…”."
        case .portInUse: body += " Close the other program or restart your Mac."
        default: body += " Automatic recovery did not help."
        }
        if !failure.detail.isEmpty { body += "\n" + String(failure.detail.suffix(160)) }
        notify("iCloud sync problem", body)
    }

    /// Stops an icloudpd that is not ours and holds the web UI port (a leftover from an earlier run).
    @discardableResult
    private func freePort() -> Bool {
        var killed = false
        for pid in shell("/usr/sbin/lsof", ["-nP", "-iTCP:8080", "-sTCP:LISTEN", "-t"])
            .split(whereSeparator: \.isNewline).compactMap({ Int32($0) }) {
            if let p = process, p.processIdentifier == pid { continue }
            if shell("/bin/ps", ["-o", "command=", "-p", "\(pid)"]).contains("icloudpd") {
                kill(pid, SIGTERM)
                killed = true
            }
        }
        return killed
    }

    private func shell(_ path: String, _ args: [String]) -> String {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: path)
        p.arguments = args
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = FileHandle.nullDevice
        guard (try? p.run()) != nil else { return "" }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        return String(decoding: data, as: UTF8.self)
    }

    private func newLogText() -> String {
        guard let handle = try? FileHandle(forReadingFrom: AppLog.url) else { return "" }
        defer { try? handle.close() }
        let size = (try? handle.seekToEnd()) ?? 0
        if size < logOffset { logOffset = 0 }
        try? handle.seek(toOffset: logOffset)
        let data = (try? handle.readToEnd()) ?? Data()
        logOffset = size
        return String(decoding: data, as: UTF8.self)
    }

    private func tailLines(_ count: Int) -> [String] {
        guard let handle = try? FileHandle(forReadingFrom: AppLog.url) else { return [] }
        defer { try? handle.close() }
        let size = (try? handle.seekToEnd()) ?? 0
        try? handle.seek(toOffset: size > 16_384 ? size - 16_384 : 0)
        let text = String(decoding: (try? handle.readToEnd()) ?? Data(), as: UTF8.self)
        return Array(text.split(separator: "\n", omittingEmptySubsequences: true).map(String.init).suffix(count))
    }

    // MARK: - State

    // MARK: - Automatic deletion

    private var lastDeletionTask: Task<Void, Never>?
    private var deletionRetries = 0
    private var exporting = false
    private var exportDeniedNotified = false

    // Deleting in Photos should reach iCloud soon, not at the next sync (up to an hour later): the app
    // watches the Photos database and checks for deleted photos shortly after it changed.
    private var libraryTimer: Timer?
    private var libraryStamp = Date.distantPast
    private var libraryChangedAt: Date?
    private var lastLibraryPassAt = Date.distantPast

    private func startLibraryWatch() {
        libraryStamp = libraryModified()
        libraryTimer = Timer.scheduledTimer(withTimeInterval: 15, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.checkLibrary() }
        }
    }

    private func libraryModified() -> Date {
        let database = URL(fileURLWithPath: UserDefaults.standard.string(forKey: Prefs.photosLibrary) ?? "")
            .appendingPathComponent("database")
        return ["Photos.sqlite", "Photos.sqlite-wal"].compactMap {
            (try? FileManager.default.attributesOfItem(atPath: database.appendingPathComponent($0).path))?[.modificationDate] as? Date
        }.max() ?? .distantPast
    }

    private func checkLibrary() {
        let d = UserDefaults.standard
        guard d.bool(forKey: Prefs.autoDeleteICloud) || d.bool(forKey: Prefs.autoDeleteDisk)
                || d.bool(forKey: Prefs.exportNewToDisk) else { return }
        let modified = libraryModified()
        if modified > libraryStamp {  // still changing: wait until it is quiet
            libraryStamp = modified
            libraryChangedAt = Date()
            return
        }
        // 20 s without changes, and not more often than once a minute (the deletion check copies the database)
        guard let changed = libraryChangedAt, Date().timeIntervalSince(changed) >= 20,
              Date().timeIntervalSince(lastLibraryPassAt) >= 60 else { return }
        libraryChangedAt = nil
        lastLibraryPassAt = Date()
        runSerialized { await self.autoDeletePass() }
        runSerialized { await self.exportPass() }
    }

    /// Deleting in both directions touches the same files, so the passes run one after another and never
    /// at the same time.
    private func runSerialized(_ work: @escaping @MainActor () async -> Void) {
        let previous = lastDeletionTask
        lastDeletionTask = Task {
            await previous?.value
            await work()
        }
    }

    private static func loadDeletedFromICloud() -> Set<String> {
        guard let data = try? Data(contentsOf: supportFile("deleted-from-icloud.json")),
              let ids = try? JSONDecoder().decode([String].self, from: data) else { return [] }
        return Set(ids)
    }

    private func saveDeletedFromICloud() {
        if let data = try? JSONEncoder().encode(deletedFromICloud.sorted()) {
            try? data.write(to: AppModel.supportFile("deleted-from-icloud.json"))
        }
    }

    /// Runs after every sync pass: what was deleted in Photos is deleted from iCloud and/or the disk,
    /// depending on the two switches in Settings. Above the limit it asks first.
    private func autoDeletePass() async {
        let d = UserDefaults.standard
        let wantICloud = d.bool(forKey: Prefs.autoDeleteICloud)
        let wantDisk = d.bool(forKey: Prefs.autoDeleteDisk)
        guard wantICloud || wantDisk, !autoDeleting else { return }
        autoDeleting = true
        defer { autoDeleting = false }

        var options = Prefs.scanOptions
        options.maxCandidates = Int.max  // the confirmation limit below decides
        let found: [TrashCandidate]
        do {
            found = try await Task.detached { try scanTrashCandidates(options).candidates }.value
        } catch {
            AppLog.write("automatic deletion skipped: \(error.localizedDescription)")
            return
        }
        // photos that came back from the trash must be handled again if they are deleted later
        deletedFromICloud.formIntersection(found.map(\.id))
        let work = found.filter { (wantICloud && !deletedFromICloud.contains($0.id)) || wantDisk }
        guard !work.isEmpty else { pendingDeletion = []; return }

        if d.bool(forKey: Prefs.confirmLargeDeletes), work.count > d.integer(forKey: Prefs.confirmThreshold) {
            askForConfirmation(work)
        } else {
            await performDeletion(work)
        }
    }

    private func askForConfirmation(_ items: [TrashCandidate]) {
        pendingDeletion = items
        let signature = items.map(\.id).sorted().joined(separator: ",")
        guard signature != lastPendingSignature else { return }  // already asked about exactly these
        lastPendingSignature = signature
        let d = UserDefaults.standard
        var targets: [String] = []
        if d.bool(forKey: Prefs.autoDeleteICloud) { targets.append("iCloud") }
        if d.bool(forKey: Prefs.autoDeleteDisk) { targets.append("the disk (to the Trash)") }
        AppLog.write("waiting for confirmation to delete \(items.count) photo(s)")
        notify(
            "Delete \(items.count) photos?",
            "\(items.count) photos deleted in Photos would be deleted from \(targets.joined(separator: " and ")). "
                + "That is more than your limit of \(d.integer(forKey: Prefs.confirmThreshold)), so please confirm.",
            category: "CONFIRM_DELETE")
    }

    private func handleNotificationAction(_ action: String) {
        switch action {
        case "confirmDelete": runSerialized { await self.confirmPendingDeletion() }
        case "skipDelete": AppLog.write("deletion skipped by the user")
        case "confirmMirror": runSerialized { await self.confirmPendingMirror() }
        case "skipMirror": AppLog.write("deleting what was deleted in iCloud skipped by the user")
        default: break
        }
    }

    /// The user agreed: look again (the Photos library may have changed) and delete what is still waiting.
    private func confirmPendingDeletion() async {
        guard !autoDeleting else { return }
        autoDeleting = true
        defer { autoDeleting = false }
        let wanted = Set(pendingDeletion.map(\.id))
        var options = Prefs.scanOptions
        options.maxCandidates = Int.max
        guard let found = try? await Task.detached(operation: { try scanTrashCandidates(options).candidates }).value else { return }
        let work = found.filter { wanted.contains($0.id) }
        await performDeletion(work)
    }

    private func performDeletion(_ items: [TrashCandidate]) async {
        let d = UserDefaults.standard
        let wantICloud = d.bool(forKey: Prefs.autoDeleteICloud)
        let wantDisk = d.bool(forKey: Prefs.autoDeleteDisk)
        var summary: [String] = []

        if wantICloud {
            let todo = items.filter { !deletedFromICloud.contains($0.id) }
            if !todo.isEmpty {
                deletionStatus = "Deleting \(todo.count) photo(s) from iCloud…"
                let result = await Deletion.deleteFromICloud(todo, dryRun: false)
                AppLog.write("automatic deletion from iCloud \(result.ok ? "done" : "failed"): \(result.output.suffix(300))")
                if result.ok {
                    deletedFromICloud.formUnion(todo.map(\.id))
                    saveDeletedFromICloud()
                    deletionRetries = 0
                    recordEvents(.deletedICloud, todo)
                    summary.append("\(todo.count) deleted from iCloud")
                } else {
                    deletionRetries += 1
                    let willRetry = deletionRetries <= 3
                    deletionStatus = willRetry
                        ? "Deleting from iCloud failed, trying again in 5 minutes."
                        : "Deleting from iCloud failed, see the log."
                    if willRetry {
                        AppLog.write("deleting from iCloud failed, trying again in 5 minutes (\(deletionRetries)/3)")
                        Task { [weak self] in
                            try? await Task.sleep(nanoseconds: 300 * 1_000_000_000)
                            self?.runSerialized { await self?.autoDeletePass() }
                        }
                    } else if d.bool(forKey: Prefs.notifyOnError) {
                        notify("Deleting from iCloud failed", String(result.output.suffix(200)))
                    }
                    return  // keep the files: they are the only copy left
                }
            }
        }
        if wantDisk {
            let ready = items.filter { !wantICloud || deletedFromICloud.contains($0.id) }
            let result = Deletion.moveToTrash(ready)
            AppLog.write("moved \(result.moved) file(s) to the Trash. \(result.failures.joined(separator: "; "))")
            recordEvents(.trashedDisk, result.items)
            if result.moved > 0 { summary.append("\(result.moved) moved to the Trash") }
        }
        pendingDeletion = []
        lastPendingSignature = ""
        if !summary.isEmpty {
            deletionStatus = summary.joined(separator: ", ") + " at " + Date().formatted(date: .omitted, time: .shortened)
        }
    }

    // MARK: - What was deleted in iCloud: remove it from the disk and from Photos

    private static func loadMirrored() -> Set<String> {
        guard let data = try? Data(contentsOf: supportFile("mirrored-from-icloud.json")),
              let paths = try? JSONDecoder().decode([String].self, from: data) else { return [] }
        return Set(paths)
    }

    private func saveMirrored() {
        if let data = try? JSONEncoder().encode(mirroredPaths.sorted()) {
            try? data.write(to: AppModel.supportFile("mirrored-from-icloud.json"))
        }
    }

    /// Runs after every sync pass. Photos you deleted in iCloud (they are in its "Recently Deleted") are
    /// removed from the disk (moved to the Trash) and/or from Photos (macOS asks you to confirm that),
    /// depending on the two switches in Settings. Above the limit it asks first.
    private func mirrorPass() async {
        let d = UserDefaults.standard
        guard d.bool(forKey: Prefs.mirrorDisk) || d.bool(forKey: Prefs.mirrorPhotos), !mirroring else { return }
        mirroring = true
        defer { mirroring = false }

        let found = await Deletion.findDeletedInICloud()
        guard found.ok else {
            AppLog.write("problem: checking what was deleted in iCloud failed. \(found.output.suffix(300))")
            return
        }
        mirroredPaths.formIntersection(found.items.map(\.path))  // forget files that are gone
        let work = found.items.filter { !mirroredPaths.contains($0.path) }
        let photoCount = work.filter { !isSidecar($0.path) }.count
        guard photoCount > 0 else { pendingMirror = []; return }

        if d.bool(forKey: Prefs.confirmLargeDeletes), photoCount > d.integer(forKey: Prefs.confirmThreshold) {
            askToConfirmMirror(work, photoCount: photoCount)
        } else {
            await performMirror(work)
        }
    }

    private func mirrorTargets() -> String {
        let d = UserDefaults.standard
        var targets: [String] = []
        if d.bool(forKey: Prefs.mirrorPhotos) { targets.append("Photos") }
        if d.bool(forKey: Prefs.mirrorDisk) { targets.append("the disk (to the Trash)") }
        return targets.joined(separator: " and ")
    }

    private func askToConfirmMirror(_ items: [TrashCandidate], photoCount: Int) {
        pendingMirror = items
        let signature = items.map(\.path).sorted().joined(separator: ",")
        guard signature != lastMirrorSignature else { return }  // already asked about exactly these
        lastMirrorSignature = signature
        AppLog.write("waiting for confirmation: \(photoCount) photo(s) deleted in iCloud")
        notify(
            "Remove \(photoCount) photos?",
            "\(photoCount) photos were deleted in iCloud. They would be removed from \(mirrorTargets()). "
                + "That is more than your limit of \(UserDefaults.standard.integer(forKey: Prefs.confirmThreshold)), so please confirm.",
            category: "CONFIRM_MIRROR")
    }

    /// The panel row: a dialog instead of the notification buttons.
    func confirmMirrorInteractively() {
        let count = pendingMirror.filter { !isSidecar($0.path) }.count
        let alert = NSAlert()
        alert.messageText = "Remove \(count) photos?"
        alert.informativeText = "These photos were deleted in iCloud. They will be removed from \(mirrorTargets()). "
            + "Photos asks for its own confirmation, and deleted photos stay in Recently Deleted there."
        alert.addButton(withTitle: "Remove")
        alert.addButton(withTitle: "Cancel")
        NSApp.activate(ignoringOtherApps: true)
        if alert.runModal() == .alertFirstButtonReturn { runSerialized { await self.confirmPendingMirror() } }
    }

    /// The user agreed: look again, because iCloud may have changed, and act on what is still deleted.
    private func confirmPendingMirror() async {
        guard !mirroring else { return }
        mirroring = true
        defer { mirroring = false }
        let wanted = Set(pendingMirror.map(\.path))
        let found = await Deletion.findDeletedInICloud()
        guard found.ok else { return }
        await performMirror(found.items.filter { wanted.contains($0.path) })
    }

    private func performMirror(_ items: [TrashCandidate]) async {
        let d = UserDefaults.standard
        var summary: [String] = []

        if d.bool(forKey: Prefs.mirrorPhotos) {
            mirrorStatus = "Removing from Photos…"
            switch await PhotosDelete.delete(items) {
            case .deleted(let count, let notInPhotos, let deleted):
                AppLog.write("deleted \(count) photo(s) from Photos (\(notInPhotos) were not in Photos)")
                recordEvents(.deletedPhotos, deleted)
                if count > 0 { summary.append("\(count) deleted from Photos") }
            case .cancelled:
                AppLog.write("deleting from Photos was cancelled in the system dialog")
                summary.append("Photos: cancelled")
            case .denied:
                AppLog.write("problem: Photos Sync is not allowed to change the Photos library")
                if d.bool(forKey: Prefs.notifyOnError) {
                    notify("Photos Sync cannot delete from Photos",
                           "Allow it in System Settings, Privacy & Security, Photos.")
                }
                mirrorStatus = "Not allowed to delete from Photos."
                mirroredPaths.formUnion(items.map(\.path))  // do not ask again every hour
                saveMirrored()
                return
            case .failed(let message):
                AppLog.write("problem: deleting from Photos failed. \(message)")
                mirrorStatus = "Deleting from Photos failed, see the log."
                return  // not marked as done: tried again next time
            }
        }
        if d.bool(forKey: Prefs.mirrorDisk) {
            let result = Deletion.moveToTrash(items)
            AppLog.write("moved \(result.moved) file(s) to the Trash. \(result.failures.joined(separator: "; "))")
            recordEvents(.trashedDisk, result.items)
            if result.moved > 0 { summary.append("\(result.moved) moved to the Trash") }
        }
        mirroredPaths.formUnion(items.map(\.path))
        saveMirrored()
        pendingMirror = []
        lastMirrorSignature = ""
        if !summary.isEmpty {
            mirrorStatus = summary.joined(separator: ", ") + " at " + Date().formatted(date: .omitted, time: .shortened)
        }
    }

    // MARK: - Photos you add to Photos yourself: save a copy to the download folder

    private var exportTokenURL: URL { AppModel.supportFile("photos-change-token.data") }

    /// Called when the switch is turned on: only photos added from now on are saved.
    func resetExportBaseline() {
        try? FileManager.default.removeItem(at: exportTokenURL)
        exportStatus = "Watching for new photos in Photos from now on."
        runSerialized { await self.exportPass() }
    }

    private func exportPass() async {
        let d = UserDefaults.standard
        guard d.bool(forKey: Prefs.exportNewToDisk), !exporting else { return }
        exporting = true
        defer { exporting = false }
        let directory = d.string(forKey: Prefs.directory) ?? ""
        let outcome = await PhotosExport.run(directory: directory,
                                             folderStructure: d.string(forKey: Prefs.folderStructure) ?? "{:%Y/%m/%d}",
                                             tokenURL: exportTokenURL)
        switch outcome {
        case .baselineSet:
            exportStatus = "Watching for new photos in Photos from now on."
        case .saved(let items, let skipped):
            guard !items.isEmpty else { return }
            recordEvents(.savedFromPhotos, items)
            // they come from Photos: they must not be imported into Photos again
            importedPaths.formUnion(items.map(\.path))
            saveImported()
            exportFailureReset()
            AppLog.write("saved \(items.count) file(s) from Photos to the download folder (\(skipped) came from it)")
            exportStatus = "Saved \(items.count) file(s) from Photos at " + Date().formatted(date: .omitted, time: .shortened)
        case .denied:
            AppLog.write("problem: Photos Sync is not allowed to read the Photos library")
            exportStatus = "Not allowed to read Photos."
            if !exportDeniedNotified, d.bool(forKey: Prefs.notifyOnError) {
                exportDeniedNotified = true
                notify("Photos Sync cannot read Photos", "Allow it in System Settings, Privacy & Security, Photos.")
            }
        case .failed(let message):
            AppLog.write("problem: \(message)")
            exportStatus = "Saving from Photos failed, see the log."
        }
    }

    private func exportFailureReset() { exportDeniedNotified = false }

    // MARK: - Import into Apple Photos

    private static func supportFile(_ name: String) -> URL {
        let dir = dataHome().appendingPathComponent("Library/Application Support/icloudpd-menubar", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent(name)
    }

    private static var importedStoreURL: URL { supportFile("imported.json") }

    /// The list of synced files survives restarts of the app and of icloudpd.
    private static func loadActivity() -> [ActivityFile] {
        guard let data = try? Data(contentsOf: supportFile("activity.json")),
              let files = try? JSONDecoder().decode([ActivityFile].self, from: data) else { return [] }
        return files
    }

    private func saveActivity() {
        if let data = try? JSONEncoder().encode(activity) {
            try? data.write(to: AppModel.supportFile("activity.json"))
        }
    }

    private static func loadImported() -> Set<String> {
        guard let data = try? Data(contentsOf: importedStoreURL),
              let paths = try? JSONDecoder().decode([String].self, from: data) else { return [] }
        return Set(paths)
    }

    private func saveImported() {
        if let data = try? JSONEncoder().encode(importedPaths.sorted()) {
            try? data.write(to: AppModel.importedStoreURL)
        }
    }

    /// Files in the download folder that were not imported into Photos yet.
    func notImportedFiles() -> [String] {
        let root = UserDefaults.standard.string(forKey: Prefs.directory) ?? ""
        guard let walker = FileManager.default.enumerator(at: URL(fileURLWithPath: root),
                                                          includingPropertiesForKeys: [.isRegularFileKey]) else { return [] }
        var paths: [String] = []
        for case let url as URL in walker where PhotosImport.fileExtensions.contains(url.pathExtension.lowercased()) {
            if !importedPaths.contains(url.path) { paths.append(url.path) }
        }
        return paths.sorted()
    }

    /// Imports everything downloaded so far that is not in Photos yet (asked for explicitly by the user).
    func importExistingFiles() {
        enqueueImport(notImportedFiles(), force: true)
    }

    private func enqueueImport(_ paths: [String], force: Bool = false) {
        guard force || UserDefaults.standard.bool(forKey: Prefs.autoImportToPhotos) else { return }
        let queued = Set(importQueue)
        importQueue += paths.filter { !importedPaths.contains($0) && !queued.contains($0) }
        Task { await drainImportQueue() }
    }

    private func drainImportQueue() async {
        guard !importing else { return }
        importing = true
        defer { importing = false }
        var imported = 0
        while !importQueue.isEmpty {
            let batch = Array(importQueue.prefix(25))
            importQueue.removeFirst(batch.count)
            let existing = batch.filter { FileManager.default.fileExists(atPath: $0) }
            importStatus = "Importing \(existing.count) file(s) into Photos…"
            let result = await PhotosImport.run(paths: existing)
            if result.ok {
                importedPaths.formUnion(batch)
                saveImported()
                imported += existing.count
                importFailureNotified = false
                AppLog.write("imported \(existing.count) file(s) into Photos")
            } else {
                importQueue.insert(contentsOf: batch, at: 0)
                importStatus = "Import into Photos failed: \(result.message)"
                AppLog.write("problem: import into Photos failed. \(result.message)")
                if !importFailureNotified, UserDefaults.standard.bool(forKey: Prefs.notifyOnError) {
                    importFailureNotified = true
                    notify("Import into Photos failed", result.message)
                }
                return
            }
        }
        if imported > 0 {
            importStatus = "Imported \(imported) file(s) into Photos, last at "
                + Date().formatted(date: .omitted, time: .shortened)
        }
    }

    /// Keeps the history across icloudpd restarts: new entries first, no duplicates, at most 200.
    private func merge(_ files: [ActivityFile]) {
        let known = Set(activity.map(\.id))
        let fresh = files.filter { !known.contains($0.id) }
        enqueueImport(fresh.reversed().map(\.path))  // oldest first
        var seen = Set<String>()
        activity = (files + activity)
            .sorted { $0.time > $1.time }
            .filter { seen.insert($0.id).inserted }
            .prefix(200)
            .map { $0 }
        saveActivity()
    }

    private func set(_ new: State) {
        guard new != state else { return }
        let old = state
        state = new
        switch new {
        case .recovering, .error:
            switch old {
            case .recovering, .error: break
            default: problemCleared = false
            }
        default: break
        }
        if case .waiting = new {
            if case .waiting = old {} else {  // a sync pass just finished
                runSerialized { await self.autoDeletePass() }
                runSerialized { await self.mirrorPass() }
                runSerialized { await self.exportPass() }
            }
        }
        switch new {
        case .idle, .syncing, .waiting:
            // the sync works, so the Apple ID is linked
            let user = (UserDefaults.standard.string(forKey: Prefs.username) ?? "").trimmingCharacters(in: .whitespaces)
            if !user.isEmpty, UserDefaults.standard.string(forKey: Prefs.linkedAccount) != user {
                UserDefaults.standard.set(user, forKey: Prefs.linkedAccount)
            }
        case .needsMFA where old != .needsMFA && UserDefaults.standard.bool(forKey: Prefs.notifyOnInput):
            notify("iCloud needs a code", "Open the menu and choose “Enter code…”.")
        case .needsPassword where old != .needsPassword && UserDefaults.standard.bool(forKey: Prefs.notifyOnInput):
            notify("iCloud needs a password", "Open the menu and choose “Enter password…”.")
        default: break
        }
    }

    private func notify(_ title: String, _ body: String, category: String? = nil) {
        guard Bundle.main.bundleIdentifier != nil else { return }
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        if let category { content.categoryIdentifier = category }
        UNUserNotificationCenter.current().add(
            UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil))
    }
}
