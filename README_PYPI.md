# iCloud Photos Downloader [![Quality Checks](https://github.com/icloud-photos-downloader/icloud_photos_downloader/workflows/Quality%20Checks/badge.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/actions/workflows/quality-checks.yml) [![Multi Platform Docker Build](https://github.com/icloud-photos-downloader/icloud_photos_downloader/workflows/Docker%20Build/badge.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/actions/workflows/docker-build.yml) [![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE.md)

A command-line tool to download all your iCloud photos.

## Install

``` sh
pip install icloudpd
```

### Windows

``` sh
pip install icloudpd --user
```

Plus add `C:\Users\<YourUserAccountHere>\AppData\Roaming\Python\Python<YourPythonVersionHere>\Scripts` to PATH. The exact path will be given at the end of `icloudpd` installation.

### MacOS

Add `/Users/<YourUserAccountHere>/Library/Python/<YourPythonVersionHere>/bin` to PATH. The exact path will be given at the end of `icloudpd` installation.

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

### Alternatives for Mac

#### Command Line Tools from Apple

Apple provices Python & Pip as part of the Command Line Tools for XCode. They can be downloaded from Apple Developer portal or installed with 

``` sh
xcode-select --install
```

Use `pip3` to install `icloudpd`:

``` sh
pip3 install icloudpd
```

#### Homebrew package manager

Homebrew is open source package manager for MacOS. Install [Homebrew](https://brew.sh/) (if not already installed):

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
