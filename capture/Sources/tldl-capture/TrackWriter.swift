import AudioToolbox
import CoreAudio
import Foundation

/// Writes what one input device delivers to a file: one Track, as mono 16-bit FLAC at the device's
/// sample rate.
///
/// The audio reaches the disk while the device runs, about ten times a second, and the file can be decoded
/// at every moment: if the program dies, the Track is there up to about that moment.
final class TrackWriter {
    private let device: AudioDeviceID
    private let path: String
    private var file: ExtAudioFileRef?
    private var ioProc: AudioDeviceIOProcID?

    /// Scratch space for the mono mix, allocated up front because the audio thread must not allocate.
    private let mix: UnsafeMutablePointer<Float32>
    private static let mixCapacity = 4096

    /// The mono mix on its way from the audio thread to `writing`.
    private let pending: PendingAudio
    /// Where all work on the file happens, so that neither the encoder nor the disk holds up the audio
    /// thread.
    private let writing = DispatchQueue(label: "tldl-capture.track-writer")
    private var writeTimer: DispatchSourceTimer?
    private static let writeInterval = DispatchTimeInterval.milliseconds(100)

    /// A second handle on the file, for what `ExtAudioFile` does not do: see `describeStream` and
    /// `writePending`.
    private var descriptor: Int32 = -1
    private var writesSinceSync = 0
    private static let writesPerSync = 10

    /// Called once, on the main queue, when the Track's first audio has arrived: with the moment that
    /// audio was captured, in seconds on the host clock.
    var onFirstAudio: ((Double) -> Void)?
    /// Set on the audio thread before the first audio goes into `pending`, read on `writing` after it
    /// came out.
    private var firstAudioHostTime: UInt64 = 0
    private var firstAudioReported = false

    init(device: AudioDeviceID, path: String) throws {
        self.device = device
        self.path = path
        mix = .allocate(capacity: Self.mixCapacity)

        let sampleRate = try readProperty(
            kAudioDevicePropertyNominalSampleRate,
            of: device,
            startingFrom: Float64(0),
            to: "read the sample rate for \(path)"
        )
        // Room for ten seconds of audio, a hundred times what normally waits between two writes.
        pending = PendingAudio(capacity: Int(sampleRate) * 10)

        var fileFormat = AudioStreamBasicDescription()
        fileFormat.mSampleRate = sampleRate
        fileFormat.mFormatID = kAudioFormatFLAC
        fileFormat.mFormatFlags = kAppleLosslessFormatFlag_16BitSourceData
        fileFormat.mChannelsPerFrame = 1
        try check(
            ExtAudioFileCreateWithURL(
                URL(fileURLWithPath: path) as CFURL,
                kAudioFileFLACType,
                &fileFormat,
                nil,
                AudioFileFlags.eraseFile.rawValue,
                &file
            ),
            "create \(path)"
        )

        // What the file is handed: the mono mix, in the 32-bit float samples Core Audio devices deliver.
        var mixFormat = AudioStreamBasicDescription(
            mSampleRate: sampleRate,
            mFormatID: kAudioFormatLinearPCM,
            mFormatFlags: kAudioFormatFlagsNativeFloatPacked,
            mBytesPerPacket: UInt32(MemoryLayout<Float32>.size),
            mFramesPerPacket: 1,
            mBytesPerFrame: UInt32(MemoryLayout<Float32>.size),
            mChannelsPerFrame: 1,
            mBitsPerChannel: 32,
            mReserved: 0
        )
        try check(
            ExtAudioFileSetProperty(
                file!,
                kExtAudioFileProperty_ClientDataFormat,
                UInt32(MemoryLayout<AudioStreamBasicDescription>.size),
                &mixFormat
            ),
            "set up the encoder for \(path)"
        )
        try describeStream(sampleRate: sampleRate)

        try check(
            AudioDeviceCreateIOProcIDWithBlock(&ioProc, device, nil) { [unowned self] _, input, inputTime, _, _ in
                let time = inputTime.pointee
                self.write(
                    input,
                    capturedAt: time.mFlags.contains(.hostTimeValid) ? time.mHostTime : mach_absolute_time()
                )
            },
            "listen to the device for \(path)"
        )
    }

    func start() throws {
        let timer = DispatchSource.makeTimerSource(queue: writing)
        timer.schedule(deadline: .now() + Self.writeInterval, repeating: Self.writeInterval)
        timer.setEventHandler { [unowned self] in self.writePending() }
        timer.resume()
        writeTimer = timer
        try check(AudioDeviceStart(device, ioProc), "start the device")
    }

    /// Stops listening, writes what is still waiting and closes the file.
    func stop() {
        if let ioProc {
            AudioDeviceStop(device, ioProc)
            AudioDeviceDestroyIOProcID(device, ioProc)
            self.ioProc = nil
        }
        writeTimer?.cancel()
        writing.sync {
            writePending()
            if let file {
                // Replaces the stream description with the complete one.
                ExtAudioFileDispose(file)
                self.file = nil
            }
            if descriptor >= 0 {
                close(descriptor)
                descriptor = -1
            }
        }
    }

    /// Writes the FLAC stream description into the new file, so that the file can be decoded from now on.
    ///
    /// `ExtAudioFile` puts the encoded audio on disk as it goes, but leaves the stream description
    /// (STREAMINFO, which a decoder reads first) zeroed until the file is disposed: a capture program
    /// killed mid-capture left files that nothing would open. So the description goes in here, with the
    /// length unknown and no checksum, which the format allows. Disposing the file replaces it.
    private func describeStream(sampleRate: Float64) throws {
        var encoded = AudioStreamBasicDescription()
        var size = UInt32(MemoryLayout<AudioStreamBasicDescription>.size)
        try check(
            ExtAudioFileGetProperty(file!, kExtAudioFileProperty_FileDataFormat, &size, &encoded),
            "read the encoder's format for \(path)"
        )
        let blockSize = UInt16(clamping: encoded.mFramesPerPacket)
        let blockSizeBytes = [UInt8(blockSize >> 8), UInt8(blockSize & 0xff)]
        // Sample rate (20 bits), channels - 1 (3 bits), bits per sample - 1 (5 bits), length in samples
        // (36 bits, zero for unknown).
        let channels: UInt64 = 1
        let bitsPerSample: UInt64 = 16
        let format: UInt64 = UInt64(sampleRate) << 44 | (channels - 1) << 41 | (bitsPerSample - 1) << 36

        var description: [UInt8] = [0, 0, 0, 34]  // Block header: STREAMINFO, 34 bytes, more blocks follow.
        description += blockSizeBytes + blockSizeBytes  // Smallest and largest block, in samples.
        description += [UInt8](repeating: 0, count: 6)  // Smallest and largest frame, in bytes: unknown.
        description += (0..<8).map { UInt8(truncatingIfNeeded: format >> (56 - 8 * $0)) }
        description += [UInt8](repeating: 0, count: 16)  // MD5 of the audio: not computed.

        descriptor = open(path, O_WRONLY)
        // The description sits right after the four-byte "fLaC" marker that opens the file.
        guard descriptor >= 0, pwrite(descriptor, description, description.count, 4) == description.count
        else {
            throw CaptureError(reason: "could not write the stream description to \(path)")
        }
    }

    /// Encodes the audio that arrived since the last call and writes it to the file. Runs on `writing`.
    private func writePending() {
        guard let file else { return }
        let samples = pending.take()
        guard samples.count > 0 else { return }

        if !firstAudioReported {
            firstAudioReported = true
            var timebase = mach_timebase_info_data_t()
            mach_timebase_info(&timebase)
            let nanoseconds = Double(firstAudioHostTime) * Double(timebase.numer) / Double(timebase.denom)
            let seconds = nanoseconds / 1_000_000_000
            DispatchQueue.main.async { [onFirstAudio] in onFirstAudio?(seconds) }
        }

        var mono = AudioBufferList(
            mNumberBuffers: 1,
            mBuffers: AudioBuffer(
                mNumberChannels: 1,
                mDataByteSize: UInt32(samples.count * MemoryLayout<Float32>.size),
                mData: samples.baseAddress
            )
        )
        let status = ExtAudioFileWrite(file, UInt32(samples.count), &mono)
        guard status == noErr else {
            fail("could not write \(path) (Core Audio error \(status))")
        }

        // Once a second, ask for the audio to leave the system's cache for the disk, so that losing
        // power costs about as little as losing the process.
        writesSinceSync += 1
        if writesSinceSync == Self.writesPerSync {
            fsync(descriptor)
            writesSinceSync = 0
        }
    }

    /// Mixes every channel the device delivered down to mono and leaves it in `pending` for the file.
    /// Runs on the device's audio thread.
    private func write(_ input: UnsafePointer<AudioBufferList>, capturedAt hostTime: UInt64) {
        let buffers = UnsafeMutableAudioBufferListPointer(UnsafeMutablePointer(mutating: input))

        var channelCount = 0
        var frameCount = Int.max
        for buffer in buffers where buffer.mNumberChannels > 0 && buffer.mData != nil {
            let channels = Int(buffer.mNumberChannels)
            channelCount += channels
            frameCount = min(frameCount, Int(buffer.mDataByteSize) / (MemoryLayout<Float32>.size * channels))
        }
        guard channelCount > 0, frameCount > 0 else { return }
        let gain = 1 / Float32(channelCount)
        if firstAudioHostTime == 0 {
            firstAudioHostTime = hostTime
        }

        var written = 0
        while written < frameCount {
            let frames = min(Self.mixCapacity, frameCount - written)
            for frame in 0..<frames {
                mix[frame] = 0
            }
            for buffer in buffers where buffer.mNumberChannels > 0 && buffer.mData != nil {
                let channels = Int(buffer.mNumberChannels)
                let samples = buffer.mData!.assumingMemoryBound(to: Float32.self) + written * channels
                for frame in 0..<frames {
                    for channel in 0..<channels {
                        mix[frame] += samples[frame * channels + channel] * gain
                    }
                }
            }
            pending.append(mix, count: frames)
            written += frames
        }
    }
}
