# Web UI

```{versionadded} 1.21.0
```

`icloudpd` can start an internal web server on port 8080 and accept input (password and MFA code) from there instead of the console. The web server is started only if `webui` is selected for [MFA provider and/or Password Provider](authentication).

## Listening address

The server listens on all network interfaces by default and has no password protection. Use [`--webui-host`](webui-host-parameter) `127.0.0.1` to accept connections from this computer only.

In Docker, keep the default `0.0.0.0` (the container's loopback is not reachable from the host) and limit access with the port mapping instead, for example `-p 127.0.0.1:8080:8080`.
