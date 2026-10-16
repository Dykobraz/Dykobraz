import Foundation
import ScreenCaptureKit
import CoreMedia
import AudioToolbox

// Only PCM is sent through stdout to the parent process. No audio files.
final class AudioOutput: NSObject, SCStreamOutput, SCStreamDelegate {
    func stream(_ stream: SCStream, didStopWithError error: Error) {
        fputs("Zachytávání bylo přerušeno: \(error.localizedDescription)\n", stderr)
        exit(1)
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sample: CMSampleBuffer,
                of type: SCStreamOutputType) {
        guard type == .audio, sample.isValid,
              let desc = sample.formatDescription,
              let format = CMAudioFormatDescriptionGetStreamBasicDescription(desc) else { return }
        let f = format.pointee
        guard f.mFormatID == kAudioFormatLinearPCM,
              f.mFormatFlags & kAudioFormatFlagIsFloat != 0,
              f.mBitsPerChannel == 32 else {
            fputs("Nepodporovaný zvukový formát.\n", stderr)
            exit(2)
        }
        var size = 0
        CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(sample,
            bufferListSizeNeededOut: &size, bufferListOut: nil, bufferListSize: 0,
            blockBufferAllocator: nil, blockBufferMemoryAllocator: nil,
            flags: 0, blockBufferOut: nil)
        guard size >= MemoryLayout<AudioBufferList>.size else { return }
        let memory = UnsafeMutableRawPointer.allocate(byteCount: size,
            alignment: MemoryLayout<AudioBufferList>.alignment)
        defer { memory.deallocate() }
        let list = memory.bindMemory(to: AudioBufferList.self, capacity: 1)
        var block: CMBlockBuffer?
        let result = CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(sample,
            bufferListSizeNeededOut: nil, bufferListOut: list, bufferListSize: size,
            blockBufferAllocator: nil, blockBufferMemoryAllocator: nil,
            flags: 0, blockBufferOut: &block)
        guard result == noErr else { return }
        let buffers = UnsafeMutableAudioBufferListPointer(list)
        let frames = CMSampleBufferGetNumSamples(sample)
        let channels = Int(f.mChannelsPerFrame)
        guard frames > 0, channels > 0 else { return }
        var mono = [Float](repeating: 0, count: frames)
        for buffer in buffers {
            guard let raw = buffer.mData else { continue }
            let width = Int(buffer.mNumberChannels)
            guard width > 0, Int(buffer.mDataByteSize) >= frames * width * 4 else { continue }
            let values = raw.assumingMemoryBound(to: Float.self)
            for i in 0..<frames {
                for c in 0..<width { mono[i] += values[i * width + c] / Float(channels) }
            }
        }
        let data = mono.withUnsafeBytes { Data($0) }
        let packet: [String: Any] = ["rate": Int(f.mSampleRate), "pcm": data.base64EncodedString()]
        if var encoded = try? JSONSerialization.data(withJSONObject: packet) {
            encoded.append(10)
            FileHandle.standardOutput.write(encoded)
        }
    }
}

@main struct Capture {
    static func main() async {
        do {
            let content = try await SCShareableContent.excludingDesktopWindows(false,
                onScreenWindowsOnly: true)
            guard let display = content.displays.first else {
                fputs("Nebyl nalezen displej.\n", stderr); exit(1)
            }
            let filter = SCContentFilter(display: display, excludingApplications: [], exceptingWindows: [])
            let config = SCStreamConfiguration()
            config.capturesAudio = true
            config.excludesCurrentProcessAudio = true
            config.sampleRate = 48000
            config.channelCount = 2
            config.width = 2
            config.height = 2
            config.minimumFrameInterval = CMTime(value: 1, timescale: 1)
            let output = AudioOutput()
            let stream = SCStream(filter: filter, configuration: config, delegate: output)
            try stream.addStreamOutput(output, type: .audio,
                sampleHandlerQueue: DispatchQueue(label: "seminar.audio"))
            try await stream.startCapture()
            fputs("Zachytávání systémového zvuku spuštěno.\n", stderr)
            while true { try await Task.sleep(nanoseconds: 1_000_000_000) }
        } catch {
            fputs("Nelze spustit zachytávání: \(error.localizedDescription)\nPovolte záznam obrazovky a systémového zvuku v Nastavení systému → Soukromí a zabezpečení.\n", stderr)
            exit(1)
        }
    }
}
