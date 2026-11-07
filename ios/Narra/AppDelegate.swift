import AVFoundation
import UIKit

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        // .playback + modo de áudio em segundo plano: a narração continua com a tela bloqueada
        let session = AVAudioSession.sharedInstance()
        try? session.setCategory(.playback, mode: .spokenAudio, options: [])
        try? session.setActive(true)

        let controller = ViewController()
        let window = UIWindow(frame: UIScreen.main.bounds)
        window.rootViewController = controller
        window.makeKeyAndVisible()
        self.window = window

        if let url = launchOptions?[.url] as? URL {
            controller.openDocument(url)
        }
        return true
    }

    /// Documento aberto pelo "Compartilhar"/"Abrir em" do app Arquivos.
    func application(_ app: UIApplication, open url: URL,
                     options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
        (window?.rootViewController as? ViewController)?.openDocument(url)
        return true
    }
}
