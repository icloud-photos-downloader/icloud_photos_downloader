# iCloud Photos Downloader

* A command-line tool to download all your iCloud photos.
* Works on Mac and Linux.
* Run it multiple times to download any new photos.


### Motivation

* I use the Photos app on my MacBook, set to "Optimize Mac Storage". It stores full-resolution images in iCloud, and only stores thumbnails on my computer until they are requested.
* I wanted to download a copy of all my photos onto my Linux PC. I also want to keep them updated.
* I only want to download the "medium" size of photos whenever possible. They save some space while still being big enough for slideshows. If "medium" is not available, then fall back to downloading the original size.


### Installation

    # Clone the repo somewhere
    git clone https://github.com/ndbroadbent/icloud_photos_downloader.git
    cd icloud_photos_downloader

    # Install dependencies
    sudo pip install -r requirements.txt


### Authentication

*(Taken from [the pyicloud docs](https://github.com/picklepete/pyicloud#authentication))*

You can store your password in the system keyring using the `icloud` command-line tool
(installed with the `pyicloud` dependency):

    >>> icloud --username=jappleseed@apple.com
    ICloud Password for jappleseed@apple.com:
    Save password in keyring? (y/N)

If you have stored a password in the keyring, you will not be required to provide a password
when running the script.

If your account has two-factor authentication enabled, you will be prompted for a code on the first run.

If you would like to delete a password stored in your system keyring,
you can clear a stored password using the `--delete-from-keyring` command-line option:

    >>> icloud --username=jappleseed@apple.com --delete-from-keyring


Note: Both regular login and two-factor authentication will expire after an interval set by Apple,
at which point you will have to re-authenticate. This interval is currently two months.


### Usage

    ./download_photos --username=<username> [--password=<password>] <download_directory>
    ./download_photos --username=<username> [--password=<password>] <download_directory>
                      [--size=(original|medium|thumb)]
    ./download_photos -h | --help
    ./download_photos --version


    Options:
      --username <username>           Your iCloud username or email address
      --password <password>           Your iCloud password (leave blank if stored in keyring)
      --size [original|medium|thumb]  Image size to download (default: original)
      --download-videos               Download both videos and photos (default: only download photos)
      --force-size                    Only download the requested size (default: download original if
                                      requested size is not available)
      -h, --help                      Show this message and exit.



### Run once an hour using Cron

    cp cron_script.sh.example cron_script.sh

* Edit cron_script.sh with your username, password, and other options

* Run `crontab -e`, and add the following line:

```
0 * * * * /path/to/icloud_photos_downloader/cron_script.sh
```

Change to `0 */3 * * *` if you want to run every 3 hours, etc.
