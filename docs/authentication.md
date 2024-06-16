# iCloud Authentication

## Multi Factor Authentication

If your Apple account has two-factor authentication (multi-factor authentication, MFA) enabled,
you will be prompted for a code when you run the script. Two-factor authentication will expire after an interval set by Apple,
at which point you will have to re-authenticate. This interval is currently two months. Apple requires MFA for all new accounts.

You can receive an email notification when two-factor authentication expires by passing the
`--smtp-username` and `--smtp-password` options. Emails will be sent to `--smtp-username` by default,
or you can send to a different email address with `--notification-email`.

If you want to send notification emails using your Gmail account, and you have enabled two-factor authentication, you will need to generate an App Password at <https://myaccount.google.com/apppasswords>

## FIDO

Authentication to iCloud with hardware keys (FIDO) is not supported.

## ADP

Advanced Data Protection (ADP) for iCloud accounts is not supported because iCloudPD simulates web access, which is disabled with ADP.

## Occasional Errors

Some authentication errors may be resolved by clearing `.pycloud` subfolder in the user's home dir. [Example](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/772#issuecomment-1950963522)

## System Keyring

You can store your password in the system keyring using the `icloud` command-line tool:

``` plain
$ icloud --username jappleseed@apple.com
ICloud Password for jappleseed@apple.com:
Save password in keyring? (y/N)
```

If you have stored a password in the keyring, you will not be required to provide a password
when running the script.

If you would like to delete a password stored in your system keyring,
you can clear a stored password using the `--delete-from-keyring` command-line option:

``` sh
icloud --username jappleseed@apple.com --delete-from-keyring
```

```{note}
Use `icloud`, not `icloudpd`
```