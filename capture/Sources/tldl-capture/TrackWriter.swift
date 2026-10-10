import AudioToolbox
import CoreAudio
import Foundation

/// Writes what one input device delivers to a file: one Track, as mono 16-bit FLAC at the device's
/// sample rate.
final class TrackWriter {
    private let device: AudioDeviceID
    private var file: ExtAudioFileRef?
    private var ioProc: AudioDeviceIOProcID?

    /// The level of what is being written.
    let level = LevelMeter()

    /// Scratch space for the mono mix, allocated up front because the audio thread must not allocate.
    private let mix: UnsafeMutablePointer<Float32>
    private static let mixCapacity = 4096

    init(device: AudioDeviceID, path: String) throws {
        self.device = device
        mix = .allocate(capacity: Self.mixCapacity)

        let sampleRate = try readProperty(
            kAudioDevicePropertyNominalSampleRate,
            of: device,
            startingFrom: Float64(0),
            to: "read the sample rate for \(path)"
        )

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

        // What `write` hands over: the mono mix, in the 32-bit float samples Core Audio devices deliver.
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
        // An empty write here does the allocations, so the writes on the audio thread do none.
        try check(ExtAudioFileWriteAsync(file!, 0, nil), "prepare writing \(path)")

        try check(
            AudioDeviceCreateIOProcIDWithBlock(&ioProc, device, nil) { [unowned self] _, input, _, _, _ in
                self.write(input)
            },
            "listen to the device for \(path)"
        )
    }

    func start() throws {
        try check(AudioDeviceStart(device, ioProc), "start the device")
    }

    /// Stops listening and closes the file, flushing what is still waiting to be written.
    func stop() {
        if let ioProc {
            AudioDeviceStop(device, ioProc)
            AudioDeviceDestroyIOProcID(device, ioProc)
            self.ioProc = nil
        }
        if let file {
            ExtAudioFileDispose(file)
            self.file = nil
        }
    }

    /// Mixes every channel the device delivered down to mono and queues it for the file.
    /// Runs on the device's audio thread.
    private func write(_ input: UnsafePointer<AudioBufferList>) {
        guard let file else { return }
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
            level.hear(mix, count: frames)
            var mono = AudioBufferList(
                mNumberBuffers: 1,
                mBuffers: AudioBuffer(
                    mNumberChannels: 1,
                    mDataByteSize: UInt32(frames * MemoryLayout<Float32>.size),
                    mData: mix
                )
            )
            ExtAudioFileWriteAsync(file, UInt32(frames), &mono)
            written += frames
        }
    }
}
