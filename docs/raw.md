# RAW Assets

## Apple ProRAW/ProRes

Apple supports shooting ProRAW stills in [DNG](https://en.wikipedia.org/wiki/Digital_Negative) format and ProRes videos in QuickTime (`.MOV`) format,
and they can be downloaded by `icloudpd` like any other supported format.

## Imported RAW images

```{versionadded} 1.19.0
```

RAW images from third-party cameras can be imported into Apple Photos or uploaded to iCloud.com. 
These types of assets can also be downloaded by `icloudpd`. The following formats are recognized:

- Adobe DNG - same as Apple ProRAW
- Canon CR2, CR3, and CRW
- Sony ARW
- Fuji RAF
- Panasonic RW2
- Nikon NRF, NEF
- Pentax PEF
- Olympus ORF

## RAW+JPEG and JPEG+RAW

```{versionadded} 1.19.0
```

iCloud supports images with two representations, a RAW file and a JPEG file. `icloudpd` can download one or both representations.

One representation will be the `original` [size](size) and the other `alternative`. Which one is which depends on the asset in iCloud, so `icloudpd` lets you fix it with the [`--align-raw`](align-raw-parameter) parameter:

- `as-is` (default) keeps the order as it is in iCloud data
- `original` always treats RAW as the `original` size
- `alternative` always treats RAW as the `alternative` size

`--align-raw` only matters for assets that have both representations; photos with a single file are not affected.

### Recipes

For a RAW+JPEG asset named `IMG_1234` in iCloud:

| Goal | Parameters | Files |
|---|---|---|
| RAW only | `--align-raw original` | `IMG_1234.CR2` |
| JPEG only | `--align-raw alternative` | `IMG_1234.JPG` |
| Both | `--size original --size alternative` | `IMG_1234.CR2`, `IMG_1234.JPG` |

The extension of each file follows its file type (here a Canon CR2), so the two files of a pair normally get different names. An `-alternative` suffix is only added when both would get the same name.

Assets without an `alternative` representation are downloaded as `original` in all three recipes, see [Fallback Logic](size).
