// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "ICloudpdMenuBar",
    platforms: [.macOS(.v13)],
    targets: [
        // Photos trash detection and the safeguards around deleting from iCloud (no UI, testable from a terminal)
        .target(name: "MenuBarCore"),
        // `swift run candidates-cli` prints what the app would offer to delete
        .executableTarget(name: "candidates-cli", dependencies: ["MenuBarCore"]),
        .executableTarget(name: "MenuBarApp", dependencies: ["MenuBarCore"]),
    ]
)
