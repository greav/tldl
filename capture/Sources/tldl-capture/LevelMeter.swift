import Foundation
import os

/// The level of one Track: the loudest sample since it was last asked, as a fraction of full scale.
///
/// Fed from the device's audio thread and asked from the main queue. The audio thread never waits for
/// the lock: when the main queue holds it, the audio thread keeps what it heard and hands it over with
/// the next buffer.
final class LevelMeter {
    private let loudest = OSAllocatedUnfairLock(initialState: Float32(0))
    /// Heard but not yet handed over. Touched by the audio thread only.
    private var waiting: Float32 = 0

    /// Takes in the samples of one buffer. Runs on the device's audio thread.
    func hear(_ samples: UnsafePointer<Float32>, count: Int) {
        let heard = UnsafeBufferPointer(start: samples, count: count).reduce(waiting) { max($0, abs($1)) }
        let handedOver: Void? = loudest.withLockIfAvailable { $0 = max($0, heard) }
        waiting = handedOver == nil ? heard : 0
    }

    /// The level since the last call, from 0 to 1, and a fresh start for the next one.
    func take() -> Float32 {
        let level = loudest.withLock { loudest -> Float32 in
            defer { loudest = 0 }
            return loudest
        }
        return min(level, 1)
    }
}
