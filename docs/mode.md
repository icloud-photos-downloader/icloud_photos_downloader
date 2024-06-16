# Operation Modes

```{versionchanged} 1.8.0
Added `--delete-after-download` parameter
```

`icloudpd` works in one of three modes of operation:

- **Copy** - download new photos from iCloud (default mode)
- **Sync** - download new photos from iCloud and delete local files that were removed in iCloud (`--auto-delete` parameter)
- **Move** - download new photos from iCloud and delete photos in iCloud (`--delete-after-download` parameter)