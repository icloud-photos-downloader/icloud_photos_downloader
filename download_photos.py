#!/usr/bin/env python

"""
iCloud Photos Downloader

If your account has two-factor authentication enabled,
you will be prompted for a code.

Note: Both regular login and two-factor authentication will expire after an interval set by Apple,
at which point you will have to re-authenticate. This interval is currently two months.

Usage:
  download_photos --username=<username> [--password=<password>] <download_directory>
  download_photos --username=<username> [--password=<password>] <download_directory>
                  [--size=(original|medium|thumb)]
  download_photos -h | --help
  download_photos --version

Options:
  --username=<username>     iCloud username (or email)
  --password=<password>     iCloud password (optional if saved in keyring)
  --size=<size>             Image size to download [default: original].
  -h --help                 Show this screen.
  --version                 Show version.
"""

from docopt import docopt, DocoptExit
from schema import Schema, And, Use, Optional, SchemaError
import os
import sys

try:
    arguments = docopt(__doc__, version='1.0.0')

    sch = Schema({ '<download_directory>': Schema(os.path.isdir,
                        error=('%s is not a valid directory' % arguments['<download_directory>'])),
                    '--size': Schema((lambda s: s in ('original', 'medium', 'thumb')),
                         error='--size must be one of: original, medium, thumb')
                }, ignore_extra_keys=True)

    sch.validate(arguments)

except (DocoptExit, SchemaError) as e:
    print e.message
    sys.exit(1)


from click import prompt
from tqdm import tqdm
from dateutil.parser import parse
from pyicloud import PyiCloudService
import requests
import socket
import time

print("Signing in...")
sys.exit(1)

if '--password' in arguments:
  icloud = PyiCloudService(arguments['--username'], arguments['--password'])
else:
  icloud = PyiCloudService(arguments['--username'])


if icloud.requires_2fa:
    print "Two-factor authentication required. Your trusted devices are:"

    devices = icloud.trusted_devices
    for i, device in enumerate(devices):
        print "  %s: %s" % (i, device.get('deviceName',
            "SMS to %s" % device.get('phoneNumber')))

    device = prompt('Which device would you like to use?', default=0)
    device = devices[device]
    if not icloud.send_verification_code(device):
        print "Failed to send verification code"
        sys.exit(1)

    code = prompt('Please enter validation code')
    if not icloud.validate_verification_code(device, code):
        print "Failed to verify verification code"
        sys.exit(1)


print("Looking up all photos...")
all_photos = icloud.photos.all
photos_count = len(all_photos.photos)

base_download_dir = arguments['<download_directory>'].rstrip('/')
size = arguments['--size']

MAX_RETRIES = 5
WAIT_SECONDS = 5

print("Downloading %d %s photos to %s/ ..." % (photos_count, size, base_download_dir))


def download_with_retries(photo):
    for i in range(MAX_RETRIES):
        try:
            download = photo.download(size)

            if download:
                with open(filepath, 'wb') as file:
                    for chunk in download.iter_content(chunk_size=1024):
                        if chunk:
                            file.write(chunk)
                return

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



pbar = tqdm(all_photos, total=photos_count)
for photo in pbar:
    created_date = parse(photo.created)
    date_path = '{:%Y/%m/%d}'.format(created_date)
    download_dir = '/'.join((base_download_dir, date_path))

    filename_with_size = photo.filename.replace('.', '-%s.' % size)
    filepath = '/'.join((download_dir, filename_with_size))

    if os.path.isfile(filepath):
        pbar.set_description("%s already exists." % filepath)
        continue

    pbar.set_description("Downloading %s to %s" % (photo.filename, filepath))

    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    download_with_retries(photo)

print("All photos have been downloaded!")
