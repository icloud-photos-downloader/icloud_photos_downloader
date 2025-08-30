# Asset Sizes

## Basic Sizes

```{versionchanged} 1.19.0
Multiple `--size` parameters can be specified
```

Each asset in iCloud may have multiple sizes available for downloading:
- original
- medium
- thumb

Size can be selected with the `--size` parameter and multiple specifications are accepted (e.g., `--size original --size medium`). The default is `original`.

If the size parameter is specified, but it is not available for the asset in iCloud, then `original` is downloaded, unless `--force-size` is specified.

Assets for sizes other than original will have a suffix added to their name, e.g., `IMG-1234-medium.JPG`.

## Special Sizes

```{versionadded} 1.19.0
```

Image edits are represented as a special size `adjusted`. Two common use cases related to edits:
- Download the edited version or original if it was not edited: use the `--size adjusted` parameter
- Download edit and original: use the `--size adjusted --size original` parameters. Edits will have a `-adjusted` suffix added if the file extension is the same as the original.

```{note}
Portraits are represented in iCloud as edits.
```

```{seealso}
[RAW](raw) assets use `alternative` size
```