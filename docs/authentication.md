# iCloud Authentication

~~~{admonition} Two programs: `icloudpd` and `icloud`
- `icloudpd` downloads your photos. Use it for everything on this page, including signing in (see [`--auth-only`](auth-only-parameter)).
- `icloud` is a small extra tool that comes with `icloudpd` (its help text says "Find My iPhone CommandLine Tool"). It is only useful to save your password in the system keyring or to delete it from there, see [Managing System Keyring](managing-system-keyring).

Both use the same keyring entry, but `icloud` keeps its session in a different folder (`pyicloud/<your login name>` in the system temporary folder, on Linux usually `/tmp/pyicloud/<your login name>`) and has no `--cookie-directory` option. Signing in or entering a 2FA code with `icloud` therefore does not sign in `icloudpd`.
~~~

## Multi-Factor Authentication

If your Apple account has two-factor authentication (multi-factor authentication, MFA) enabled,
you will be prompted for a code when you run the script. Two-factor authentication will expire after an interval set by Apple,
at which point you will have to re-authenticate. This interval is currently two months. Apple requires MFA for all new accounts.

You can receive an email notification when two-factor authentication expires by passing the
`--smtp-username` and `--smtp-password` options. Emails will be sent to `--smtp-username` by default,
or you can send to a different email address with `--notification-email`.

If you want to send notification emails using your Gmail account, and you have enabled two-factor authentication, you will need to generate an App Password at <https://myaccount.google.com/apppasswords>.

(mfa-providers)=
## MFA Providers

```{versionadded} 1.21.0
```

There are two ways to provide an MFA code to `icloudpd`:
- Using console
- Using web interface

The choice can be made with [`--mfa-provider`](mfa-provider-parameter) parameter.

Default: *console*
Other options: *webui*

(mfa-code-not-arriving)=
## The 2FA Code Doesn't Arrive

`icloudpd` asks Apple to send the code to your trusted Apple devices. If it doesn't show up there, the console can send it by SMS instead. If your account has trusted phone numbers, they are listed with a letter before the prompt, for example:

```
  a: (•••) •••-••12
Please enter two-factor authentication code or device index (a) to send SMS with a code:
```

Type the letter of a number (here `a`) instead of the code. `icloudpd` sends an SMS to that number and asks for the code that you received over SMS.

The [Web UI](webui) only has a field for the code and cannot send an SMS. If you normally use `webui`, sign in once in the console with [`--auth-only`](auth-only-parameter) and the same [`--cookie-directory`](cookie-directory-parameter); in Docker, add `-it` to `docker run` so you can type in the console.

## Access from Mainland China

Access to iCloud.com is blocked from mainland China. `icloudpd` can be used with the [`--domain cn`](domain-parameter) parameter to support downloading iCloud Photos from mainland China; however, people have reported mixed results with that parameter.

(fido)=
## FIDO

```{versionadded} 1.33.0
```

Accounts with security keys (FIDO, e.g. YubiKey) don't get a six-digit code. `icloudpd` asks for one of the registered keys instead, which must be plugged into the machine running `icloudpd`.

To use `icloudpd` on a machine without the key, sign in once with [`--auth-only`](auth-only-parameter) where the key is and copy the [`--cookie-directory`](cookie-directory-parameter) over.

The [`webui`](mfa-provider-parameter) MFA provider does not support security keys.

(adp)=
## ADP

```{versionadded} 1.33.0
```

Accounts with Advanced Data Protection (ADP) can be used with the [`--adp-web-access`](adp-web-access-parameter) parameter. It replays the consent sequence that icloud.com performs before showing photos, so it requires `Settings > [your name] > iCloud > Access iCloud Data on the Web` to be enabled on the Apple device.

The first run sends an approval notification to your Apple devices and waits up to two minutes for it to be accepted. Once approved, later runs (including from other machines or cookie directories) do not ask again.

Without the parameter, an ADP account fails with `ACCESS_DENIED`.

## Occasional Errors

Some authentication errors may be resolved by deleting the session folder, so that `icloudpd` signs in from scratch (you will be asked for a 2FA code again). [Example](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/772#issuecomment-1950963522)

The session folder is:
- the folder given with [`--cookie-directory`](cookie-directory-parameter), if you set one;
- otherwise `~/.pyicloud` (on Windows `C:\Users\<you>\.pyicloud`);
- inside Docker without `--cookie-directory`: `/root/.pyicloud` in the container.

To sign in again for one account only, delete just its two files: the file name is the Apple ID with everything except letters, digits and `_` removed, e.g. `jappleseedapplecom` and `jappleseedapplecom.session` for `jappleseed@apple.com`.

(password-providers)=
## Password Providers

```{versionadded} 1.20.0
```
```{versionadded} 1.21.0
WebUI support
```

Passwords for iCloud access can be supplied by the user in four ways:
- Using [`--password`](password-parameter) command line parameter
- Using keyring
- Using console
- Using web interface

It is possible to specify which of these four ways `icloudpd` should use, by specifying them with the [`--password-provider`](password-provider-parameter) parameter. More than one can be specified and the order
of providers matches the order they will be checked for a password. E.g., `--password-provider keyring --password-provider console` means that `icloudpd` will check the password in the keyring first and then, if no password is found, ask for a password in the console.

The keyring password provider, if specified, saves the valid password back into the keyring.

Console and Web UI are not compatible with each other. Console or WebUI providers, if specified, must be last in the list of providers because they cannot be skipped.

Default set and order of providers are: *parameter*, *keyring*, *console*

(managing-system-keyring)=
### Managing System Keyring

When `keyring` is one of the password providers (it is by default), `icloudpd` saves the password in the system keyring after a successful sign-in, so later runs don't ask for it again.

You can also store your password in the system keyring, or delete it from there, using the `icloud` command-line tool:

```
$ icloud --username jappleseed@apple.com
Enter iCloud password for jappleseed@apple.com:
Save password in keyring? [y/N]
```

If you would like to delete a password stored in your system keyring,
you can clear a stored password using the `--delete-from-keyring` command-line option:

``` sh
icloud --username jappleseed@apple.com --delete-from-keyring
```

After deleting the password, `icloud` continues and asks for the password to sign in. Press Ctrl+C if you only wanted to delete it.

```{note}
Use `icloud`, not `icloudpd`
```

### Keyring on Servers and in Docker

On a machine without a desktop keyring (a headless Linux server, a NAS, or the Docker image), the keyring falls back to a plain text file, `~/.local/share/python_keyring/keyring_pass.cfg` (in Docker: `/root/.local/share/python_keyring/keyring_pass.cfg` in the container). The password in that file is not encrypted.

If you don't want the password stored on disk, leave `keyring` out of the password providers, e.g. use `--password-provider console` or `--password-provider webui`. A password that is already stored can be deleted with `icloud --delete-from-keyring` (see above).

(multiple-accounts-and-configs)=
## Using Multiple Accounts and Config

`icloudpd` can process iCloud collections for multiple accounts or use multiple configs for one account. This is achieved by specifying the `--username` parameter multiple times: any options specified after `--username` will be applied to the mentioned user only. Parameters specified before the first `--username` work as defaults for all other user configs. Global app-wide settings can be specified anywhere. These are the global settings:
- `--help`, `--version`
- [`--use-os-locale`](use-os-locale-parameter)
- [`--only-print-filenames`](only-print-filenames-parameter)
- `--log-level`
- [`--no-progress-bar`](no-progress-bar-parameter)
- [`--domain`](domain-parameter)
- [`--watch-with-interval`](watch-with-interval-parameter)
- [`--password-provider`](password-provider-parameter)
- [`--mfa-provider`](mfa-provider-parameter)
- `--threads-num` (deprecated, has no effect)

All other parameters can be set per user.

### Example: using two user accounts

```
$ icloudpd --use-os-locale --cookie-directory ./cookies --username alice@apple.com --directory ./alice --username bob@apple.com --directory ./bob
```

Explanation

- `--use-os-locale` is a global parameter and can be used anywhere
- `--cookie-directory` is a default for both users; it is okay to use the same folder since sessions and cookies are stored in files based on the user name, so they would not collide
- `--directory ./alice` specifies that all photos for Alice will be downloaded into the ./alice folder
- `--directory ./bob` specifies that all photos for Bob will be downloaded into the ./bob folder

### Example: using two configs for one account

```
$ icloudpd --cookie-directory ./cookies --username alice@apple.com --directory ./photos --skip-videos --username alice@apple.com --directory ./videos --skip-photos --use-os-locale
```

Explanation

- `--cookie-directory` is a default for both configs
- `--directory ./photos --skip-videos` specifies that all photos for Alice will be downloaded into the ./photos folder
- `--directory ./videos --skip-photos` specifies that all videos for Alice will be downloaded into the ./videos folder
- `--use-os-locale` is a global parameter and can be used anywhere

```{versionadded} 1.32.0
```
