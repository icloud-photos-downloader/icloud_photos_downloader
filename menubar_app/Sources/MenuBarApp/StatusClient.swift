import Foundation

/// Response of icloudpd's `GET /api/status` (needs the repo version of icloudpd).
struct APIStatus: Decodable {
    struct Progress: Decodable {
        let photosCount: Int
        let photosCounter: Int
        let photosPercent: Int
        let lastMessage: String?
        let waitingSeconds: Int
    }
    let state: String
    let status: String
    let currentUser: String?
    let error: String?
    let progress: Progress
    let downloadedTotal: Int?  // missing in older icloudpd versions
}

/// One file downloaded by icloudpd (`GET /api/activity`).
struct ActivityFile: Codable, Identifiable, Hashable {
    let name: String
    let path: String
    let size: Int64?
    let time: Double
    /// nil for a download (what icloudpd reports); the app adds the deletions it carries out
    var kind: String? = nil
    var id: String { "\(kind ?? "downloaded")|\(path)|\(time)" }

    enum Kind: String {
        case downloaded
        case deletedICloud
        case deletedPhotos
        case trashedDisk
        case savedFromPhotos
    }

    var event: Kind { Kind(rawValue: kind ?? "") ?? .downloaded }
}

struct ActivityResponse: Decodable {
    let total: Int
    let files: [ActivityFile]
}

enum StatusClient {
    static func fetch() async -> APIStatus? {
        var request = URLRequest(url: webUIURL.appendingPathComponent("api/status"))
        request.timeoutInterval = 2
        guard let (data, response) = try? await URLSession.shared.data(for: request),
              (response as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try? decoder.decode(APIStatus.self, from: data)
    }

    static func fetchActivity() async -> ActivityResponse? {
        var request = URLRequest(url: webUIURL.appendingPathComponent("api/activity"))
        request.timeoutInterval = 2
        guard let (data, response) = try? await URLSession.shared.data(for: request),
              (response as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        return try? JSONDecoder().decode(ActivityResponse.self, from: data)
    }

    /// Ends the waiting period and starts the next sync run immediately.
    static func resume() async {
        var request = URLRequest(url: webUIURL.appendingPathComponent("resume"))
        request.httpMethod = "POST"
        request.timeoutInterval = 2
        _ = try? await URLSession.shared.data(for: request)
    }
}
