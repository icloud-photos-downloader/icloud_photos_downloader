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
- `adjusted`: The edited version of a photo, see [Special Sizes](special-sizes).
- `alternative`: The second representation of a photo that has two, e.g. the JPEG of a RAW+JPEG pair, see [RAW](raw).

Videos only have `original`, `medium` and `thumb`.

```{note}
The file format of each size is decided by Apple: `icloudpd` saves the file type iCloud reports for it. Apple can change these formats at any time (e.g. `medium` could become HEIC).
```

Size can be selected with the `--size` parameter and multiple specifications are accepted (e.g., `--size original --size medium`). The default is `original`.

### Fallback Logic

`icloudpd` implements its own logic on top of what is available from Apple. When a requested size is not available for an asset in iCloud:

| Requested | Without `--force-size` | With [`--force-size`](force-size-parameter) |
|---|---|---|
| `medium` or `thumb` | `original` is downloaded instead, without a size suffix | nothing is downloaded for that size; an error is logged |
| `adjusted` or `alternative` | `original` is downloaded instead | same as without: `original` is downloaded (these sizes are never forced) |
| any missing size, with `--size original` also given | only `original` is downloaded | `original` is downloaded; an error is logged for the missing size |

For example, `--size adjusted` downloads the edit of an edited photo and the original of an unedited photo or a video. `--size original --size adjusted` downloads the original of every asset, plus the edit when there is one; don't combine it with `--force-size`, which logs an error for every asset that has no `adjusted` version.

### Size Suffixes

Assets downloaded as `medium` or `thumb` get the size as a suffix in their name, e.g., `IMG_1234-medium.JPG`. `adjusted` and `alternative` only get a suffix (`-adjusted`, `-alternative`) when their name would be the same as another file downloaded for the same asset. `original` never gets a suffix.

## Live Photo Videos

The video part of a Live Photo has its own size option, [`--live-photo-size`](live-photo-size-parameter): `original` (default), `medium` or `thumb`. It is independent of `--size`, so `--size medium` still downloads the `original` video unless `--live-photo-size` says otherwise. Sizes other than `original` add a suffix to the name, see [Live Photos](naming).

There is no fallback for the video: when the chosen video size is not available in iCloud, the video is not downloaded. `--force-size` has no effect on it. Use [`--skip-live-photos`](skip-live-photos-parameter) to download only the still image.

(special-sizes)=
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