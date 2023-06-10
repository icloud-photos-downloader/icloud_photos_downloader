# iCloud Photos Downloader [![Quality Checks](https://github.com/icloud-photos-downloader/icloud_photos_downloader/workflows/Quality%20Checks/badge.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/actions/workflows/quality-checks.yml) [![Multi Platform Docker Build](https://github.com/icloud-photos-downloader/icloud_photos_downloader/workflows/Docker%20Build/badge.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/actions/workflows/docker-build.yml) [![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE.md)

A command-line tool to download all your iCloud photos.

## Install

``` sh
pip install icloudpd
```

## Usage

``` sh
icloudpd --directory /data --username my@email.address --watch-with-interval 3600
```

Synchronization logic can be adjusted with command-line parameters. Run the following to get full list:

``` sh 
icloudpd --help
``` 

## Getting Python & Pip

You can get Python with accompanying Pip from [Official site](https://www.python.org/downloads/).

### Alternative for Mac

Install [Homebrew](https://brew.sh/) (if not already installed):

``` sh
which brew > /dev/null 2>&1 || /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
```

Install Python (includes `pip`):

``` sh
brew install python
```

### Alternative for Linux (Ubuntu)

``` sh
sudo apt-get update
sudo apt-get install -y python
```

## More

See [Project page](https://github.com/icloud-photos-downloader/icloud_photos_downloader/) for more details.
