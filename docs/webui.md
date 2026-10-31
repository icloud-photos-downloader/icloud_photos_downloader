# Web UI

```{versionadded} 1.21.0
```

`icloudpd` can start an internal web server on port 8080 and accept input (password and MFA code) from there instead of the console. The web server is started only if `webui` is selected for [MFA provider and/or Password Provider](authentication).

## Listening address

The server listens on all network interfaces by default and has no password protection. Use [`--webui-host`](webui-host-parameter) `127.0.0.1` to accept connections from this computer only.

## Status API

Besides the pages for the password and the MFA code, the server answers a few requests with JSON, so other programs (such as a menu bar app) can follow what `icloudpd` does:

| Request | Answer |
|---|---|
| `GET /api/status` | `state` (`idle`, `syncing`, `waiting`, `need_password`, `need_mfa` and the intermediate states), `current_user`, `error`, `downloaded_total`, and `progress` with `photos_count`, `photos_counter`, `photos_percent`, `last_message` and `waiting_seconds` (time until the next run in watch mode) |
| `GET /api/activity` | `total` (files downloaded by this process) and `files`, the newest 50 with `name`, `path`, `size` and `time` (unix timestamp) |
| `POST /resume` | ends the waiting period of [`--watch-with-interval`](watch-with-interval-parameter) and starts the next run now |
| `POST /cancel` | stops the download that is running |

The history of `/api/activity` lives in memory and starts empty with every `icloudpd` process.
