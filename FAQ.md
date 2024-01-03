# Nuances and Known Issues

## iCloud Authentication

### MFA

If your Apple account has two-factor authentication (multi-factor authentication, MFA) enabled,
you will be prompted for a code when you run the script. Two-factor authentication will expire after an interval set by Apple,
at which point you will have to re-authenticate. This interval is currently two months. Apple requires MFA for all new accounts.

You can receive an email notification when two-factor authentication expires by passing the
`--smtp-username` and `--smtp-password` options. Emails will be sent to `--smtp-username` by default,
or you can send to a different email address with `--notification-email`.

If you want to send notification emails using your Gmail account, and you have enabled two-factor authentication, you will need to generate an App Password at <https://myaccount.google.com/apppasswords>

### FIDO

Authentication to iCloud with hardware keys (FIDO) is not supported.

### ADP

Advanced Data Protection (ADP) for iCloud accounts is not supported because iCloudPD simulates web access, which is disabled with ADP.

### System Keyring

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

## Error on the First Run

When you run the script for the first time, you might see an error message like this:

``` plain
Bad Request (400)
```

This error often happens because your account hasn't used the iCloud API before, so Apple's servers need to prepare some information about your photos. This process can take around 5-10 minutes, so please wait a few minutes and try again.

If you are still seeing this message after 30 minutes, then please [open an issue on GitHub](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/new) and post the script output.

## Access from Mainland China

Access to iCloud.com is blocked from mainland China. `icloudpd` can be used with `--domain cn` parameter to support downloading iCloud phtotos from mainland China, however, people reported mixed results with that parameter.

## MacOS binary

`icloudpd` is available as Intel 64bit binary for MacOS, but works on ARM macs too (M1, M2).

Here are the steps to make it working:
- download binary from Github [Releases](https://github.com/icloud-photos-downloader/icloud_photos_downloader/releases) into desired local folder
- add executable flag by running `chmod +x icloudpd-1.17.3-macos-amd64`
- start it from the terminal: `icloudpd-1.17.3-macos-amd64`
- Apple will tell you that it cannot check for malicous software and refuse to run the app; click "Ok"
- Open "System Settings"/"Privacy & Security" and find `icloudpd-1.17.3-macos-amd64` as blocked app; Click "Allow"
- Start `icloudpd-1.17.3-macos-amd64` from the terminal again
- Apple will show another warning; click "Open"
- After that you can run `icloudpd-1.17.3-macos-amd64 --help` or any other supported command/option
