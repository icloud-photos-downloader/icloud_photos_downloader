#!/usr/bin/env python
import click
import os
import sys
import socket
import requests
import time
from tqdm import tqdm
from dateutil.parser import parse
import pyicloud

# For retrying connection after timeouts and errors
MAX_RETRIES = 5
WAIT_SECONDS = 5


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
@click.command(context_settings=CONTEXT_SETTINGS, options_metavar='<options>')
@click.argument('directory', type=click.Path(exists=True), metavar='<directory>')
@click.option('--username',
              help='Your iCloud username or email address',
              metavar='<username>',
              prompt='iCloud username/email')
@click.option('--password',
              help='Your iCloud password (leave blank if stored in keyring)',
              metavar='<password>')
@click.option('--size',
              help='Image size to download (default: original)',
              type=click.Choice(['original', 'medium', 'thumb']),
              default='original')
@click.option('--download-videos',
              help='Download both videos and photos (default: only download photos)',
              is_flag=True)
@click.option('--force-size',
              help='Only download the requested size ' + \
                   '(default: download original if requested size is not available)',
              is_flag=True)
@click.option('--auto-delete',
              help='Scans the "Recently Deleted" folder and deletes any files found in there. ' + \
                   'If you restore the photo in iCloud, it will be downloaded again.',
              is_flag=True)


def download(directory, username, password, size, download_videos, force_size, auto_delete):
    """Download all iCloud photos to a local directory"""

    icloud = authenticate(username, password)

    # From: https://github.com/torarnv/pyicloud/tree/photos-update
    print "Updating photos..."
    try:
        icloud.photos.update()
    except pyicloud.exceptions.PyiCloudAPIResponseError as exception:
        print exception
        print
        print(
            "This error usually means that Apple's servers are getting ready "
            "to send you data about your photos.")
        print(
            "This process can take around 5-10 minutes, and it only happens when "
            "you run the script for the very first time.")
        print "Please wait a few minutes, then try again."
        print
        print(
            "(If you are still seeing this message after 30 minutes, "
            "then please open an issue on GitHub.)")
        print
        sys.exit(1)

    print "Looking up all photos..."
    all_photos = icloud.photos.all
    photos_count = len(all_photos.photos)

    directory = directory.rstrip('/')

    if download_videos:
        print "Downloading %d %s photos and videos to %s/ ..." % (photos_count, size, directory)
    else:
        print "Downloading %d %s photos to %s/ ..." % (photos_count, size, directory)

    progress_bar = tqdm(all_photos, total=photos_count)

    for photo in progress_bar:
        for _ in range(MAX_RETRIES):
            try:
                if not download_videos \
                    and not photo.filename.lower().endswith(('.png', '.jpg', '.jpeg')):

                    progress_bar.set_description(
                        "Skipping %s, only downloading photos." % photo.filename)
                    continue

                created_date = None
                try:
                    created_date = parse(photo.created)
                except TypeError:
                    print "Could not find created date for photo!"
                    continue

                date_path = '{:%Y/%m/%d}'.format(created_date)
                download_dir = '/'.join((directory, date_path))

                if not os.path.exists(download_dir):
                    os.makedirs(download_dir)

                download_photo(photo, size, force_size, download_dir, progress_bar)
                break

            except (requests.exceptions.ConnectionError, socket.timeout):
                tqdm.write('Connection failed, retrying after %d seconds...' % WAIT_SECONDS)
                time.sleep(WAIT_SECONDS)

        else:
            tqdm.write("Could not process %s! Maybe try again later." % photo.filename)

    print "All photos have been downloaded!"

    if auto_delete:
        print "Deleting any photos found in 'Recently Deleted'..."

        recently_deleted_photos = icloud.photos.albums['Recently Deleted']

        for photo in recently_deleted_photos:
            if not download_videos \
                and not photo.filename.lower().endswith(('.png', '.jpg', '.jpeg')):

                print "Skipping %s, only downloading photos." % photo.filename
                continue

            created_date = parse(photo.created)
            date_path = '{:%Y/%m/%d}'.format(created_date)
            download_dir = '/'.join((directory, date_path))

            filename = filename_with_size(photo, size)
            path = '/'.join((download_dir, filename))

            if os.path.exists(path):
                print "Deleting %s!" % path
                os.remove(path)


def authenticate(username, password):
    print "Signing in..."

    if password:
      icloud = pyicloud.PyiCloudService(username, password)
    else:
      icloud = pyicloud.PyiCloudService(username)

    if icloud.requires_2fa:
        print "Two-factor authentication required. Your trusted devices are:"

        devices = icloud.trusted_devices
        for i, device in enumerate(devices):
            print "  %s: %s" % (i, device.get('deviceName',
                "SMS to %s" % device.get('phoneNumber')))

        device = click.prompt('Which device would you like to use?', default=0)
        device = devices[device]
        if not icloud.send_verification_code(device):
            print "Failed to send verification code"
            sys.exit(1)

        code = click.prompt('Please enter validation code')
        if not icloud.validate_verification_code(device, code):
            print "Failed to verify verification code"
            sys.exit(1)

    return icloud


def truncate_middle(s, n):
    if len(s) <= n:
        return s
    n_2 = int(n) // 2 - 2
    n_1 = n - n_2 - 4
    if n_2 < 1: n_2 = 1
    return '{0}...{1}'.format(s[:n_1], s[-n_2:])

def filename_with_size(photo, size):
    return photo.filename.encode('utf-8') \
        .decode('ascii', 'ignore').replace('.', '-%s.' % size)

def download_photo(photo, size, force_size, download_dir, progress_bar):
    # Strip any non-ascii characters.
    filename = filename_with_size(photo, size)
    download_path = '/'.join((download_dir, filename))

    truncated_filename = truncate_middle(filename, 24)
    truncated_path = truncate_middle(download_path, 72)

    if os.path.isfile(download_path):
        progress_bar.set_description("%s already exists." % truncated_path)
        return

    # Fall back to original if requested size is not available
    if size not in photo.versions and not force_size and size != 'original':
        download_photo(photo, 'original', True, download_dir, progress_bar)
        return

    progress_bar.set_description("Downloading %s to %s" % (truncated_filename, truncated_path))

    for _ in range(MAX_RETRIES):
        try:
            download_url = photo.download(size)

            if download_url:
                with open(download_path, 'wb') as file:
                    for chunk in download_url.iter_content(chunk_size=1024):
                        if chunk:
                            file.write(chunk)
                break

            else:
                tqdm.write(
                    "Could not find URL to download %s for size %s!" %
                    (photo.filename, size))


        except (requests.exceptions.ConnectionError, socket.timeout):
            tqdm.write(
                '%s download failed, retrying after %d seconds...' %
                (photo.filename, WAIT_SECONDS))
            time.sleep(WAIT_SECONDS)
    else:
        tqdm.write("Could not download %s! Maybe try again later." % photo.filename)


if __name__ == '__main__':
    download()
