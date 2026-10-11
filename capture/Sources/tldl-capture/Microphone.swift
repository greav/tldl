import CoreAudio
import Foundation

/// The microphone the mic track is taken from, as the capture program reports it.
struct Microphone {
    /// What the system calls the device.
    let name: String
    /// How the device is connected.
    let transport: String
    /// The rate the device delivers audio at, in hertz.
    let sampleRate: Int

    /// The `microphone` event of the contract. The name is percent-encoded, since a value holds no spaces.
    var event: String {
        let plain = CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._")
        let encodedName = name.addingPercentEncoding(withAllowedCharacters: plain) ?? "unknown"
        return "microphone name=\(encodedName) transport=\(transport) sample-rate=\(sampleRate)"
    }
}

/// The device to take the mic track from: the microphone the system calls `name`, or the system default
/// microphone at this moment when no name is given.
///
/// The device is only looked up. Which microphone is the system's default is never changed, so other
/// programs keep the one the system gave them.
func microphone(named name: String?) throws -> AudioDeviceID {
    guard let name else {
        return try defaultMicrophone()
    }
    let microphones = try devicesWithInput().map { (device: $0, name: deviceName($0)) }
    if let named = microphones.first(where: { $0.name == name }) {
        return named.device
    }
    let names = microphones.compactMap(\.name)
    let there = names.isEmpty ? "there are no microphones" : "the microphones are \(names.joined(separator: ", "))"
    throw CaptureError(reason: "there is no microphone named \(name); \(there)")
}

/// Every device of the system that sound can be taken from.
private func devicesWithInput() throws -> [AudioDeviceID] {
    let system = AudioObjectID(kAudioObjectSystemObject)
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioHardwarePropertyDevices,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain
    )
    var size = UInt32(0)
    try check(AudioObjectGetPropertyDataSize(system, &address, 0, nil, &size), "list the microphones")
    var devices = [AudioDeviceID](
        repeating: AudioDeviceID(kAudioObjectUnknown),
        count: Int(size) / MemoryLayout<AudioDeviceID>.size
    )
    try check(AudioObjectGetPropertyData(system, &address, 0, nil, &size, &devices), "list the microphones")
    // The list may have shrunk between the two calls.
    devices.removeLast(devices.count - Int(size) / MemoryLayout<AudioDeviceID>.size)
    return devices.filter(hasInput)
}

/// Whether `device` has a stream that delivers sound, as a microphone does and a loudspeaker does not.
private func hasInput(_ device: AudioDeviceID) -> Bool {
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioDevicePropertyStreams,
        mScope: kAudioObjectPropertyScopeInput,
        mElement: kAudioObjectPropertyElementMain
    )
    var size = UInt32(0)
    return AudioObjectGetPropertyDataSize(device, &address, 0, nil, &size) == noErr && size > 0
}

/// What the system calls `device`, when it says.
private func deviceName(_ device: AudioDeviceID) -> String? {
    let name = try? readProperty(
        kAudioObjectPropertyName,
        of: device,
        startingFrom: Unmanaged<CFString>?.none,
        to: "read the device's name"
    )
    return (name ?? nil).map { $0.takeRetainedValue() as String }
}

/// What the system says about the microphone `device`.
func describeMicrophone(_ device: AudioDeviceID) throws -> Microphone {
    let transport = try? readProperty(
        kAudioDevicePropertyTransportType,
        of: device,
        startingFrom: UInt32(0),
        to: "read how the microphone is connected"
    )
    let sampleRate = try readProperty(
        kAudioDevicePropertyNominalSampleRate,
        of: device,
        startingFrom: Float64(0),
        to: "read the microphone's sample rate"
    )
    return Microphone(
        name: deviceName(device) ?? "unknown",
        transport: transportWord(transport ?? 0),
        sampleRate: Int(sampleRate)
    )
}
