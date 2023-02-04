# iCloud Photos Downloader [![Quality Checks](https://github.com/icloud-photos-downloader/icloud_photos_downloader/workflows/Quality%20Checks/badge.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/actions/workflows/quality-checks.yml) [![Multi Platform Docker Build](https://github.com/icloud-photos-downloader/icloud_photos_downloader/workflows/Docker%20Build/badge.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/actions/workflows/docker-build.yml) [![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

- A command-line tool to download all your iCloud photos.
- Works on Linux, Windows, and MacOS.
- Run as a [scheduled cron task](#cron-task) to keep a local backup of your photos and videos.

This tool is developed and maintained by volunteers (we are always looking for [help](CONTRIBUTING.md)...). We aim to release new versions once a week (Friday), if there is something worth delivering.

## Install

There are three ways to run `icloudpd`:
1. Download executable for your platform from the Github Release and run it
1. Use Docker to download and run the tool (requires Docker installed, e.g. [Docker Desktop](https://www.docker.com/products/docker-desktop/)
1. Run from the source (requires Python and `pip` installed)

### Download with Docker

Docker automatically pulls images from the remote repository if necessary. To download explicitely, e.g. to force version update, use:

```sh
docker pull icloudpd/icloudpd:1.8.1
```

### Running from the source

`icloudpd` is a Python package that can be installed using `pip`:

``` sh
pip install icloudpd
```

> If you need to install Python, see the [Appendix](#appendix) section for instructions.

## Usage

[//]: # (This is now only a copy&paste from --help output)

``` plain
Usage: icloudpd-linux <options>

  Download all iCloud photos to a local directory

Options:
  -d, --directory <directory>     Local directory that should be used for
                                  download
  -u, --username <username>       Your iCloud username or email address
  -p, --password <password>       Your iCloud password (default: use PyiCloud
                                  keyring or prompt for password)
  --cookie-directory </cookie/directory>
                                  Directory to store cookies for
                                  authentication (default: ~/.pyicloud)
  --size [original|medium|thumb]  Image size to download (default: original)
  --live-photo-size [original|medium|thumb]
                                  Live Photo video size to download (default:
                                  original)
  --recent INTEGER RANGE          Number of recent photos to download
                                  (default: download all photos)
  --until-found INTEGER RANGE     Download most recently added photos until we
                                  find x number of previously downloaded
                                  consecutive photos (default: download all
                                  photos)
  -a, --album <album>             Album to download (default: All Photos)
  -l, --list-albums               Lists the available albums
  --skip-videos                   Don't download any videos (default: Download
                                  all photos and videos)
  --skip-live-photos              Don't download any live photos (default:
                                  Download live photos)
  --force-size                    Only download the requested size (default:
                                  download original if size is not available)
  --auto-delete                   Scans the "Recently Deleted" folder and
                                  deletes any files found in there. (If you
                                  restore the photo in iCloud, it will be
                                  downloaded again.)
  --only-print-filenames          Only prints the filenames of all files that
                                  will be downloaded (not including files that
                                  are already downloaded.)(Does not download
                                  or delete any files.)
  --folder-structure <folder_structure>
                                  Folder structure (default: {:%Y/%m/%d}). If
                                  set to 'none' all photos will just be placed
                                  into the download directory
  --set-exif-datetime             Write the DateTimeOriginal exif tag from
                                  file creation date, if it doesn't exist.
  --smtp-username <smtp_username>
                                  Your SMTP username, for sending email
                                  notifications when two-step authentication
                                  expires.
  --smtp-password <smtp_password>
                                  Your SMTP password, for sending email
                                  notifications when two-step authentication
                                  expires.
  --smtp-host <smtp_host>         Your SMTP server host. Defaults to:
                                  smtp.gmail.com
  --smtp-port <smtp_port>         Your SMTP server port. Default: 587 (Gmail)
  --smtp-no-tls                   Pass this flag to disable TLS for SMTP (TLS
                                  is required for Gmail)
  --notification-email <notification_email>
                                  Email address where you would like to
                                  receive email notifications. Default: SMTP
                                  username
  --notification-script PATH      Runs an external script when two factor
                                  authentication expires. (path required:
                                  /path/to/my/script.sh)
  --log-level [debug|info|error]  Log level (default: debug)
  --no-progress-bar               Disables the one-line progress bar and
                                  prints log messages on separate lines
                                  (Progress bar is disabled by default if
                                  there is no tty attached)
  --threads-num INTEGER RANGE     Number of cpu threads -- deprecated. To be
                                  removed in future version
  --delete-after-download         Delete the photo/video after download it.
                                  The deleted items will be appear in the
                                  "Recently Deleted". Therefore, should not
                                  combine with --auto-delete option.
  --version                       Show the version and exit.
  -h, --help                      Show this message and exit.
```

Example:

``` sh
icloudpd --directory ./Photos \
--username testuser@example.com \
--password pass1234 \
--recent 500 \
--auto-delete
```

## Authentication

If your Apple account has two-factor authentication enabled,
you will be prompted for a code when you run the script.

Two-factor authentication will expire after an interval set by Apple,
at which point you will have to re-authenticate. This interval is currently two months.

Authentication cookies will be stored in a temp directory (`/tmp/pyicloud` on Linux, or `/var/tmp/...` on macOS.) This directory can be configured with the `--cookie-directory` option.

You can receive an email notification when two-factor authentication expires by passing the
`--smtp-username` and `--smtp-password` options. Emails will be sent to `--smtp-username` by default,
or you can send to a different email address with `--notification-email`.

If you want to send notification emails using your Gmail account, and you have enabled two-factor authentication, you will need to generate an App Password at <https://myaccount.google.com/apppasswords>

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

## Error on first run

When you run the script for the first time, you might see an error message like this:

``` plain
Bad Request (400)
```

This error often happens because your account hasn't used the iCloud API before, so Apple's servers need to prepare some information about your photos. This process can take around 5-10 minutes, so please wait a few minutes and try again.

If you are still seeing this message after 30 minutes, then please [open an issue on GitHub](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/new) and post the script output.

## Cron Task

You can run `icloudpd` using `cron` on platforms that support it:

- copy the example cron script from source tree, e.g. `cp cron_script.sh.example cron_script.sh`

- Update `cron_script.sh` with your username, password, and other options

- Edit your "crontab" with `crontab -e`, then add the following line:

``` plain
0 */6 * * * /path/to/cron_script.sh
```

Now the script will run every 6 hours to download any new photos and videos.

> If you provide SMTP credentials, the script will send an email notification
> whenever two-step authentication expires.

## Docker

This script is available in a Docker image: `docker pull icloudpd/icloudpd:1.8.1`

Usage (Downloads all photos to ./Photos):

```bash
docker run -it --rm --name icloudpd \
    -v $(pwd)/Photos:/data \
    -v $(pwd)/cookies:/cookies \
    -e TZ=America/Los_Angeles \
    icloudpd/icloudpd:1.8.1 \
    icloudpd --directory /data \
    --cookie-directory /cookies \
    --folder-structure {:%Y/%Y-%m-%d} \
    --username testuser@example.com \
    --password pass1234 \
    --size original \
    --recent 500 \
    --auto-delete
```

On Windows:

- use `%cd%` instead of `$(pwd)`
- or full path, e.g. `-v c:/photos/icloud:/data`

Building image locally from the source tree:

```bash
docker build . -t icloudpd:dev
docker run -it --rm icloudpd:latest icloudpd --version
```

## Appendix

### Install Python & pip

Note that `icloudpd` works with python 3.7+.

#### Windows

- [Download Python](https://www.python.org/downloads/windows/)

#### Mac

- Install [Homebrew](https://brew.sh/) (if not already installed):

``` sh
which brew > /dev/null 2>&1 || /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
```

- Install Python (includes `pip`):

``` sh
brew install python
```

> Alternatively, you can [download the latest Python 3.x installer for Mac](https://www.python.org/downloads/mac-osx/).

#### Linux (Ubuntu)

``` sh
sudo apt-get update
sudo apt-get install -y python
```

### Install Docker Desktop

To install Docker with user interface on Windows or Mac, download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/)

## Contributing

Want to contribute to iCloud Photos Downloader? Awesome! Check out the [contributing guidelines](CONTRIBUTING.md) to get involved.
