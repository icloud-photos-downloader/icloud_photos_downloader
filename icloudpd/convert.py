"""Image conversion functions."""
from pathlib import PurePath, Path
from PIL import Image
from pyheif import read

def heif_to_jpg(path: PurePath, delete_og: bool = False):
    """Convert the heif image to jpg."""
    new_path = PurePath(path.parent) / path.name.replace(path.suffix, ".jpg")
    heif_file = read(str(path))
    image = Image.frombytes(mode=heif_file.mode,
                            size=heif_file.size,
                            data=heif_file.data)
    image.save(str(new_path), "JPEG")

    if delete_og:
        Path(path).unlink()
