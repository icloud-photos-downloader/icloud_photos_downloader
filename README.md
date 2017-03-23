# iCloud Photos Downloader

* A command-line tool to download all your iCloud photos.
* Works on Mac and Linux.
* Run it multiple times to download any new photos.

# PLEASE NOTE

There's currently a bug in the [pyicloud](https://github.com/picklepete/pyicloud) library, where recent photos aren't being updated. You can install a fixed version with this command:

```bash
sudo pip install git+https://github.com/torarnv/pyicloud.git@photos-update
```


### Motivation

* I use the Photos app on my MacBook, set to "Optimize Mac Storage". It stores full-resolution images in iCloud, and only stores thumbnails on my computer until they are requested.
* I wanted to download a copy of all my photos onto my Linux PC, because:
  * I use Plex, which doesn't integrate with iCloud. So now I can display photo slideshows on my TV.
  * I just like having a backup of all my photos on my own hard-drive.
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

    $ icloud --username=jappleseed@apple.com
    ICloud Password for jappleseed@apple.com:
    Save password in keyring? (y/N)

If you have stored a password in the keyring, you will not be required to provide a password
when running the script.

If your account has two-factor authentication enabled, you will be prompted for a code on the first run.

If you would like to delete a password stored in your system keyring,
you can clear a stored password using the `--delete-from-keyring` command-line option:

    $ icloud --username=jappleseed@apple.com --delete-from-keyring


Note: Both regular login and two-factor authentication will expire after an interval set by Apple,
at which point you will have to re-authenticate. This interval is currently two months.


### Usage

    ./download_photos --username=<username> [--password=<password>] <download_directory>
    ./download_photos --username=<username> [--password=<password>] <download_directory>
                      [--size=(original|medium|thumb)]
                      --auto-delete
    ./download_photos -h | --help
    ./download_photos --version


    Options:
      --username <username>           Your iCloud username or email address
      --password <password>           Your iCloud password (leave blank if stored in keyring)
      --size [original|medium|thumb]  Image size to download (default: original)
      --download-videos               Download both videos and photos (default: only download photos)
      --force-size                    Only download the requested size (default: download original if
                                      requested size is not available)
      --auto-delete                   Scans the "Recently Deleted" folder and deletes any files found in there.
                                      If you restore the photo in iCloud, it will be downloaded again.
      -h, --help                      Show this message and exit.

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
