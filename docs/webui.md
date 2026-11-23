# Web UI

```{versionadded} 1.21.0
```

`icloudpd` can start an internal web server and accept input from a browser instead of the console. In the browser you can:
- enter the iCloud password;
- enter the two-factor authentication (2FA) code;
- see the status and download progress, and the settings in use;
- cancel the current download run, or, with [`--watch-with-interval`](watch-with-interval-parameter), skip the wait and start the next run now (Resume).

## Enabling

The web server starts only if `webui` is selected as [MFA provider](mfa-providers) and/or [password provider](password-providers):

```
icloudpd --username jappleseed@apple.com --directory ./photos --mfa-provider webui --password-provider webui
```

Both [`--mfa-provider`](mfa-provider-parameter) and [`--password-provider`](password-provider-parameter) are global options, so they apply to all accounts. Then open `http://<machine>:8080/` in a browser.

With Docker, publish the port:

```
docker run --rm -p 8080:8080 -v $(pwd)/Photos:/data icloudpd/icloudpd:latest icloudpd --username jappleseed@apple.com --directory /data --mfa-provider webui --password-provider webui
```

(webui-security)=
## Security

```{warning}
The web server always uses port 8080, listens on all network interfaces by default, and has no login or password protection. Anyone who can reach the port can enter a password or code, and see the status page, which lists your settings (without passwords). Do not expose port 8080 to the internet; only make it reachable on your own network.
```

Use [`--webui-host`](webui-host-parameter) `127.0.0.1` to accept connections from this computer only.

In Docker, keep the default `0.0.0.0` (the container's loopback is not reachable from the host, unless you use host networking with `--network host`) and limit access with the port mapping instead, for example `-p 127.0.0.1:8080:8080`.

(webui-status-api)=
## Status API

With [`--webui-api`](webui-api-parameter) the server also answers a few requests with JSON, so other programs (such as a menu bar app) can follow what `icloudpd` does. Without the option these paths return 404 and nothing is recorded. Like the rest of the web server, the API only runs when `webui` is selected as MFA or password provider (see [Enabling](#enabling)). It has no password protection; combine it with [`--webui-host`](webui-host-parameter) `127.0.0.1` to keep it on this computer (in Docker, limit access with the port mapping instead, as described in [Security](webui-security)).

| Request | Answer |
|---|---|
| `GET /api/status` | `state`, `status`, `error`, `downloaded_total`, and `progress` with `photos_count`, `photos_counter`, `photos_percent`, `last_message` and `waiting_seconds` (time until the next run in watch mode) |
| `GET /api/activity` | `total` (files downloaded by this process) and `files`, the newest ones with `name`, `path`, `size` and `time` (unix timestamp). `?limit=N` returns up to `N` files (default 50, at most 200) |

`state` is one of `need_password`, `supplied_password`, `checking_password`, `need_mfa`, `supplied_mfa` or `checking_mfa` while a password or code is needed, entered or being checked. Otherwise it is `syncing` while a run is in progress, which includes signing in, listing albums and the time between albums (so it does not depend on `photos_count`, which is empty with `--until-found`), `waiting` between the runs of watch mode, and `idle` when nothing runs.

```{warning}
`/api/activity` shows the full local paths of the downloaded files to anyone who can reach the port.
```

The Apple ID is not part of the answers. The history lives in memory (the last 200 files) and starts empty with every `icloudpd` process. The existing `POST /resume` and `POST /cancel` stay available with or without the option.

## Limitations

- The port can't be changed. With Docker, map it to another port on the host instead, e.g. `-p 9090:8080`.
- The web UI can't send the 2FA code by SMS; see [The 2FA Code Doesn't Arrive](mfa-code-not-arriving).
- The web UI doesn't support security keys (FIDO); see [FIDO](fido).
