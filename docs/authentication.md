# iCloud Authentication

## Multi-Factor Authentication

If your Apple account has two-factor authentication (multi-factor authentication, MFA) enabled,
you will be prompted for a code when you run the script. Two-factor authentication will expire after an interval set by Apple,
at which point you will have to re-authenticate. This interval is currently two months. Apple requires MFA for all new accounts.

You can receive an email notification when two-factor authentication expires by passing the
`--smtp-username` and `--smtp-password` options. Emails will be sent to `--smtp-username` by default,
or you can send to a different email address with `--notification-email`.

If you want to send notification emails using your Gmail account, and you have enabled two-factor authentication, you will need to generate an App Password at <https://myaccount.google.com/apppasswords>

## MFA Providers

```{versionadded} 1.21.0
```

There are two ways to provide MFA code to `icloudpd`:
- Using console
- Using web interface

The choice can be made with [`--mfa-provider`](mfa-provider-parameter) parameter.

Default: *console*
Other options: *webui*

## Access from Mainland China

Access to iCloud.com is blocked from mainland China. `icloudpd` can be used with [`--domain cn`](domain-parameter) parameter to support downloading iCloud Photos from mainland China, however, people reported mixed results with that parameter.

## FIDO

Authentication to iCloud with hardware keys (FIDO) is not supported.

## ADP

Advanced Data Protection (ADP) for iCloud accounts is not supported because `icloudpd` simulates web access, which is disabled with ADP.

## Occasional Errors

Some authentication errors may be resolved by clearing `.pyicloud` subfolder in the user's home directory. [Example](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/772#issuecomment-1950963522)

## Password Providers

```{versionadded} 1.20.0
```
```{versionadded} 1.21.0
WebUI support
```

Passwords for iCloud access can be supplied by user in four ways:
- Using [`--password`](password-parameter) command line parameter
- Using keyring
- Using console
- Using web interface

It is possible to specify which of these three ways `icloudpd` should use, by specifying them with [`--password-provider`](password-provider-parameter) parameter. More than one can be specified and the order
of providers matches the order then will be checked for password. E.g. `--password-provider keyring --password-provider console` means that `icloudpd` will check password in keyring first and then, if no password found, ask for password in the console.

Keyring password provider, if specified, saves valid password back into keyring.

Console and Web UI are not compatible with each other. Console or WebUI providers, if specified, must be last in the list of providers because they cannot be skipped.

Default set and order of providers are: *parameter*, *keyring*, *console*

### Managing System Keyring

You can store your password in the system keyring or delete it from there using the `icloud` command-line tool:

```
$ icloud --username jappleseed@apple.com
ICloud Password for jappleseed@apple.com:
Save password in keyring? (y/N)
```

If you would like to delete a password stored in your system keyring,
you can clear a stored password using the `--delete-from-keyring` command-line option:

``` sh
icloud --username jappleseed@apple.com --delete-from-keyring
```

```{note}
Use `icloud`, not `icloudpd`
```
