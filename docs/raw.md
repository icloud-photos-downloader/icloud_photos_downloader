# RAW Assets

## Apple ProRAW/ProRes

Apple supports shooting stills and videos in [DNG](https://en.wikipedia.org/wiki/Digital_Negative) format and 
they can be downloaded by `icloudpd` like any other supported format.

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

iCloud supports images with two representations. `icloudpd` can download one or both representations.

One representation will be the `original` [size](size) and the other `alternative`.

As of June 2024, icloud.com always shows assets with two representations as RAW+JPEG. The Photos app on Mac
allows choosing which representation to treat as original, but it is not clear what that setting changes. 

`icloudpd` disambiguates the behavior with the [`--align-raw`](align-raw-parameter) parameter:

- *original* always treats RAW as the original [size](size)
- *alternative* always treats RAW as the alternative [size](size)
- *as-is* treats RAW as it is in iCloud data
