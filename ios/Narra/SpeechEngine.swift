import AVFoundation
import UIKit

/// Narração e gravação com o motor de voz do iOS (AVSpeechSynthesizer).
final class SpeechEngine: NSObject, AVSpeechSynthesizerDelegate {

    var runJavaScript: ((String) -> Void)?
    var shareFile: ((URL) -> Void)?

    private let synth = AVSpeechSynthesizer()
    /// utterance -> (geração, índice da frase), para avisar a página qual frase está sendo lida
    private var tracked: [ObjectIdentifier: (generation: Int, index: Int)] = [:]

    // gravação
    private var exporter: AVSpeechSynthesizer?
    private var exportCancelled = false

    override init() {
        super.init()
        synth.delegate = self
    }

    // MARK: - Vozes

    func voicesJSON() -> String {
        let wanted: Set<String> = ["pt", "en", "es"]
        let voices = AVSpeechSynthesisVoice.speechVoices().filter { wanted.contains(String($0.language.prefix(2))) }
        let list: [[String: Any]] = voices.map { v in
            var neural = v.quality == .enhanced
            var label = v.name
            if v.quality == .enhanced { label += " (Aprimorada)" }
            if #available(iOS 16.0, *), v.quality == .premium {
                neural = true
                label += " (Premium)"
            }
            return ["name": v.identifier, "lang": v.language, "label": label, "neural": neural]
        }
        guard let data = try? JSONSerialization.data(withJSONObject: list),
              let json = String(data: data, encoding: .utf8) else { return "[]" }
        return json
    }

    private func voice(_ id: String, _ language: String) -> AVSpeechSynthesisVoice? {
        if !id.isEmpty, let v = AVSpeechSynthesisVoice(identifier: id) { return v }
        return AVSpeechSynthesisVoice(language: language)
    }

    private func utterance(_ text: String, _ voice: AVSpeechSynthesisVoice?, _ rate: Double, _ pitch: Double) -> AVSpeechUtterance {
        let u = AVSpeechUtterance(string: text)
        u.voice = voice
        // a página usa 0,5×–2× (1× = normal); o iOS usa 0–1 com 0,5 como padrão
        let r = Float(rate) * AVSpeechUtteranceDefaultSpeechRate
        u.rate = min(max(r, AVSpeechUtteranceMinimumSpeechRate), AVSpeechUtteranceMaximumSpeechRate)
        u.pitchMultiplier = Float(min(max(pitch, 0.5), 2.0))
        return u
    }

    // MARK: - Narração

    func speakQueue(json: String, start: Int, generation: Int, voiceId: String, language: String,
                    rate: Double, pitch: Double, flush: Bool) {
        guard exporter == nil else { return }
        guard let texts = (try? JSONSerialization.jsonObject(with: Data(json.utf8))) as? [String] else { return }
        if flush {
            tracked.removeAll()
            synth.stopSpeaking(at: .immediate)
        }
        try? AVAudioSession.sharedInstance().setActive(true)
        let v = voice(voiceId, language)
        for (i, text) in texts.enumerated() {
            let u = utterance(text, v, rate, pitch)
            if generation >= 0 {
                tracked[ObjectIdentifier(u)] = (generation, start + i)
            }
            synth.speak(u)
        }
    }

    func stop() {
        tracked.removeAll()
        synth.stopSpeaking(at: .immediate)
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didStart utterance: AVSpeechUtterance) {
        guard synthesizer === synth, let t = tracked[ObjectIdentifier(utterance)] else { return }
        runJavaScript?("window.__tts&&window.__tts('start',\(t.generation),\(t.index))")
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        guard synthesizer === synth, let t = tracked.removeValue(forKey: ObjectIdentifier(utterance)) else { return }
        runJavaScript?("window.__tts&&window.__tts('done',\(t.generation),\(t.index))")
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        if synthesizer === synth { tracked.removeValue(forKey: ObjectIdentifier(utterance)) }
    }

    // MARK: - Gravação em arquivo (M4A)

    func export(json: String, title: String, voiceId: String, language: String, rate: Double, pitch: Double) {
        guard exporter == nil else { return }
        guard let chunks = (try? JSONSerialization.jsonObject(with: Data(json.utf8))) as? [String], !chunks.isEmpty else {
            notify("error", "nada para gravar")
            return
        }
        stop()
        exportCancelled = false
        UIApplication.shared.isIdleTimerDisabled = true

        let invalid = CharacterSet(charactersIn: "/\\:*?\"<>|")
        var name = title.components(separatedBy: invalid).joined(separator: " ").trimmingCharacters(in: .whitespaces)
        if name.isEmpty { name = "audiolivro" }
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("export", isDirectory: true)
        try? FileManager.default.removeItem(at: dir)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let url = dir.appendingPathComponent(name + ".m4a")

        let v = voice(voiceId, language)
        let ex = AVSpeechSynthesizer()
        exporter = ex
        var file: AVAudioFile?
        var index = 0
        var failure: String?

        func finish() {
            file = nil // fecha e finaliza o arquivo
            exporter = nil
            UIApplication.shared.isIdleTimerDisabled = false
            if let failure = failure {
                try? FileManager.default.removeItem(at: url)
                notify("error", failure)
            } else if exportCancelled {
                try? FileManager.default.removeItem(at: url)
                notify("cancel", "")
            } else if FileManager.default.fileExists(atPath: url.path) {
                notify("done", url.lastPathComponent)
                shareFile?(url)
            } else {
                notify("error", "a voz escolhida não gerou áudio. Tente outra voz.")
            }
        }

        func next() {
            if exportCancelled || failure != nil || index >= chunks.count {
                if index >= chunks.count && failure == nil && !exportCancelled {
                    notify("encoding", "")
                }
                finish()
                return
            }
            runJavaScript?("window.__exp&&window.__exp('progress',\(index + 1),\(chunks.count))")
            let u = utterance(chunks[index], v, rate, pitch)
            index += 1
            var advanced = false
            let advance = {
                DispatchQueue.main.async {
                    if advanced { return }
                    advanced = true
                    next()
                }
            }
            ex.write(u) { buffer in
                guard let pcm = buffer as? AVAudioPCMBuffer else { return }
                if pcm.frameLength == 0 { // buffer vazio = fim deste trecho
                    advance()
                    return
                }
                do {
                    if file == nil {
                        let settings: [String: Any] = [
                            AVFormatIDKey: kAudioFormatMPEG4AAC,
                            AVSampleRateKey: pcm.format.sampleRate,
                            AVNumberOfChannelsKey: pcm.format.channelCount,
                            AVEncoderBitRateKey: 64000,
                        ]
                        file = try AVAudioFile(forWriting: url, settings: settings,
                                               commonFormat: pcm.format.commonFormat,
                                               interleaved: pcm.format.isInterleaved)
                    }
                    try file?.write(from: pcm)
                } catch {
                    DispatchQueue.main.async {
                        if failure == nil { failure = error.localizedDescription }
                    }
                    advance()
                }
            }
        }
        next()
    }

    func cancelExport() {
        exportCancelled = true
    }

    private func notify(_ event: String, _ arg: String) {
        runJavaScript?("window.__exp&&window.__exp('\(event)',\(ViewController.jsString(arg)),0)")
    }
}
