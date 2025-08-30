# Web UI

```{versionadded} 1.21.0
```

`icloudpd` can start an internal web server on port 8080 and accept input (password and MFA code) from there instead of the console. The web server is started only if `webui` is selected for [MFA provider and/or Password Provider](authentication).
