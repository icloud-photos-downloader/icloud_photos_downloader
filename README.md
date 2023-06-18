# iCloud Photos Downloader [![Quality Checks](https://github.com/icloud-photos-downloader/icloud_photos_downloader/workflows/Quality%20Checks/badge.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/actions/workflows/quality-checks.yml) [![Multi Platform Docker Build](https://github.com/icloud-photos-downloader/icloud_photos_downloader/workflows/Docker%20Build/badge.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/actions/workflows/docker-build.yml) [![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

- A command-line tool to download all your iCloud photos.
- Works on Linux, Windows, and MacOS; laptop, desktop, and NAS
- Available as an executable for direct downloading and through package managers/ecosystems ([Docker](README_DOCKER.md), [PyPI](README_PYPI.md), Experimental: [Npm](README_NPM.md))
- Developed and maintained by volunteers (we are always looking for [help](CONTRIBUTING.md)). 

We aim to release new versions once a week (Friday), if there is something worth delivering.

## Install and Run

There are three ways to run `icloudpd`:
1. Download executable for your platform from the Github [Releases](https://github.com/icloud-photos-downloader/icloud_photos_downloader/releases) and run it
1. Use package manager to install, update, and, in some cases, run ([Docker](README_DOCKER.md), [PyPI](README_PYPI.md), Experimental: [Npm](README_NPM.md))
1. Build and run from the source

## Features

- Three modes of operation:
  - **Copy** - download new photos from iCloud (default mode)
  - **Sync** - download new photos from iCloud and delete local files that were removed in iCloud (`--auto-delete` option)
  - **Move** - download new photos from iCloud and delete photos in iCloud (`--delete-after-download` option)
- Support for Live Photos (image and video as separate files)
- Automatic de-duplication of photos with the same name
- One time download and an option to monitor for iCloud changes continuously (`--watch-with-interval` option)
- Optimizations for incremental runs (`--until-found` and `--recent` options)
- Photo meta data (EXIF) updates (`--set-exif-datetime` option)
- ... and many (use `--help` option to get full list)

## Experimental Mode

Some changes are added to the experimental mode before they graduate into the main package. [Details](EXPERIMENTAL.md)

## Usage

To keep your iCloud photo collection synchronized to your local system:

```
icloudpd --directory /data --username my@email.address --watch-with-interval 3600
```

Synchronization logic can be adjusted with command-line parameters. Run `icloudpd --help` to get full list.

## FAQ

Nuances of working with the iCloud or a specific operating system are collected in the [FAQ](FAQ.md). Also, check [Issues](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues).

## Contributing

Want to contribute to iCloud Photos Downloader? Awesome! Check out the [contributing guidelines](CONTRIBUTING.md) to get involved.
