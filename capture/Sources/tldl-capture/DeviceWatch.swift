import CoreAudio
import Foundation

/// Whether `device` is still part of the system. A device that was unplugged, switched off or carried
/// out of range is not, and cannot even be asked.
func isAlive(_ device: AudioDeviceID) -> Bool {
    let alive = try? readProperty(
        kAudioDevicePropertyDeviceIsAlive,
        of: device,
        startingFrom: UInt32(0),
        to: "ask whether the device is alive"
    )
    return alive != nil && alive != 0
}

/// Calls `handler` on the main queue when `device` is gone from the system.
///
/// Two things are listened to, because either may be the one that speaks: the device saying it is no
/// longer alive, and the system's list of devices changing. Both lead to the same question, so a change
/// to some other device does nothing. `handler` may be called more than once.
func whenDeviceDisappears(_ device: AudioDeviceID, _ handler: @escaping () -> Void) throws {
    let listener: AudioObjectPropertyListenerBlock = { _, _ in
        if !isAlive(device) {
            handler()
        }
    }
    let watched = [
        (AudioObjectID(device), kAudioDevicePropertyDeviceIsAlive),
        (AudioObjectID(kAudioObjectSystemObject), kAudioHardwarePropertyDevices),
    ]
    for (object, selector) in watched {
        var address = AudioObjectPropertyAddress(
            mSelector: selector,
            mScope: kAudioObjectPropertyScopeGlobal,
            mElement: kAudioObjectPropertyElementMain
        )
        try check(
            AudioObjectAddPropertyListenerBlock(object, &address, DispatchQueue.main, listener),
            "watch for the device going away"
        )
    }
}
