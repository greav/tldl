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

/// What the system says about the microphone `device`.
func describeMicrophone(_ device: AudioDeviceID) throws -> Microphone {
    let name = try? readProperty(
        kAudioObjectPropertyName,
        of: device,
        startingFrom: Unmanaged<CFString>?.none,
        to: "read the microphone's name"
    )
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
        name: (name ?? nil).map { $0.takeRetainedValue() as String } ?? "unknown",
        transport: transportWord(transport ?? 0),
        sampleRate: Int(sampleRate)
    )
}
