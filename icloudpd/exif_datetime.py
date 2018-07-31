import piexif
from icloudpd.logger import setup_logger

def get_photo_exif(path):
    try:
        exif_dict = piexif.load(path)
        return exif_dict.get('Exif').get(36867)
    except:
        logger = setup_logger()
        logger.debug("Error fetching EXIF data for %s" % path)
        return None

def set_photo_exif(path, date):
    try:
        exif_dict = piexif.load(path)
        exif_dict.get('1st')[306] = date
        exif_dict.get('Exif')[36867] = date
        exif_dict.get('Exif')[36868] = date
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, path)
    except:
        logger = setup_logger()
        logger.debug("Error setting EXIF data for %s" % path)
        return
