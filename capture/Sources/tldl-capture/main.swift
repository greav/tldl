// The capture program: writes the mic track and the system track to two given paths until the stop signal.
//
// Its arguments, stop signal, output and failure behaviour are the capture program contract, described
// in one place: the docstring of `src/tldl/capture.py`. Change the contract there first.

import CoreAudio
import Foundation

/// Reports one event of the contract on standard output.
func report(_ event: String) {
    print(event)
    fflush(stdout)
}

func fail(_ reason: String, status: Int32 = 1) -> Never {
    FileHandle.standardError.write(Data("tldl-capture: \(reason)\n".utf8))
    exit(status)
}

let arguments = CommandLine.arguments.dropFirst()
guard arguments.count == 2 else {
    fail("usage: tldl-capture <mic-track-path> <system-track-path>", status: 2)
}
let micTrackPath = arguments[arguments.startIndex]
let systemTrackPath = arguments[arguments.startIndex + 1]

// Taken over before any device starts, so a stop signal can never kill the program with files open.
let stopSignals = [SIGINT, SIGTERM, SIGHUP]
let stopSources = stopSignals.map { stopSignal -> DispatchSourceSignal in
    signal(stopSignal, SIG_IGN)
    return DispatchSource.makeSignalSource(signal: stopSignal, queue: .main)
}

do {
    let systemTap = try SystemTap()
    let micTrack = try TrackWriter(device: try defaultMicrophone(), path: micTrackPath)
    let systemTrack = try TrackWriter(device: systemTap.device, path: systemTrackPath)
    micTrack.onFirstAudio = { report("track-started track=mic host-time=\(String(format: "%.6f", $0))") }
    systemTrack.onFirstAudio = { report("track-started track=system host-time=\(String(format: "%.6f", $0))") }

    var stopping = false
    for source in stopSources {
        source.setEventHandler {
            guard !stopping else { return }
            stopping = true
            micTrack.stop()
            systemTrack.stop()
            systemTap.remove()
            exit(0)
        }
        source.resume()
    }

    try micTrack.start()
    try systemTrack.start()
    report("started")
    let outputRoute = currentOutputRoute()
    report("output-route route=\(outputRoute.route) transport=\(outputRoute.transport)")
} catch let error as CaptureError {
    fail(error.reason)
}

dispatchMain()
