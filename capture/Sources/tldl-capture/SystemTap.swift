import CoreAudio
import Foundation

/// Everything the computer plays, offered as an input device the system track can be read from.
///
/// A Core Audio process tap of the whole system, mixed down to mono, wrapped in a private aggregate device
/// that holds nothing but the tap. No output device is part of it, so it does not depend on where the
/// sound is playing.
final class SystemTap {
    /// The device to read the system track from.
    private(set) var device = AudioDeviceID(kAudioObjectUnknown)
    private var tap = AudioObjectID(kAudioObjectUnknown)

    init() throws {
        // Excluding no process makes the tap global: every process that plays sound is in it.
        let description = CATapDescription(monoGlobalTapButExcludeProcesses: [])
        description.uuid = UUID()
        description.name = "tldl system track"
        description.isPrivate = true
        description.muteBehavior = .unmuted
        try check(AudioHardwareCreateProcessTap(description, &tap), "tap the system's sound")

        let aggregate: [String: Any] = [
            kAudioAggregateDeviceNameKey: "tldl system track",
            kAudioAggregateDeviceUIDKey: UUID().uuidString,
            kAudioAggregateDeviceIsPrivateKey: true,
            kAudioAggregateDeviceIsStackedKey: false,
            // Off, so the device runs from the moment it is started and delivers silence while nothing
            // plays. With auto-start on it delivers nothing until some process plays sound, and nothing
            // again in every pause, which would squeeze the silences out of the system track.
            kAudioAggregateDeviceTapAutoStartKey: false,
            kAudioAggregateDeviceTapListKey: [
                [
                    kAudioSubTapUIDKey: description.uuid.uuidString,
                    kAudioSubTapDriftCompensationKey: true,
                ]
            ],
        ]
        do {
            try check(
                AudioHardwareCreateAggregateDevice(aggregate as CFDictionary, &device),
                "create the device for the system track"
            )
        } catch {
            remove()
            throw error
        }
    }

    /// Takes the tap and its device out of the system.
    func remove() {
        if device != kAudioObjectUnknown {
            AudioHardwareDestroyAggregateDevice(device)
            device = AudioDeviceID(kAudioObjectUnknown)
        }
        if tap != kAudioObjectUnknown {
            AudioHardwareDestroyProcessTap(tap)
            tap = AudioObjectID(kAudioObjectUnknown)
        }
    }
}
