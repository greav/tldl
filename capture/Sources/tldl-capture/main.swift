// The capture program: writes the mic track and the system track to two given paths until the stop signal,
// taking the mic track from the microphone it was given the name of or from the system default microphone.
//
// Its arguments, stop signal, output and failure behaviour are the capture program contract, described
// in one place: the docstring of `src/tldl/capture.py`. Change the contract there first.

import CoreAudio
import Foundation

/// Reports one event of the contract on standard output. False when nobody is reading it any more.
@discardableResult
func report(_ event: String) -> Bool {
    print(event)
    return fflush(stdout) == 0
}

/// Ends the program over a mistake in how it was started, which the contract has no event for.
func fail(_ reason: String, status: Int32) -> Never {
    FileHandle.standardError.write(Data("tldl-capture: \(reason)\n".utf8))
    exit(status)
}

let arguments = CommandLine.arguments.dropFirst()
guard arguments.count == 2 || arguments.count == 3 else {
    fail("usage: tldl-capture <mic-track-path> <system-track-path> [<microphone-name>]", status: 2)
}
let micTrackPath = arguments[arguments.startIndex]
let systemTrackPath = arguments[arguments.startIndex + 1]
let microphoneName = arguments.count == 3 ? arguments[arguments.startIndex + 2] : nil

// Taken over before any device starts, so a stop signal can never kill the program with files open.
let stopSignals = [SIGINT, SIGTERM, SIGHUP]
let stopSources = stopSignals.map { stopSignal -> DispatchSourceSignal in
    signal(stopSignal, SIG_IGN)
    return DispatchSource.makeSignalSource(signal: stopSignal, queue: .main)
}
// Reporting to a reader that is gone would kill the program in the same way.
signal(SIGPIPE, SIG_IGN)

let levelInterval = 0.1
let levelTimer = DispatchSource.makeTimerSource(queue: .main)

/// What keeps the Mac from idle sleep while capture runs. The system lets go of it when the program
/// exits, however it exits.
var awake: NSObjectProtocol?

func written(_ level: Float32) -> String {
    String(format: "%.4f", level)
}

do {
    // Before anything is created: a microphone that is not there leaves no file and no tap behind, and
    // the tap's own device is not yet among the devices that have input.
    let microphone = try microphone(named: microphoneName)
    let microphoneDescription = try describeMicrophone(microphone)
    let systemTap = try SystemTap()
    let micTrack = try TrackWriter(device: microphone, path: micTrackPath)
    let systemTrack = try TrackWriter(device: systemTap.device, path: systemTrackPath)
    micTrack.onFirstAudio = { report("track-started track=mic host-time=\(String(format: "%.6f", $0))") }
    systemTrack.onFirstAudio = { report("track-started track=system host-time=\(String(format: "%.6f", $0))") }

    var stopping = false
    /// Closes both Tracks and ends the program: as asked, or as a failure when given the reason.
    func stop(failure: String? = nil) {
        guard !stopping else { return }
        stopping = true
        levelTimer.cancel()
        micTrack.stop()
        systemTrack.stop()
        systemTap.remove()
        if let failure {
            report("failed \(failure)")
            exit(1)
        }
        exit(0)
    }
    for source in stopSources {
        source.setEventHandler { stop() }
        source.resume()
    }
    try whenDeviceDisappears(microphone) { stop(failure: "the microphone disappeared") }
    micTrack.onWriteFailure = { stop(failure: $0) }
    systemTrack.onWriteFailure = { stop(failure: $0) }

    try micTrack.start()
    try systemTrack.start()
    awake = ProcessInfo.processInfo.beginActivity(
        options: .idleSystemSleepDisabled,
        reason: "tldl is recording"
    )
    report("started")
    let outputRoute = currentOutputRoute()
    report("output-route route=\(outputRoute.route) transport=\(outputRoute.transport)")
    report(microphoneDescription.event)

    levelTimer.schedule(deadline: .now() + levelInterval, repeating: levelInterval)
    levelTimer.setEventHandler {
        let mic = written(micTrack.level.take())
        let system = written(systemTrack.level.take())
        // With nobody reading, nobody can send the stop signal either.
        if !report("level mic=\(mic) system=\(system)") {
            stop()
        }
    }
    levelTimer.resume()
} catch let error as CaptureError {
    report("failed \(error.reason)")
    exit(1)
}

dispatchMain()
