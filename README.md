# iCloud Photos Downloader

* A command-line tool to download all your iCloud photos.
* Works on Mac, Linux, and Windows.
* Run it multiple times to download any new photos.

### Why?

* I use the Photos app on my MacBook, set to "Optimize Mac Storage". It stores full-resolution images in iCloud, and only stores thumbnails on my computer until they are requested.
* I want to download a copy of all my photos onto my Linux PC, because:
  * I use Plex instead of an Apple TV. Now I can display photo slideshows with Plex.
  * I like having a backup of all my photos on my own hard-drive.
* I only want to download the "medium" size of all my photos. They save some space while still being big enough for slideshows. If "medium" is not available, then fall back to downloading the original size.


### Installation

    # Clone the repo somewhere
    git clone https://github.com/ndbroadbent/icloud_photos_downloader.git
    cd icloud_photos_downloader

    # Install dependencies (Linux)
    # Note: This will install a fork of the latest pyicloud with some bug fixes
    # Also note that you may not need sudo for `pip install`.
    sudo pip install -r requirements.txt


### Authentication

If your account has two-factor authentication enabled,
you will be prompted for a code when you run the script.

Two-factor authentication will expire after an interval set by Apple,
at which point you will have to re-authenticate. This interval is currently two months.

You can receive an email notification when two-factor authentication expires by passing the
`--smtp-username` and `--smtp-password` options. Emails will be sent to `--smtp-username` by default,
or you can send to a different email address with `--notification-email`.

If you want to send notification emails using your Gmail account, and you have enabled two-factor authentication, you will need to generate an App Password at https://myaccount.google.com/apppasswords


#### System Keyring

You can store your password in the system keyring using the `icloud` command-line tool
(installed with the `pyicloud` dependency):

    $ icloud --username=jappleseed@apple.com
    ICloud Password for jappleseed@apple.com:
    Save password in keyring? (y/N)

If you have stored a password in the keyring, you will not be required to provide a password
when running the script.

If you would like to delete a password stored in your system keyring,
you can clear a stored password using the `--delete-from-keyring` command-line option:

    $ icloud --username=jappleseed@apple.com --delete-from-keyring


### Usage

    $ ./download_photos.py <download_directory>
                           --username=<username>
                           [--password=<password>]
                           [--size=(original|medium|thumb)]
                           [--recent <integer>]
                           [--until-found <integer>]
                           [--download-videos]
                           [--auto-delete]
                           [--only-print-filenames]
                           [--folder-structure=({:%Y/%m/%d})]
                           [--set-exif-datetime]
                           [--smtp-username <smtp_username>]
                           [--smtp-password <smtp_password>]
                           [--smtp-host <smtp_host>]
                           [--smtp-port <smtp_port>]
                           [--smtp-no-tls]
                           [--notification-email <notification_email>]

    Options:
        --username <username>           Your iCloud username or email address
        --password <password>           Your iCloud password (default: use PyiCloud
                                        keyring or prompt for password)
        --size [original|medium|thumb]  Image size to download (default: original)
        --recent INTEGER RANGE          Number of recent photos to download
                                        (default: download all photos)
        --until-found INTEGER RANGE     Download most recently added photos until we
                                        find x number of previously downloaded
                                        consecutive photos (default: download all
                                        photos)
        --download-videos               Download both videos and photos (default:
                                        only download photos)
        --force-size                    Only download the requested size (default:
                                        download original if size is not available)
        --auto-delete                   Scans the "Recently Deleted" folder and
                                        deletes any files found in there. (If you
                                        restore the photo in iCloud, it will be
                                        downloaded again.)
        --only-print-filenames          Only prints the filenames of all files that
                                        will be downloaded. (Does not download any
                                        files.)
        --folder-structure              Folder structure. Default is {:%Y/%m/%d}.
        --set-exif-datetime             Write the DateTimeOriginal exif tag from file creation date, if it doesn't exist.
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
        -h, --help                      Show this message and exit.


Example:

    $ ./download_photos.py ./Photos \
        --username=testuser@example.com \
        --password=pass1234 \
        --size=original \
        --recent 500 \
        --auto-delete


### Error on first run

The first time you run the script, you will probably see an error message like this:

```
Bad Request (400)
```

This error usually means that Apple's servers are getting ready to send you data about your photos.
This process can take around 5-10 minutes, so please wait a few minutes, then try again.

(If you are still seeing this message after 30 minutes, then please open an issue on GitHub.)


### Run once every 3 hours using Cron

    cp cron_script.sh.example cron_script.sh

* Edit cron_script.sh with your username, password, and other options

* Run `crontab -e`, and add the following line:

```
0 */3 * * * /path/to/icloud_photos_downloader/cron_script.sh
```

### Docker

* Build the image:

```
$ git clone https://github.com/ndbroadbent/icloud_photos_downloader.git
$ cd icloud_photos_downloader.git/docker
$ docker build -t icloud_photos_downloader .
```

* Usage:

```
$ docker run -it --rm --name icloud -v $(pwd)/Photos:/data icloud_photos_downloader ./download_photos.py \
    --username=testuser@example.com \
    --password=pass1234 \
    --size=original \
    --recent 500 \
    --auto-delete \
    /data
```


### Support Development

<a href='https://ko-fi.com/ndbroadbent' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://az743702.vo.msecnd.net/cdn/kofi4.png?v=0' border='0' alt='Buy Me a Coffee' /></a>

* *Bitcoin (BTC)*: 15eSc6JiwBtxte9zak44ZFhw9bkKWaMGAe
* *Bitcoin Cash (BCH)*: 157a1zxtY7vozdkrom2aSiVu4oZ6JkXpSU
* *Ethereum (ETH)*: 0x080300A117758EC601b7b6c501afE3571E5cA1c3
* *Litecoin (LTC)*: LP7pURasgBVU8FMh4Rx2WW45iWCnMoGDMD
