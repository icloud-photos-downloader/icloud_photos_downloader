# File Naming

Assets on iCloud have names. When downloading assets, `icloudpd` can adjust names.

(folder-structure)=
## Folder Structure

```{versionchanged} 1.7.0
Support for `none` value added
```
```{versionchanged} 1.22.0
Support for OS locale added
```

`icloudpd` uses asset metadata (_created date_) to build folder hierarchy, and it can be adjusted with [`--folder-structure`](folder-structure-parameter) parameter.

The created date is converted to the local time zone before it is formatted, so a photo taken just before midnight can end up in a different day folder on machines with different time zones. Set the `TZ` environment variable (e.g. `TZ=Europe/Amsterdam`) to choose the time zone, which is especially useful in Docker containers that run in UTC by default.

Specifying `--folder-structure none` (in any letter case) will put all files into one folder.

Albums don't get folders of their own: assets selected with [`--album`](album-parameter) are saved in the same folder structure as the rest of the library. To keep albums apart, run `icloudpd` with a different [`--directory`](directory-parameter) for each album.

### Formatting

`icloudpd` follows [Python string formatting grammar](https://docs.python.org/3/library/string.html#formatstrings) for [`--folder-structure`](folder-structure-parameter) parameter, e.g. `{:%Y}` extracts only the 4-digit year from the creation date. Full list of format codes is [available](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes).

Default format is: `{:%Y/%m/%d}`

### Language-specific formatting

```{versionadded} 1.22.0
```

Some formatting codes, e.g. `%B` for printing full month, are specific to the language. By default `icloudpd` uses English regardless of the locale of the OS. With [`--use-os-locale`](use-os-locale-parameter) the behavior can be changed.

Example of running `icloudpd` with  specific locale under Linux or MacOS:

```shell
LC_ALL=ru_RU.UTF-8 icloudpd --use-os-locale --version
```

## File Names

The file name comes from the name of the asset in iCloud, e.g. `IMG_1234.HEIC`. The extension is set to match the file type of the downloaded [size](size), so the JPEG `medium` copy of `IMG_1234.HEIC` is saved as `IMG_1234-medium.JPG`.

Assets without a name in iCloud are named after the first 12 characters of their iCloud id, with any character other than `A-Z`, `a-z` and `0-9` replaced by `_`, e.g. `AWYDRiGu_b9X.JPG`.

## Duplicates

```{versionchanged} 1.20.0
`--file-match-policy` parameter added and `name-id7` policy implemented
```

In large iCloud collections, it is possible to have name collisions. To avoid collisions if files need to be downloaded into the same folder, use the [`--file-match-policy`](file-match-policy-parameter) parameter:
- add a unique invariant asset identification suffix to the name (e.g., **"IMG_1234_QVpTNGN.JPG"**) with `--file-match-policy name-id7`
- de-duplicate by adding file size as a suffix (e.g., **"IMG_1234-67890.JPG"** for the second asset); `--file-match-policy name-size-dedup-with-suffix` - this is the default

With `name-size-dedup-with-suffix`, the size suffix is only added when a file with the same name already exists locally and its size differs from the size of the file in iCloud. A local file with the same name and size counts as already downloaded. The number in the suffix is the size of the file in iCloud, in bytes. A local file that was changed after downloading (e.g. edited in another program) has a different size, so the iCloud file is downloaded again next to it with a size suffix.

With `name-id7`, every file name gets the suffix, and a local file with the same name always counts as already downloaded. The suffix is placed before the other suffixes, e.g. `IMG_1234_QVpTNGN-medium.JPG`, `IMG_1234_QVpTNGN-adjusted.JPG` or `IMG_1234_QVpTNGN_HEVC.MOV`.

```{warning}
The two policies produce different file names. Switching `--file-match-policy` for a folder that already has downloads makes `icloudpd` download everything again under the new names; the old files are left in place.
```

## Live Photos

```{versionchanged} 1.18.0
`--live-photo-mov-filename-policy` parameter added and `original` policy implemented
```

Live Photo assets have two components: a still image and a short video. `icloudpd` can download both and allows customizing the file name of the video portion with the [`--live-photo-mov-filename-policy`](live-photo-mov-filename-policy-parameter) parameter:

| Still image | `suffix` (default) | `original` |
|---|---|---|
| `IMG_1234.HEIC` | `IMG_1234_HEVC.MOV` | `IMG_1234.MOV` |
| `IMG_1234.JPG` | `IMG_1234.MOV` | `IMG_1234.MOV` |

- The `suffix` policy only adds `_HEVC` when the still image is a HEIC file; for other still images both policies give the same name.
- With a name like `IMG_1234.MOV`, the video of a Live Photo can clash with a separate video of the same name; use `--file-match-policy name-id7` to avoid that.

The video size is chosen with [`--live-photo-size`](live-photo-size-parameter). Sizes other than `original` add a suffix: `IMG_1234_HEVC-medium.MOV` or `IMG_1234_HEVC-thumb.MOV`.

## XMP Sidecars

With [`--xmp-sidecar`](xmp-sidecar-parameter), the sidecar is named after the full name of the downloaded file, including its extension: `IMG_1234.HEIC.xmp`. See [Metadata](metadata) for details.

## Unicode

```{versionchanged} 1.18.0
`--keep-unicode-in-filenames` parameter flag added with default `false` 
```

Non-ASCII characters are removed from file names for better compatibility: they are dropped, not replaced or transliterated. `Café.JPG` becomes `Caf.JPG`, and a name made only of non-ASCII characters, such as `照片.JPG`, becomes `.JPG`. `icloudpd` keeps them when [`--keep-unicode-in-filenames`](keep-unicode-in-filenames-parameter) is specified.

Characters that are not allowed in file names on some systems (`<`, `>`, `:`, `"`, `/`, `\`, `|`, `?`, `*`) are always replaced with `_`.
