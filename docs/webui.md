# Web UI

```{versionadded} 1.21.0
```

`icloudpd` can start an internal web server on port 8080 and accept input (password and MFA code) from there instead of the console. The web server is started only if `webui` is selected for [MFA provider and/or Password Provider](authentication).

## Listening address

The server listens on all network interfaces by default and has no password protection. Use [`--webui-host`](webui-host-parameter) `127.0.0.1` to accept connections from this computer only.

In Docker, keep the default `0.0.0.0` (the container's loopback is not reachable from the host, unless you use host networking with `--network host`) and limit access with the port mapping instead, for example `-p 127.0.0.1:8080:8080`.

## Status API

With [`--webui-api`](webui-api-parameter) the server also answers a few requests with JSON, so other programs (such as a menu bar app) can follow what `icloudpd` does. Without the option these paths return 404. The API has no password protection; combine it with [`--webui-host`](webui-host-parameter) `127.0.0.1` to keep it on this computer.

| Request | Answer |
|---|---|
| `GET /api/status` | `state` (`idle`, `syncing`, `waiting`, `need_password`, `need_mfa` and the intermediate states), `error`, `downloaded_total`, and `progress` with `photos_count`, `photos_counter`, `photos_percent`, `last_message` and `waiting_seconds` (time until the next run in watch mode) |
| `GET /api/activity` | `total` (files downloaded by this process) and `files`, the newest 50 with `name`, `path`, `size` and `time` (unix timestamp) |

The Apple ID is not part of the answers. The file paths in `/api/activity` are the full paths of the downloaded files. The history lives in memory and starts empty with every `icloudpd` process. The existing `POST /resume` and `POST /cancel` stay available with or without the option.

