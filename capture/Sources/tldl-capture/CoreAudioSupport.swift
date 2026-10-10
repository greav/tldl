import CoreAudio
import Foundation

/// Why capture could not start or go on, in words fit for the user.
struct CaptureError: Error {
    let reason: String
}

/// Turns a Core Audio status into a `CaptureError` naming what was being done.
func check(_ status: OSStatus, _ action: String) throws {
    guard status == noErr else {
        throw CaptureError(reason: "could not \(action) (Core Audio error \(status))")
    }
}

/// Reads one fixed-size property of a Core Audio object.
func readProperty<Value>(
    _ selector: AudioObjectPropertySelector,
    of object: AudioObjectID,
    scope: AudioObjectPropertyScope = kAudioObjectPropertyScopeGlobal,
    startingFrom initial: Value,
    to action: String
) throws -> Value {
    var address = AudioObjectPropertyAddress(
        mSelector: selector,
        mScope: scope,
        mElement: kAudioObjectPropertyElementMain
    )
    var size = UInt32(MemoryLayout<Value>.size)
    var value = initial
    let status = withUnsafeMutableBytes(of: &value) { bytes in
        AudioObjectGetPropertyData(object, &address, 0, nil, &size, bytes.baseAddress!)
    }
    try check(status, action)
    return value
}

/// The system default microphone at this moment.
func defaultMicrophone() throws -> AudioDeviceID {
    let device = try readProperty(
        kAudioHardwarePropertyDefaultInputDevice,
        of: AudioObjectID(kAudioObjectSystemObject),
        startingFrom: AudioDeviceID(kAudioObjectUnknown),
        to: "find the default microphone"
    )
    guard device != kAudioObjectUnknown else {
        throw CaptureError(reason: "there is no default microphone")
    }
    return device
}

/// How a device is connected, as the contract words it, from its Core Audio transport type.
func transportWord(_ transport: UInt32) -> String {
    switch transport {
    case kAudioDeviceTransportTypeBuiltIn: "built-in"
    case kAudioDeviceTransportTypeBluetooth, kAudioDeviceTransportTypeBluetoothLE: "bluetooth"
    case kAudioDeviceTransportTypeUSB: "usb"
    case kAudioDeviceTransportTypeHDMI: "hdmi"
    case kAudioDeviceTransportTypeDisplayPort: "displayport"
    case kAudioDeviceTransportTypeAirPlay: "airplay"
    case kAudioDeviceTransportTypeVirtual, kAudioDeviceTransportTypeAggregate: "virtual"
    default: "other"
    }
}
