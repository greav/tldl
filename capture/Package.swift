// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "tldl-capture",
    // Core Audio process taps, which the system track is built on, start at macOS 14.2.
    platforms: [.macOS("14.2")],
    targets: [
        .executableTarget(name: "tldl-capture", path: "Sources/tldl-capture")
    ]
)
