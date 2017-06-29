#!/usr/bin/env python
from __future__ import print_function
import click
import os
import sys
import socket
import requests
import time
from tqdm import tqdm
from dateutil.parser import parse
from pyicloud import PyiCloudService

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


def list_photos(directory, username, password, size, download_videos, force_size):
    """Prints out file path of photos that will be downloaded"""

    icloud = authenticate(username, password)
    all_photos = icloud.photos.all

    directory = directory.rstrip('/')

    for photo in all_photos:
        for _ in range(MAX_RETRIES):
            try:
                if not download_videos \
                    and not photo.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    continue

                created_date = photo.created
                date_path = '{:%Y/%m/%d}'.format(created_date)
                download_dir = '/'.join((directory, date_path))

                # Strip any non-ascii characters.
                filename = photo.filename.encode('utf-8') \
                    .decode('ascii', 'ignore').replace('.', '-%s.' % size)

                download_path = '/'.join((download_dir, filename))
                print(download_path)

                break

            except (requests.exceptions.ConnectionError, socket.timeout):
                time.sleep(WAIT_SECONDS)


def authenticate(username, password):
    if password:
      icloud = PyiCloudService(username, password)
    else:
      icloud = PyiCloudService(username)

    if icloud.requires_2fa:
        print("Two-factor authentication required. Your trusted devices are:")

        devices = icloud.trusted_devices
        for i, device in enumerate(devices):
            print("  %s: %s" % (i, device.get('deviceName',
                "SMS to %s" % device.get('phoneNumber'))))

        device = click.prompt('Which device would you like to use?', default=0)
        device = devices[device]
        if not icloud.send_verification_code(device):
            print("Failed to send verification code")
            sys.exit(1)

        code = click.prompt('Please enter validation code')
        if not icloud.validate_verification_code(device, code):
            print("Failed to verify verification code")
            sys.exit(1)

        print("Great, you're all set up. Now re-run the script to print out filenames.")
        sys.exit(1)

    return icloud

if __name__ == '__main__':
    list_photos()
