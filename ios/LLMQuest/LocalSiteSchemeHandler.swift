import Foundation
import UniformTypeIdentifiers
import WebKit

final class LocalSiteSchemeHandler: NSObject, WKURLSchemeHandler {
    private let siteRoot: URL

    override init() {
        guard let siteRoot = Bundle.main.resourceURL?.appendingPathComponent("site", isDirectory: true) else {
            fatalError("Unable to locate app bundle resources")
        }
        self.siteRoot = siteRoot
        super.init()
    }

    func webView(_ webView: WKWebView, start urlSchemeTask: WKURLSchemeTask) {
        guard let requestURL = urlSchemeTask.request.url else {
            urlSchemeTask.didFailWithError(LocalSiteError.invalidURL)
            return
        }

        let requestedPath = requestURL.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let relativePath = requestedPath.isEmpty ? "play.html" : requestedPath

        guard !relativePath.split(separator: "/").contains("..") else {
            urlSchemeTask.didFailWithError(LocalSiteError.invalidURL)
            return
        }

        let fileURL = siteRoot.appendingPathComponent(relativePath, isDirectory: false)

        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            guard let response = HTTPURLResponse(
                url: requestURL,
                statusCode: 404,
                httpVersion: nil,
                headerFields: nil
            ) else {
                urlSchemeTask.didFailWithError(LocalSiteError.invalidURL)
                return
            }
            urlSchemeTask.didReceive(response)
            urlSchemeTask.didFinish()
            return
        }

        do {
            let data = try Data(contentsOf: fileURL)
            let response = URLResponse(
                url: requestURL,
                mimeType: mimeType(for: fileURL),
                expectedContentLength: data.count,
                textEncodingName: nil
            )
            urlSchemeTask.didReceive(response)
            urlSchemeTask.didReceive(data)
            urlSchemeTask.didFinish()
        } catch {
            urlSchemeTask.didFailWithError(error)
        }
    }

    func webView(_ webView: WKWebView, stop urlSchemeTask: WKURLSchemeTask) {}

    private func mimeType(for fileURL: URL) -> String {
        let ext = fileURL.pathExtension.lowercased()
        switch ext {
        case "html":
            return "text/html"
        case "js":
            return "application/javascript"
        case "css":
            return "text/css"
        case "json":
            return "application/json"
        case "gz":
            return "application/gzip"
        case "png":
            return "image/png"
        case "jpg", "jpeg":
            return "image/jpeg"
        case "svg":
            return "image/svg+xml"
        case "mp3":
            return "audio/mpeg"
        default:
            return UTType(filenameExtension: ext)?.preferredMIMEType ?? "application/octet-stream"
        }
    }
}

enum LocalSiteError: Error {
    case invalidURL
}
