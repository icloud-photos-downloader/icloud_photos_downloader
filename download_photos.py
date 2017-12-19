#!/usr/bin/env python
from __future__ import print_function
import click
import os
import sys
import socket
import requests
import time
import itertools
import piexif
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
              help='Your iCloud password',
              metavar='<password>')
@click.option('--size',
              help='Image size to download (default: original)',
              type=click.Choice(['original', 'medium', 'thumb']),
              default='original')
@click.option('--recent',
              help='Number of recent photos to download (default: download all photos)',
              type=click.IntRange(0))
@click.option('--until-found',
              help='Download most recently added photos until we find x number of previously downloaded consecutive photos (default: download all photos)',
              type=click.IntRange(0))
@click.option('--download-videos',
              help='Download both videos and photos (default: only download photos)',
              is_flag=True)
@click.option('--force-size',
              help='Only download the requested size ' + \
                   '(default: download original if size is not available)',
              is_flag=True)
@click.option('--auto-delete',
              help='Scans the "Recently Deleted" folder and deletes any files found in there. ' + \
                   '(If you restore the photo in iCloud, it will be downloaded again.)',
              is_flag=True)
@click.option('--only-print-filenames',
              help='Only prints the filenames of all files that will be downloaded. ' + \
                '(Does not download any files.)',
              is_flag=True)
@click.option('--folder-structure',
              help='Folder structure (default: {:%Y/%m/%d})',
              metavar='<folder_structure>',
              default='{:%Y/%m/%d}')
@click.option('--set-exif-datetime',
              help='Set exif DateTimeOriginal tag if it's missing.',
              is_flag=True)
@click.option('--smtp-username',
              help='Your SMTP username, for sending email notifications when two-step authentication expires.',
              metavar='<smtp_username>')
@click.option('--smtp-password',
              help='Your SMTP password, for sending email notifications when two-step authentication expires.',
              metavar='<smtp_password>')
@click.option('--smtp-host',
              help='Your SMTP server host. Defaults to: smtp.gmail.com',
              metavar='<smtp_host>',
              default='smtp.gmail.com')
@click.option('--smtp-port',
              help='Your SMTP server port. Default: 587 (Gmail)',
              metavar='<smtp_port>',
              type=click.IntRange(0),
              default=587)
@click.option('--smtp-no-tls',
              help='Pass this flag to disable TLS for SMTP (TLS is required for Gmail)',
              metavar='<smtp_no_tls>',
              is_flag=True)
@click.option('--notification-email',
              help='Email address where you would like to receive email notifications. Default: SMTP username',
              metavar='<notification_email>')


def download(directory, username, password, size, recent, \
    until_found, download_videos, force_size, auto_delete, \
    only_print_filenames, folder_structure, set_exif_datetime, \
    smtp_username, smtp_password, smtp_host, smtp_port, smtp_no_tls, \
    notification_email):
    """Download all iCloud photos to a local directory"""

    if not notification_email:
        notification_email = smtp_username

    icloud = authenticate(username, password, \
        smtp_username, smtp_password, smtp_host, smtp_port, smtp_no_tls, notification_email)

    if hasattr(directory, 'decode'):
        directory = directory.decode('utf-8')

    directory = os.path.normpath(directory)

    if not only_print_filenames:
        print("Looking up all photos...")
    photos = icloud.photos.all
    photos_count = len(photos)

    # Optional: Only download the x most recent photos.
    if recent is not None:
        photos_count = recent
        photos = itertools.islice(photos, recent)

    kwargs = {'total': photos_count}

    if until_found is not None:
        del kwargs['total']
        photos_count = '???'

        # ensure photos iterator doesn't have a known length
        photos = (p for p in photos)

    if not only_print_filenames:
        if download_videos:
            print("Downloading %s %s photos and videos to %s/ ..." % (photos_count, size, directory))
        else:
            print("Downloading %s %s photos to %s/ ..." % (photos_count, size, directory))

    consecutive_files_found = 0
    if only_print_filenames:
        progress_bar = photos
    else:
        progress_bar = tqdm(photos, **kwargs)

    for photo in progress_bar:
        for _ in range(MAX_RETRIES):
            try:
                if not download_videos \
                    and not photo.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    if not only_print_filenames:
                        progress_bar.set_description(
                            "Skipping %s, only downloading photos." % photo.filename)
                    continue

                created_date = photo.created

                date_path = (folder_structure).format(created_date)
                download_dir = os.path.join(directory, date_path)

                if not os.path.exists(download_dir):
                    os.makedirs(download_dir)

                download_path = local_download_path(photo, size, download_dir)
                if os.path.isfile(download_path):
                    if until_found is not None:
                        consecutive_files_found += 1
                    if not only_print_filenames:
                        progress_bar.set_description("%s already exists." % truncate_middle(download_path, 96))
                    break

                if only_print_filenames:
                    print(download_path)
                else:
                    download_photo(photo, download_path, size, force_size, download_dir, progress_bar)

                if set_exif_datetime \
                    and photo.filename.lower().endswith(('.jpg', '.jpeg')) \
                    and not get_datetime(download_path):
                        set_datetime(download_path, created_date.strftime("%Y:%m:%d %H:%M:%S"))

                if until_found is not None:
                    consecutive_files_found = 0
                break

            except (requests.exceptions.ConnectionError, socket.timeout):
                if not only_print_filenames:
                    tqdm.write('Connection failed, retrying after %d seconds...' % WAIT_SECONDS)
                time.sleep(WAIT_SECONDS)

        else:
            if not only_print_filenames:
                tqdm.write("Could not process %s! Maybe try again later." % photo.filename)

        if until_found is not None and consecutive_files_found >= until_found:
            if not only_print_filenames:
                tqdm.write('Found %d consecutive previusly downloaded photos. Exiting' % until_found)
                progress_bar.close()
            break

    if not only_print_filenames:
        print("All photos have been downloaded!")

        if auto_delete:
            print("Deleting any files found in 'Recently Deleted'...")

            recently_deleted = icloud.photos.albums['Recently Deleted']

            for media in recently_deleted:
                created_date = media.created
                date_path = (folder_structure).format(created_date)
                download_dir = os.path.join(directory, date_path)

                filename = filename_with_size(media, size)
                path = os.path.join(download_dir, filename)

                if os.path.exists(path):
                    print("Deleting %s!" % path)
                    os.remove(path)

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

def local_download_path(photo, size, download_dir):
    # Strip any non-ascii characters.
    filename = filename_with_size(photo, size)
    download_path = os.path.join(download_dir, filename)

    return download_path

def download_photo(photo, download_path, size, force_size, download_dir, progress_bar):
    truncated_path = truncate_middle(download_path, 96)

    # Fall back to original if requested size is not available
    if size not in photo.versions and not force_size and size != 'original':
        download_photo(photo, download_path, 'original', True, download_dir, progress_bar)
        return

    progress_bar.set_description("Downloading %s" % truncated_path)

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

def get_datetime(path):
    try:
        exif_dict = piexif.load(path)
        date = exif_dict.get('Exif').get(36867)
    except:
        date = None
    return date

def set_datetime(path, date):
    try:
        exif_dict = piexif.load(path)
        exif_dict.get('Exif')[36867] = date
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, path)
    except:
        return

if __name__ == '__main__':
    download()
