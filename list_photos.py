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

from authentication import authenticate

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
@click.option('--smtp-username',
              help='Your SMTP username, for sending email notifications.',
              metavar='<smtp_username>')
@click.option('--smtp-password',
              help='Your SMTP password, for sending email notifications.',
              metavar='<smtp_password>')
@click.option('--notification-email',
              help='Email address where you would like to receive notifications. Default: SMTP username',
              metavar='<notification_email>')

def list_photos(directory, username, password, size, download_videos, force_size, \
    smtp_username, smtp_password, notification_email):
    """Prints out file path of photos that will be downloaded"""

    if not notification_email:
        notification_email = smtp_username

    icloud = authenticate(username, password, smtp_username, smtp_password, notification_email)
    all_photos = icloud.photos.all

    directory = os.path.normpath(directory)

    for photo in all_photos:
        for _ in range(MAX_RETRIES):
            try:
                if not download_videos \
                    and not photo.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    continue

                created_date = photo.created
                date_path = '{:%Y/%m/%d}'.format(created_date)
                download_dir = os.path.join(directory, date_path)

                # Strip any non-ascii characters.
                filename = photo.filename.encode('utf-8') \
                    .decode('ascii', 'ignore').replace('.', '-%s.' % size)

                download_path = os.path.join(download_dir, filename)
                print(download_path)

                break

            except (requests.exceptions.ConnectionError, socket.timeout):
                time.sleep(WAIT_SECONDS)

if __name__ == '__main__':
    list_photos()
