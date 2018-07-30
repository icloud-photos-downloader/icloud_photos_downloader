import piexif

def get_exif_datetime(path):
    try:
        exif_dict = piexif.load(path)
        date = exif_dict.get('Exif').get(36867)
    except:
        date = None
    return date

def set_exif_datetime(path, date):
    try:
        exif_dict = piexif.load(path)
        exif_dict.get('1st')[306] = date
        exif_dict.get('Exif')[36867] = date
        exif_dict.get('Exif')[36868] = date
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, path)
    except:
       return
