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

## Security

```{warning}
The web server always uses port 8080, listens on all network interfaces, and has no login or password protection. Anyone who can reach the port can enter a password or code, and see the status page, which lists your settings (the iCloud password is hidden, the SMTP password is not). Do not expose port 8080 to the internet; only make it reachable on your own network.
```

## Limitations

- The port can't be changed. With Docker, map it to another port on the host instead, e.g. `-p 9090:8080`.
- The web UI can't send the 2FA code by SMS; see [The 2FA Code Doesn't Arrive](mfa-code-not-arriving).
- The web UI doesn't support security keys (FIDO); see [FIDO](fido).
