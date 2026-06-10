import UIKit
import WebKit

final class QuestWebViewController: UIViewController {
    private var webView: WKWebView!

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 0.05, green: 0.07, blue: 0.09, alpha: 1)

        let configuration = WKWebViewConfiguration()
        configuration.setURLSchemeHandler(LocalSiteSchemeHandler(), forURLScheme: "lqb")
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []

        let contentController = configuration.userContentController
        contentController.add(self, name: "shareFile")

        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.isOpaque = false
        webView.backgroundColor = .clear
        webView.scrollView.backgroundColor = .clear

        view.addSubview(webView)
        webView.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            webView.topAnchor.constraint(equalTo: view.topAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])

        loadPlayPage()
    }

    private func loadPlayPage() {
        guard let url = URL(string: "lqb://app/play.html") else {
            assertionFailure("Invalid bundled play URL")
            return
        }
        webView.load(URLRequest(url: url))
    }

    private func presentShareSheet(items: [Any]) {
        let vc = UIActivityViewController(activityItems: items, applicationActivities: nil)
        vc.popoverPresentationController?.sourceView = webView
        vc.popoverPresentationController?.sourceRect = CGRect(
            x: webView.bounds.midX, y: webView.bounds.maxY - 40,
            width: 1, height: 1
        )
        present(vc, animated: true)
    }
}

// MARK: - WKScriptMessageHandler

extension QuestWebViewController: WKScriptMessageHandler {
    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard message.name == "shareFile",
              let body = message.body as? [String: Any],
              let content = body["content"] as? String,
              let filename = body["filename"] as? String
        else { return }

        let mimeType = body["mimeType"] as? String ?? "application/octet-stream"
        let tmpDir = FileManager.default.temporaryDirectory
        let fileURL = tmpDir.appendingPathComponent(filename)

        let data: Data?
        if mimeType.hasPrefix("image/"), let b64 = content.split(separator: ",").last {
            data = Data(base64Encoded: String(b64))
        } else {
            data = content.data(using: .utf8)
        }

        guard let fileData = data else { return }

        do {
            try fileData.write(to: fileURL, options: .atomic)
            presentShareSheet(items: [fileURL])
        } catch {
            // File write failed — fall through silently.
        }
    }
}

// MARK: - WKNavigationDelegate

extension QuestWebViewController: WKNavigationDelegate {
    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }

        if url.scheme == "lqb" {
            decisionHandler(.allow)
            return
        }

        if navigationAction.navigationType == .linkActivated {
            UIApplication.shared.open(url)
        }

        decisionHandler(.cancel)
    }
}
