# iCloud Photos Downloader

* A command-line tool to download all your iCloud photos. 
* Works on Mac and Linux.
* Run it multiple times to download any new photos.


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
                        [--size=original | --size=medium | --size=thumb]
      ./download_photos -h | --help
      ./download_photos --version

    Options:
      --username=<username>     iCloud username (or email)
      --password=<password>     iCloud password (optional if saved in keyring)
      --size=<size>             Image size to download [default: original].
      -h --help                 Show this screen.
      --version                 Show version.

