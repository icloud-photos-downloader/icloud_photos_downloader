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


def download(directory, username, password, size):
    """Download all iCloud photos to a local directory"""

    icloud = authenticate(username, password)

    print("Looking up all photos...")
    all_photos = icloud.photos.all
    photos_count = len(all_photos.photos)

    directory = directory.rstrip('/')
    print("Downloading %d %s photos to %s/ ..." % (photos_count, size, directory))

    pbar = tqdm(all_photos, total=photos_count)
    for photo in pbar:
        created_date = parse(photo.created)
        date_path = '{:%Y/%m/%d}'.format(created_date)
        download_dir = '/'.join((directory, date_path))

        filename_with_size = photo.filename.replace('.', '-%s.' % size)
        destination = '/'.join((download_dir, filename_with_size))

        if os.path.isfile(destination):
            pbar.set_description("%s already exists." % destination)
            continue

        pbar.set_description("Downloading %s to %s" % (photo.filename, destination))

        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

        download_photo(photo, size, destination)

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

def download_photo(photo, size, destination):
    for i in range(MAX_RETRIES):
        try:
            download = photo.download(size)

            if download:
                with open(destination, 'wb') as file:
                    for chunk in download.iter_content(chunk_size=1024):
                        if chunk:
                            file.write(chunk)
            else:
                tqdm.write("Could not download %s, %s size does not exist." % (photo.filename, size))

            return

        except requests.exceptions.ConnectionError:
            tqdm.write('HTTP connection failed, retrying...')

        except socket.timeout:
            tqdm.write('Download failed, retrying...')

        time.sleep(WAIT_SECONDS)
    else:
        tqdm.write("Could not download %s! Try again later." % photo.filename)


if __name__ == '__main__':
    download()