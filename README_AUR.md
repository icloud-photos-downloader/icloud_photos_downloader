# iCloud Photos Downloader [![Quality Checks](https://github.com/icloud-photos-downloader/icloud_photos_downloader/workflows/Quality%20Checks/badge.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/actions/workflows/quality-checks.yml) [![Multi Platform Docker Build](https://github.com/icloud-photos-downloader/icloud_photos_downloader/workflows/Docker%20Build/badge.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/actions/workflows/docker-build.yml) [![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE.md)

A command-line tool to download all your iCloud photos.

## Install

AUR packages can be installed on Arch Linux. Installation can be done [manually](https://wiki.archlinux.org/title/Arch_User_Repository#Installing_and_upgrading_packages) or with the use of an [AUR helper](https://wiki.archlinux.org/title/AUR_helpers).

The manual process would look like this:

``` sh
git clone https://aur.archlinux.org/icloudpd-bin.git
cd icloudpd-bin
makepkg -sirc
```

With the use of the AUR helper e.g. [yay](https://github.com/Jguer/yay) the installation process would look like this:

``` sh
yay -S icloudpd-bin
```

## Usage

Synchronization logic can be adjusted with command-line parameters. Run the following to get full list:

``` sh 
icloudpd --help
``` 

## More

See [Project page](https://github.com/icloud-photos-downloader/icloud_photos_downloader/) for more details.
