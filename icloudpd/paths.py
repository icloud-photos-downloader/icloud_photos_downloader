import os

def local_download_path(media, size, download_dir):
    filename = filename_with_size(media, size)
    download_path = os.path.join(download_dir, filename)
    return download_path

def filename_with_size(media, size=None):
    # Strip any non-ascii characters.
    # TODO: Support utf-8 characters without crashing
    filename = media.filename.encode('utf-8').decode('ascii', 'ignore')
    if size is None:
        return filename
    return filename.replace('.', '-%s.' % size)
