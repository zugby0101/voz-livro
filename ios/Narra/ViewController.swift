import UIKit
import WebKit

/// Mostra a interface do Narra (a mesma da versão web) e liga o JavaScript ao motor de voz do iOS.
final class ViewController: UIViewController, WKScriptMessageHandler, WKNavigationDelegate {

    private var web: WKWebView!
    private let speech = SpeechEngine()
    private var pageLoaded = false
    private var pendingDocument: String?

    /// Objeto `window.NarraTTS` que a página usa (o mesmo contrato do app Android).
    private static let bridgeScript = """
    (function () {
      var post = function (cmd, args) {
        window.webkit.messageHandlers.narra.postMessage({ cmd: cmd, args: Array.prototype.slice.call(args) });
      };
      var voices = "[]", pending = "";
      window.NarraTTS = {
        platform: "ios",
        getVoices: function () { return voices; },
        speakQueue: function () { post("speakQueue", arguments); },
        stop: function () { post("stop", arguments); },
        openSettings: function () { post("openSettings", arguments); },
        takePendingFile: function () { var f = pending; pending = ""; return f; },
        exportAudio: function () { post("exportAudio", arguments); },
        cancelExport: function () { post("cancelExport", arguments); }
      };
      window.__narraSetVoices = function (v) { voices = v; if (window.__ttsReady) window.__ttsReady(true); };
      window.__narraSetPending = function (f) { pending = f; if (window.__checkPending) window.__checkPending(); };
    })();
    """

    override func loadView() {
        let contents = WKUserContentController()
        contents.addUserScript(WKUserScript(source: Self.bridgeScript,
                                            injectionTime: .atDocumentStart,
                                            forMainFrameOnly: true))
        contents.add(WeakMessageHandler(self), name: "narra")

        let config = WKWebViewConfiguration()
        config.userContentController = contents
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []

        web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = self
        web.isOpaque = false
        web.backgroundColor = UIColor(red: 0.933, green: 0.945, blue: 0.957, alpha: 1)
        // a página já trata as áreas seguras (notch e barra inferior) via CSS env()
        web.scrollView.contentInsetAdjustmentBehavior = .never
        view = web

        speech.runJavaScript = { [weak self] code in
            self?.web.evaluateJavaScript(code, completionHandler: nil)
        }
        speech.shareFile = { [weak self] url in
            self?.share(url)
        }
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        guard let index = Bundle.main.url(forResource: "index", withExtension: "html", subdirectory: "www") else {
            assertionFailure("www/index.html não está no app. Rode ios/prepare-www.sh")
            return
        }
        web.loadFileURL(index, allowingReadAccessTo: index.deletingLastPathComponent())
    }

    override var preferredStatusBarStyle: UIStatusBarStyle { .darkContent }

    // MARK: - Página

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        pageLoaded = true
        runJS("window.__narraSetVoices(\(Self.jsString(speech.voicesJSON())))")
        if let doc = pendingDocument {
            pendingDocument = nil
            runJS("window.__narraSetPending(\(Self.jsString(doc)))")
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let url = navigationAction.request.url,
           url.scheme == "http" || url.scheme == "https",
           navigationAction.navigationType == .linkActivated {
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    // MARK: - Mensagens do JavaScript

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any], let cmd = body["cmd"] as? String else { return }
        let args = body["args"] as? [Any] ?? []
        func str(_ i: Int) -> String { i < args.count ? (args[i] as? String ?? "") : "" }
        func num(_ i: Int) -> Double { i < args.count ? ((args[i] as? NSNumber)?.doubleValue ?? 0) : 0 }
        func flag(_ i: Int) -> Bool { i < args.count ? ((args[i] as? NSNumber)?.boolValue ?? false) : false }

        switch cmd {
        case "speakQueue":
            speech.speakQueue(json: str(0), start: Int(num(1)), generation: Int(num(2)), voiceId: str(3),
                              language: str(4), rate: num(5), pitch: num(6), flush: flag(7))
        case "stop":
            speech.stop()
        case "openSettings":
            showVoiceHelp()
        case "exportAudio":
            speech.export(json: str(0), title: str(1), voiceId: str(2), language: str(3),
                          rate: num(4), pitch: num(5))
        case "cancelExport":
            speech.cancelExport()
        default:
            break
        }
    }

    // MARK: - Documentos recebidos

    func openDocument(_ url: URL) {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        do {
            let data = try Data(contentsOf: url)
            guard data.count <= 60 * 1024 * 1024 else {
                alert("Arquivo grande demais", "O limite é de 60 MB.")
                return
            }
            let payload: [String: String] = ["name": url.lastPathComponent, "b64": data.base64EncodedString()]
            let json = String(data: try JSONSerialization.data(withJSONObject: payload), encoding: .utf8) ?? ""
            if pageLoaded {
                runJS("window.__narraSetPending(\(Self.jsString(json)))")
            } else {
                pendingDocument = json
            }
        } catch {
            alert("Não foi possível abrir o arquivo", error.localizedDescription)
        }
    }

    // MARK: - Utilidades

    private func share(_ url: URL) {
        let sheet = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        if let pop = sheet.popoverPresentationController {
            pop.sourceView = view
            pop.sourceRect = CGRect(x: view.bounds.midX, y: view.bounds.midY, width: 1, height: 1)
            pop.permittedArrowDirections = []
        }
        present(sheet, animated: true)
    }

    private func showVoiceHelp() {
        let a = UIAlertController(
            title: "Vozes mais naturais",
            message: "Abra Ajustes › Acessibilidade › Conteúdo Falado › Vozes, escolha o idioma e baixe "
                + "uma voz \"Aprimorada\" ou \"Premium\". Depois volte ao Narra.",
            preferredStyle: .alert)
        a.addAction(UIAlertAction(title: "Abrir Ajustes", style: .default) { _ in
            if let url = URL(string: UIApplication.openSettingsURLString) {
                UIApplication.shared.open(url)
            }
        })
        a.addAction(UIAlertAction(title: "OK", style: .cancel))
        present(a, animated: true)
    }

    private func alert(_ title: String, _ message: String) {
        let a = UIAlertController(title: title, message: message, preferredStyle: .alert)
        a.addAction(UIAlertAction(title: "OK", style: .default))
        present(a, animated: true)
    }

    private func runJS(_ code: String) {
        web.evaluateJavaScript(code, completionHandler: nil)
    }

    /// Converte um texto Swift em literal de string JavaScript.
    static func jsString(_ s: String) -> String {
        guard let data = try? JSONSerialization.data(withJSONObject: [s]),
              let arr = String(data: data, encoding: .utf8) else { return "\"\"" }
        return String(arr.dropFirst().dropLast())
    }
}

/// Evita o ciclo de referência entre WKUserContentController e o controlador.
private final class WeakMessageHandler: NSObject, WKScriptMessageHandler {
    weak var target: WKScriptMessageHandler?
    init(_ target: WKScriptMessageHandler) { self.target = target }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        target?.userContentController(userContentController, didReceive: message)
    }
}
