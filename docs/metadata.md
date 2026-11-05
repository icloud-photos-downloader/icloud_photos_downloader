# Metadata

`icloudpd` saves the files as they are in iCloud. Some metadata that iCloud keeps outside the file can be added locally.

## File Dates

The modification time of every file `icloudpd` downloads, including the video of a Live Photo, is set to the creation date of the asset. Files that already exist locally are not touched.

## XMP Sidecars

```{versionadded} 1.25.0
```

With [`--xmp-sidecar`](xmp-sidecar-parameter), `icloudpd` writes an [XMP](https://en.wikipedia.org/wiki/Extensible_Metadata_Platform) file next to each downloaded photo or video (one per [size](size)), named after the full file name, e.g. `IMG_1234.HEIC.xmp`. The video of a Live Photo doesn't get one. The sidecar holds what iCloud knows about the asset, when present:

- title (caption) and description
- keywords
- location: latitude, longitude, altitude, speed and GPS time
- creation date, with the time zone offset iCloud stored for the asset
- orientation
- rating: `5` for favorites, `-1` (rejected) for hidden or deleted assets
- `Screenshot` as camera make, for screenshots

The sidecar is written again on every run, so changes in iCloud reach the local copy. A sidecar that was not written by `icloudpd` (e.g. by Lightroom or digiKam), or that can't be read as XML, is never overwritten. Fields that iCloud sends in an unexpected format are left out.

## EXIF Date

With [`--set-exif-datetime`](set-exif-datetime-parameter), `icloudpd` writes the creation date into downloaded JPEG files (`.jpg`/`.jpeg`) that have no `DateTimeOriginal` EXIF tag. It writes the `DateTimeOriginal`, `DateTimeDigitized` and `DateTime` tags, using the creation date in the local time zone. Files that already have `DateTimeOriginal`, other formats (HEIC, PNG, RAW, videos), and files that were already downloaded before are left as they are.

```{note}
This changes the downloaded file, so it is no longer identical to the one in iCloud.
```

```{versionchanged} 1.33.0
A JPEG that got its date written is recognised as the same photo on the next run and is no longer downloaded again with a size suffix
```

This works as long as the date `icloudpd` would write stays the same; with the default [`--file-match-policy`](file-match-policy-parameter), changing the time zone between runs (see [Folder Structure](folder-structure)) makes `icloudpd` download such files again with a size suffix.
