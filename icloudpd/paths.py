"""Path functions"""
import os


def local_download_path(media, size, download_dir):
    """Returns the full download path, including size"""
    filename = filename_with_size(media, size)
    download_path = os.path.join(download_dir, filename)
    return download_path


def filename_with_size(media, size=None):
    """Returns the filename with size, e.g. IMG1234-original.jpg"""
    # Strip any non-ascii characters.
    filename = media.filename.encode("utf-8").decode("ascii", "ignore")
    if size is None:
        return filename
    return filename.replace(".", "-%s." % size)
