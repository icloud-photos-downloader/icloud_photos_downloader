# Asset Sizes

## Basic Sizes

```{versionchanged} 1.19.0
Multiple `--size` parameters can be specified
```

`icloudpd` emulates the web browser to access iCloud.com. Whatever Apple makes available in the iCloud.com web UI is available to `icloudpd`.

Each asset in iCloud may have multiple sizes available for downloading:
- `original`: The original file as uploaded to iCloud (e.g. HEIC, JPEG, RAW).
- `medium`: A smaller copy made by iCloud. For photos this has been a JPEG; for videos it is a smaller video.
- `thumb`: A thumbnail made by iCloud. For photos this has been a JPEG; for videos it is a small video.

```{note}
The file format of each size is decided by Apple: `icloudpd` saves the file type iCloud reports for it. Apple can change these formats at any time (e.g. `medium` could become HEIC).
```

Size can be selected with the `--size` parameter and multiple specifications are accepted (e.g., `--size original --size medium`). The default is `original`.

### Fallback Logic

`icloudpd` implements its own logic on top of what is available from Apple.

If the size parameter is specified, but it is not available for the asset in iCloud, then `original` is downloaded, unless `--force-size` is specified.

Assets for sizes other than original will have a suffix added to their name, e.g., `IMG-1234-medium.JPG`.

## Special Sizes

```{versionadded} 1.19.0
```

Image edits are represented as a special size `adjusted`. This usually corresponds to the current version of the image with edits (crops, filters, etc.) applied.

Two common use cases related to edits:
- Download the edited version or original if it was not edited: use the `--size adjusted` parameter.
- Download edit and original: use the `--size adjusted --size original` parameters. Edits will have a `-adjusted` suffix added if the file extension is the same as the original.

```{note}
Portraits are represented in iCloud as edits. The `adjusted` file can be a HEIC, with the crop and edits applied.
```

```{seealso}
[RAW](raw) assets use `alternative` size
```