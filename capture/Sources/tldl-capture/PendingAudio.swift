import os

/// Mono audio on its way from a device's audio thread to the queue that writes the Track's file.
///
/// The audio thread appends to one buffer; the writing queue swaps it for an empty one and takes the full
/// one away. The lock is held for one small copy or for the swap, never during file work, so the audio
/// thread never waits on the disk.
final class PendingAudio {
    private var filling: UnsafeMutablePointer<Float32>
    private var taken: UnsafeMutablePointer<Float32>
    private var count = 0
    private let capacity: Int
    private let lock = OSAllocatedUnfairLock()

    /// `capacity` is how many samples can wait between two calls of `take`.
    init(capacity: Int) {
        self.capacity = capacity
        filling = .allocate(capacity: capacity)
        taken = .allocate(capacity: capacity)
    }

    /// Adds samples to what is waiting. Samples that do not fit are dropped, which takes the writing
    /// queue standing still for as long as the capacity lasts.
    func append(_ samples: UnsafePointer<Float32>, count added: Int) {
        lock.lock()
        let fitting = min(added, capacity - count)
        (filling + count).update(from: samples, count: fitting)
        count += fitting
        lock.unlock()
    }

    /// Hands over everything waiting. The samples stay valid until the next call.
    func take() -> UnsafeMutableBufferPointer<Float32> {
        lock.lock()
        let samples = UnsafeMutableBufferPointer(start: filling, count: count)
        swap(&filling, &taken)
        count = 0
        lock.unlock()
        return samples
    }
}
