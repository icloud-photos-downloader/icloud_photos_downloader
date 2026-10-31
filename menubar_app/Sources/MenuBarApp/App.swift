import AppKit
import MenuBarCore
import SwiftUI

@main
struct ICloudpdMenuBarApp: App {
    @StateObject private var model = AppModel()

    var body: some Scene {
        MenuBarExtra {
            PanelView().environmentObject(model)
        } label: {
            Image(systemName: model.iconName).modifier(DocLauncher())
        }
        .menuBarExtraStyle(.window)

        Window("Photos Sync Settings", id: "settings") { SettingsView().environmentObject(model) }
        Window("iCloud deletions", id: "review") { DeleteReviewView().environmentObject(model) }
    }
}

/// Opens the window asked for by PHOTOSSYNC_DOC (documentation screenshots only).
struct DocLauncher: ViewModifier {
    @Environment(\.openWindow) private var openWindow

    func body(content: Content) -> some View {
        content.onAppear {
            let doc = DocMode.value
            if doc.hasPrefix("settings") { openWindow(id: "settings") }
            if doc == "review" { openWindow(id: "review") }
            if !doc.isEmpty { NSApp.activate(ignoringOtherApps: true) }
        }
    }
}

/// Height of the main panel, so the activity view can have exactly the same height. The window then
/// never changes size when switching, which made it render oddly.
@MainActor
final class PanelLayout: ObservableObject {
    @Published var mainHeight: CGFloat = 340
}

/// Panel under the menu bar icon: status, a OneDrive-style activity row, main actions, and a gear for Settings.
struct PanelView: View {
    @EnvironmentObject var model: AppModel
    @Environment(\.openWindow) private var openWindow
    @StateObject private var layout = PanelLayout()

    var body: some View {
        Group {
            if model.showActivity {
                ActivityView().frame(height: layout.mainHeight, alignment: .top)
            } else {
                mainPanel.background(
                    GeometryReader { geometry in
                        Color.clear
                            .onAppear { layout.mainHeight = geometry.size.height }
                            .onChange(of: geometry.size.height) { layout.mainHeight = $0 }
                    })
            }
        }
        .frame(width: 320)
        // open on the main view every time
        .onReceive(NotificationCenter.default.publisher(for: NSWindow.didBecomeKeyNotification)) { _ in
            if DocMode.value != "activity" { model.showActivity = false }
        }
    }

    private var mainPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            PanelRow(icon: { Image(systemName: model.iconName).font(.system(size: 15)) }) {
                Text(model.statusLine).font(.headline).lineLimit(1)
            }

            Button { model.showActivity = true } label: {
                PanelRow(icon: { SyncBadge(syncing: model.isSyncing, size: PanelMetrics.icon) }) {
                    Text(model.activitySummary)
                } trailing: {
                    Image(systemName: "chevron.right").foregroundStyle(.secondary)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            Divider()

            if model.hasProblem {
                PanelButton(title: "View log for details", icon: "doc.text.magnifyingglass") { model.openLog() }
            }
            if !model.pendingDeletion.isEmpty {
                PanelButton(title: "\(model.pendingDeletion.count) photos wait for deletion…",
                            icon: "exclamationmark.triangle") { show("review") }
            }
            if !model.pendingMirror.isEmpty {
                PanelButton(title: "\(model.pendingMirror.filter { !isSidecar($0.path) }.count) iCloud deletions wait…",
                            icon: "exclamationmark.triangle") { model.confirmMirrorInteractively() }
            }
            if model.needsInput {
                PanelButton(title: model.state == .needsMFA ? "Enter code…" : "Enter password…",
                            icon: "key") { model.openWebUI() }
            }
            PanelButton(title: "Sync now", icon: "arrow.clockwise", disabled: !model.isRunning) { model.syncNow() }
            if model.isRunning {
                PanelButton(title: "Stop syncing", icon: "pause.circle") { model.stopWatching() }
            } else {
                PanelButton(title: "Start syncing", icon: "play.circle") { model.startWatching() }
            }
            PanelButton(title: "Open Photos", icon: "photo.on.rectangle") { model.openPhotosApp() }
            PanelButton(title: "Review iCloud deletions…", icon: "trash") { show("review") }

            Divider()

            HStack {
                Spacer()
                Button { show("settings") } label: { Image(systemName: "gearshape") }
                    .buttonStyle(.bordered).clipShape(Circle()).help("Settings")
                Menu {
                    Button("Open web UI") { model.openWebUI() }.disabled(!model.isRunning)
                    Button("Open log") { model.openLog() }
                    Divider()
                    Button("Quit") {
                        model.stopWatching()
                        NSApplication.shared.terminate(nil)
                    }
                } label: { Image(systemName: "ellipsis") }
                    .menuStyle(.button).menuIndicator(.hidden).fixedSize()
            }
        }
        .padding(14)
    }

    private func show(_ id: String) {
        openWindow(id: id)
        NSApp.activate(ignoringOtherApps: true)
    }
}

enum PanelMetrics {
    /// every row of the panel puts its icon in a column of this width, so icons and text line up
    static let icon: CGFloat = 20
}

struct PanelRow<Icon: View, Content: View, Trailing: View>: View {
    let icon: Icon
    let content: Content
    let trailing: Trailing

    init(@ViewBuilder icon: () -> Icon, @ViewBuilder content: () -> Content,
         @ViewBuilder trailing: () -> Trailing) {
        self.icon = icon()
        self.content = content()
        self.trailing = trailing()
    }

    var body: some View {
        HStack(spacing: 10) {
            icon.frame(width: PanelMetrics.icon, height: PanelMetrics.icon)
            content
            Spacer(minLength: 0)
            trailing
        }
    }
}

extension PanelRow where Trailing == EmptyView {
    init(@ViewBuilder icon: () -> Icon, @ViewBuilder content: () -> Content) {
        self.init(icon: icon, content: content, trailing: { EmptyView() })
    }
}

private struct PanelButton: View {
    let title: String
    let icon: String
    var disabled = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            PanelRow(icon: { Image(systemName: icon).font(.system(size: 14)) }) { Text(title) }
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(disabled)
        .opacity(disabled ? 0.4 : 1)
    }
}
