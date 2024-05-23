"""Path functions"""
import os


def clean_filename(filename: str) -> str:
    """Replaces invalid chars in filenames with '_'"""
    result = filename.encode(
        "utf-8").decode("ascii", "ignore")
    invalid = '<>:"/\\|?*\0'

    for char in invalid:
        result = result.replace(char, '_')

    return result


def local_download_path(filename: str, size: str, download_dir: str) -> str:
    """Returns the full download path, including size"""
    filename = filename_with_size(filename, size)
    download_path = os.path.join(download_dir, filename)
    return download_path


def filename_with_size(filename: str, size: str) -> str:
    """Returns the filename with size, e.g. IMG1234.jpg, IMG1234-small.jpg"""
    # Strip any non-ascii characters.
    filename = clean_filename(filename)
    if size == 'original':
        return filename
    return (f"-{size}.").join(filename.rsplit(".", 1))
