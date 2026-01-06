# iCloud Photos Downloader [![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE.md)

> **Note:** This is a fork of the original [iCloud Photos Downloader](https://github.com/icloud-photos-downloader/icloud_photos_downloader) project with additional features including Telegram bot integration for remote control and authentication.

- A command-line tool to download all your iCloud photos.
- Works on Linux, Windows, and macOS; laptop, desktop, and NAS
- Available as an executable for direct downloading and through package managers/ecosystems ([Docker](https://icloud-photos-downloader.github.io/icloud_photos_downloader/install.html#docker), [PyPI](https://icloud-photos-downloader.github.io/icloud_photos_downloader/install.html#pypi), [AUR](https://icloud-photos-downloader.github.io/icloud_photos_downloader/install.html#aur), [npm](https://icloud-photos-downloader.github.io/icloud_photos_downloader/install.html#npm))
- **Additional features in this fork:**
  - Telegram bot integration for remote control (`/sync`, `/syncall`, `/stop`, `/status`, `/auth` commands)
  - Telegram-based MFA authentication (no SSH required for cookie renewal)
  - Automatic authentication expiration detection and notifications
- Based on the original project developed and maintained by volunteers (we are always looking for [help](CONTRIBUTING.md)). 

See [Documentation](https://icloud-photos-downloader.github.io/icloud_photos_downloader/) for more details. Also, check [Issues](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues)

We aim to release new versions once a week (Friday), if there is something worth delivering.

## iCloud Prerequisites

To make iCloud Photo Downloader work, ensure the iCloud account is configured with the following settings, otherwise Apple Servers will return an ACCESS_DENIED error:

- **Enable Access iCloud Data on the Web:** On your iPhone / iPad, enable `Settings > Apple ID > iCloud > Access iCloud Data on the Web`
- **Disable Advanced Data Protection:** On your iPhone /iPad disable `Settings > Apple ID > iCloud > Advanced Data Protection`


## Install and Run

There are three ways to run `icloudpd`:
1. Download executable for your platform from the GitHub [Release](https://github.com/icloud-photos-downloader/icloud_photos_downloader/releases/tag/v1.32.2) and run it
1. Use package manager to install, update, and, in some cases, run ([Docker](https://icloud-photos-downloader.github.io/icloud_photos_downloader/install.html#docker), [PyPI](https://icloud-photos-downloader.github.io/icloud_photos_downloader/install.html#pypi), [AUR](https://icloud-photos-downloader.github.io/icloud_photos_downloader/install.html#aur), [npm](https://icloud-photos-downloader.github.io/icloud_photos_downloader/install.html#npm))
1. Build and run from the source

See [Documentation](https://icloud-photos-downloader.github.io/icloud_photos_downloader/install.html) for more details

## Features

<!-- start features -->

- Three modes of operation:
  - **Copy** - download new photos from iCloud (default mode)
  - **Sync** - download new photos from iCloud and delete local files that were removed in iCloud (`--auto-delete` option)
  - **Move** - download new photos from iCloud and delete photos in iCloud (`--keep-icloud-recent-days` option)
- Support for Live Photos (image and video as separate files) and RAW images (including RAW+JPEG)
- Automatic de-duplication of photos with the same name
- One time download and an option to monitor for iCloud changes continuously (`--watch-with-interval` option)
- Optimizations for incremental runs (`--until-found` and `--recent` options)
- Photo metadata (EXIF) updates (`--set-exif-datetime` option)
- ... and many more (use `--help` option to get full list)

<!-- end features -->

## Experimental Mode

Some changes are added to the experimental mode before they graduate into the main package. [Details](EXPERIMENTAL.md)

## Usage

To keep your iCloud photo collection synchronized to your local system:

```
icloudpd --directory /data --username my@email.address --watch-with-interval 3600
```

> [!IMPORTANT]
> It is `icloudpd`, not `icloud` executable

> [!TIP]
> Synchronization logic can be adjusted with command-line parameters. Run `icloudpd --help` to get full list.

To independently create and authorize a session (and complete 2SA/2FA validation if needed) on your local system:

```
icloudpd --username my@email.address --password my_password --auth-only
```
> [!TIP]
> This feature can also be used to check and verify that the session is still authenticated. 

## Contributing

Want to contribute to iCloud Photos Downloader? Awesome! Check out the [contributing guidelines](CONTRIBUTING.md) to get involved.
