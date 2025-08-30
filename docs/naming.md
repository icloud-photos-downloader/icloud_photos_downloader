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

Specifying `--folder-structure none` will put all files into one folder.

### Formatting

`icloudpd` follows [Python string formatting grammar](https://docs.python.org/3/library/string.html#formatstrings) for [`--folder-structure`](folder-structure-parameter) parameter, e.g. `{:%Y}` extracts only the 4-digit year from the creation date. Full list of format codes is [available](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes).

Default format is: `{:%Y/%m/%d}`

### Language-specific formatting

```{versionadded} 1.22.0
```

Some formatting codes, e.g. `%B` for printing full month, are specific to the language. By default `icloudpd` uses English regardless of the locale of the OS. With [`--use-os-locale`](use-os-locale-parameter) the behavior can be changed.

Example of running `icloudpd` with  specific locale under Linux or MacOS:

```shell
LC_ALL=ru_RU.UTF.8 icloudpd --use-os-locale --version
```

## Duplicates

```{versionchanged} 1.20.0
`--file-match-policy` parameter added and `name-id7` policy implemented
```

In large iCloud collections, it is possible to have name collisions. To avoid collisions if files need to be downloaded into the same folder, use the [`--file-match-policy`](file-match-policy-parameter) parameter:
- add a unique invariant asset identification suffix to the name (e.g., **"IMG_1234_QAZXSW.JPG"**) with `--file-match-policy name-id7`
- de-duplicate by adding file size as a suffix (e.g., **"IMG_1234-67890.JPG"** for the second asset); `--file-match-policy name-size-dedup-with-suffix` - this is the default

## Live Photos

```{versionchanged} 1.18.0
`--live-photo-mov-filename-policy` parameter added and `original` policy implemented
```

Live Photo assets have two components: a still image and a short video. `icloudpd` can download both and allows customizing the file name of the video portion with the [`--live-photo-mov-filename-policy`](live-photo-mov-filename-policy-parameter) parameter:

- Use the same video file name as the still image with the `original` policy; use `--file-match-policy name-id7` to avoid clashes of the video file with other videos.
- Use a suffix from the still image with the `suffix` policy: **"IMG_1234_HEVC.MOV"** for **"IMG_1234.HEIC"** still image. This is the default and works for HEIC still images only

## Unicode

```{versionchanged} 1.18.0
`--keep-unicode-in-filenames` parameter flag added with default `false` 
```

Unicode characters are stripped from file names for better compatibility. `icloudpd` can leave them when [`--keep-unicode-in-filenames`](keep-unicode-in-filenames-parameter) is specified.
