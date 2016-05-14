#!/usr/bin/env python
import click
import os
import sys
import socket
import requests
import time
from tqdm import tqdm
from dateutil.parser import parse
from pyicloud import PyiCloudService


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
    help='Only download the requested size (default: download original if requested size is not available)',
    is_flag=True)


def download(directory, username, password, size, download_videos, force_size):
    """Download all iCloud photos to a local directory"""

    icloud = authenticate(username, password)

    print("Looking up all photos...")
    all_photos = icloud.photos.all
    photos_count = len(all_photos.photos)

    directory = directory.rstrip('/')

    if download_videos:
        print("Downloading %d %s photos and videos to %s/ ..." % (photos_count, size, directory))
    else:
        print("Downloading %d %s photos to %s/ ..." % (photos_count, size, directory))

    pbar = tqdm(all_photos, total=photos_count)
    for photo in pbar:
        if not download_videos and not photo.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            pbar.set_description("Skipping %s, only downloading photos." % photo.filename)
            continue

        created_date = parse(photo.created)
        date_path = '{:%Y/%m/%d}'.format(created_date)
        download_dir = '/'.join((directory, date_path))

        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

        download_photo(photo, size, force_size, download_dir, pbar)

    print("All photos have been downloaded!")



def authenticate(username, password):
    print("Signing in...")

    if password:
      icloud = PyiCloudService(username, password)
    else:
      icloud = PyiCloudService(username)

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


MAX_RETRIES = 5
WAIT_SECONDS = 5

def download_photo(photo, size, force_size, download_dir, pbar):
    for i in range(MAX_RETRIES):
        try:
            filename_with_size = photo.filename.replace('.', '-%s.' % size)
            download_path = '/'.join((download_dir, filename_with_size))

            if os.path.isfile(download_path):
                pbar.set_description("%s already exists." % download_path)
                return

            # Fall back to original if requested size is not available
            if size not in photo.versions and not force_size and size != 'original':
                download_photo(photo, 'original', True, download_dir, pbar)
                return

            pbar.set_description("Downloading %s to %s" % (photo.filename, download_path))

            download = photo.download(size)

            if download:
                with open(download_path, 'wb') as file:
                    for chunk in download.iter_content(chunk_size=1024):
                        if chunk:
                            file.write(chunk)
            else:
                tqdm.write("Could not download %s!" % (photo.filename, size))

            return

        except (requests.exceptions.ConnectionError, socket.timeout):
            tqdm.write('Download failed, retrying after %d seconds...' % WAIT_SECONDS)

        time.sleep(WAIT_SECONDS)
    else:
        tqdm.write("Could not download %s! Maybe try again later." % photo.filename)


if __name__ == '__main__':
    download()