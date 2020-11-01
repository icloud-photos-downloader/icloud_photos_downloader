# Community Maintained

I hope this tool is useful for you! Unfortunately I don't use it personally anymore, and I don't want to spend lots of time working on it. Please let me know if you want to help maintain it and respond to the GitHub issues and pull requests.

However, I'm happy to accept any pull requests to keep the project working if the code is high quality and has 100% test coverage. Thanks a lot for your help!

---------

[![Build Status](https://travis-ci.org/ndbroadbent/icloud_photos_downloader.svg?branch=master)](https://travis-ci.org/ndbroadbent/icloud_photos_downloader)
[![Coverage Status](https://coveralls.io/repos/github/ndbroadbent/icloud_photos_downloader/badge.svg?branch=master)](https://coveralls.io/github/ndbroadbent/icloud_photos_downloader?branch=master)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

# iCloud Photos Downloader

- A command-line tool to download all your iCloud photos.
- Works on Linux, Windows, and MacOS.
- Run as a [scheduled cron task](#cron-task) to keep a local backup of your photos and videos.

## Install

`icloudpd` is a Python package that can be installed using `pip`:

```
pip install icloudpd
```

> If you need to install Python, see the [Requirements](#requirements) section for instructions.

## Usage

    $ icloudpd <download_directory>
               --username <username>
               [-p, --password <password>]
               [-d, --directory <directory>]
               [--cookie-directory </cookie/directory>]
               [--size (original|medium|thumb)]
               [--live-photo-size (original|medium|thumb)]
               [--recent <integer>]
               [--until-found <integer>]
               [-a, --album <album>]
               [-l, --list-albums]
               [--skip-videos]
               [--skip-live-photos]
               [--force-size]
               [--auto-delete]
               [--only-print-filenames]
               [--folder-structure ({:%Y/%m/%d})]
               [--set-exif-datetime]
               [--smtp-username <smtp_username>]
               [--smtp-password <smtp_password>]
               [--smtp-host <smtp_host>]
               [--smtp-port <smtp_port>]
               [--smtp-no-tls]
               [--notification-email <notification_email>]
               [--notification-script PATH]
               [--server-secretkey <server_secretkey>]
               [--log-level (debug|info|error)]
               [--no-progress-bar]
               [--threads-num <threads>]

    Options:
        --username <username>           Your iCloud username or email address
        --password <password>           Your iCloud password (default: use PyiCloud
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
        -l, --list-albums               Lists the avaliable albums
        --skip-videos                   Don't download any videos (default: Download
                                        both photos and videos)
        --skip-live-photos              Don't download any live photos (default:
                                        Download live photos)
        --force-size                    Only download the requested size (default:
                                        download original if size is not available)
        --auto-delete                   Scans the "Recently Deleted" folder and
                                        deletes any files found in there. (If you
                                        restore the photo in iCloud, it will be
                                        downloaded again.)
        --only-print-filenames          Only prints the filenames of all files that
                                        will be downloaded. (Does not download any
                                        files.)
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
        --server-secretkey              [serverChan](http://sc.ftqq.com/3.version) wechat notifaction
        --log-level [debug|info|error]  Log level (default: debug)
        --no-progress-bar               Disables the one-line progress bar and
                                        prints log messages on separate lines
                                        (Progress bar is disabled by default if
                                        there is no tty attached)
        --threads-num INTEGER RANGE     Number of cpu threads -- deprecated. To be removed in future version
        --version                       Show the version and exit.
        -h, --help                      Show this message and exit.

Example:

    $ icloudpd --directory ./Photos \
        --username testuser@example.com \
        --password pass1234 \
        --recent 500 \
        --auto-delete

## Requirements

- Python 3.6+
- pip

### Install Python & pip

#### Windows

- [Download Python 3.x](https://www.python.org/downloads/windows/)

#### Mac

- Install [Homebrew](https://brew.sh/) (if not already installed):

```
which brew > /dev/null 2>&1 || /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
```

- Install Python (includes `pip`):

```
brew install python
```

> Alternatively, you can [download the latest Python 3.x installer for Mac](https://www.python.org/downloads/mac-osx/).

#### Linux (Ubuntu)

```
sudo apt-get update
sudo apt-get install -y python
```

## Authentication

If your Apple account has two-factor authentication enabled,
you will be prompted for a code when you run the script.

Two-factor authentication will expire after an interval set by Apple,
at which point you will have to re-authenticate. This interval is currently two months.

Authentication cookies will be stored in a temp directory (`/tmp/pyicloud` on Linux, or `/var/tmp/...` on MacOS.) This directory can be configured with the `--cookie-directory` option.

You can receive an email notification when two-factor authentication expires by passing the
`--smtp-username` and `--smtp-password` options. Emails will be sent to `--smtp-username` by default,
or you can send to a different email address with `--notification-email`.

If you want to send notification emails using your Gmail account, and you have enabled two-factor authentication, you will need to generate an App Password at <https://myaccount.google.com/apppasswords>

### System Keyring

You can store your password in the system keyring using the `icloud` command-line tool
(installed with the `pyicloud` dependency):

    $ icloud --username jappleseed@apple.com
    ICloud Password for jappleseed@apple.com:
    Save password in keyring? (y/N)

If you have stored a password in the keyring, you will not be required to provide a password
when running the script.

If you would like to delete a password stored in your system keyring,
you can clear a stored password using the `--delete-from-keyring` command-line option:

    $ icloud --username jappleseed@apple.com --delete-from-keyring

## Error on first run

When you run the script for the first time, you might see an error message like this:

```
Bad Request (400)
```

This error often happens because your account hasn't used the iCloud API before, so Apple's servers need to prepare some information about your photos. This process can take around 5-10 minutes, so please wait a few minutes and try again.

If you are still seeing this message after 30 minutes, then please [open an issue on GitHub](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/new) and post the script output.

## Cron Task

Follow these instructions to run `icloudpd` as a scheduled cron task.

```
# Clone the git repo somewhere
git clone https://github.com/icloud-photos-downloader/icloud_photos_downloader.git
cd icloud_photos_downloader

# Copy the example cron script
cp cron_script.sh.example cron_script.sh
```

- Update `cron_script.sh` with your username, password, and other options

- Edit your "crontab" with `crontab -e`, then add the following line:

```
0 */6 * * * /path/to/icloud_photos_downloader/cron_script.sh
```

Now the script will run every 6 hours to download any new photos and videos.

> If you provide SMTP credentials, the script will send an email notification
> whenever two-step authentication expires.

## Docker

This script is available in a Docker image: `docker pull icloudpd/icloudpd`

Usage:

```bash
# Downloads all photos to ./Photos

$ docker pull icloudpd/icloudpd
$ docker run -it --rm --name icloud -v $(pwd)/Photos:/data icloudpd/icloudpd:latest \
    -v $(pwd)/cookies:/cookies \
    -e TZ=America/Los_Angeles \
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

Building image locally:
```bash
$ docker build . -t icloudpd
$ docker run -it --rm icloudpd:latest icloudpd --version
```

## Contributing

Install dependencies:

```
sudo pip install -r requirements.txt
sudo pip install -r requirements-test.txt
```

Run tests:

```
pytest
```

Before submitting a pull request, please check the following:

- All tests pass
  - Run `./scripts/test`
- 100% test coverage
  - After running `./scripts/test`, you will see the test coverage results in the output
  - You can also open the HTML report at: `./htmlcov/index.html`
- Code is formatted with [autopep8](https://github.com/hhatto/autopep8)
  - Run `./scripts/format`
- No [pylint](https://www.pylint.org/) errors
  - Run `./scripts/lint` (or `pylint icloudpd`)
- If you've added or changed any command-line options,
  please update the [Usage](#usage) section in the README.

If you need to make any changes to the `pyicloud` library,
`icloudpd` uses a fork of this library that has been renamed to `pyicloud-ipd`.
Please clone my [pyicloud fork](https://github.com/icloud-photos-downloader/pyicloud)
and check out the [pyicloud-ipd](https://github.com/icloud-photos-downloader/pyicloud/tree/pyicloud-ipd)
branch. PRs should be based on the `pyicloud-ipd` branch and submitted to
[icloud-photos-downloader/pyicloud](https://github.com/icloud-photos-downloader/pyicloud).

### Building the Docker image

```
$ git clone https://github.com/icloud-photos-downloader/icloud_photos_downloader.git
$ cd icloud_photos_downloader
$ docker build -t icloudpd/icloudpd .
```
