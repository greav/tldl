import CoreAudio

/// What the computer is playing sound through, judged from the default output device.
struct OutputRoute {
    /// `speakers`, `headphones`, or `unknown` when the device does not tell.
    let route: String
    /// How the device is connected: the fact the verdict rests on.
    let transport: String
}

/// The output route at this moment.
///
/// Bluetooth is taken for a headset, and HDMI, DisplayPort and AirPlay for speakers. A built-in output
/// names its data source: `ispk` for the internal speakers and `hdpn` for the headphone jack. The public
/// headers define neither code; `ispk` is what a MacBook Pro reports on macOS 26, `hdpn` is the long-used
/// counterpart. USB can be either, so it stays unknown.
func currentOutputRoute() -> OutputRoute {
    guard
        let device = try? readProperty(
            kAudioHardwarePropertyDefaultOutputDevice,
            of: AudioObjectID(kAudioObjectSystemObject),
            startingFrom: AudioDeviceID(kAudioObjectUnknown),
            to: "find the default output device"
        ),
        let transport = try? readProperty(
            kAudioDevicePropertyTransportType,
            of: device,
            startingFrom: UInt32(0),
            to: "read how the output device is connected"
        )
    else {
        return OutputRoute(route: "unknown", transport: "other")
    }

    let route: String
    switch transport {
    case kAudioDeviceTransportTypeBuiltIn:
        let dataSource = try? readProperty(
            kAudioDevicePropertyDataSource,
            of: device,
            scope: kAudioObjectPropertyScopeOutput,
            startingFrom: UInt32(0),
            to: "read the output device's data source"
        )
        route =
            switch dataSource {
            case fourCharacterCode("ispk"): "speakers"
            case fourCharacterCode("hdpn"): "headphones"
            default: "unknown"
            }
    case kAudioDeviceTransportTypeBluetooth, kAudioDeviceTransportTypeBluetoothLE:
        route = "headphones"
    case kAudioDeviceTransportTypeHDMI, kAudioDeviceTransportTypeDisplayPort, kAudioDeviceTransportTypeAirPlay:
        route = "speakers"
    default:
        route = "unknown"
    }
    return OutputRoute(route: route, transport: transportWord(transport))
}

/// A Core Audio four-character code, such as a data source's, as the number it travels as.
private func fourCharacterCode(_ code: String) -> UInt32 {
    code.utf8.reduce(0) { $0 << 8 | UInt32($1) }
}
