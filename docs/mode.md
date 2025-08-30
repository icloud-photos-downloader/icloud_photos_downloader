# Operation Modes

```{versionchanged} 1.8.0
Added `--delete-after-download` parameter
```

`icloudpd` works in one of three modes of operation:

Copy
:   Download assets from iCloud that are not in the local storage

    This is the default mode

Sync
:   Download assets from iCloud that are not in the local storage (same as Copy). In addition, delete local files that were removed in iCloud (moved into the "Recently Deleted" album)

    This mode is selected with [`--auto-delete`](auto-delete-parameter) parameter

Move
:   Download assets from iCloud that are not in the local storage (same as Copy). Then delete assets in iCloud that are in local storage, optionally leaving recent ones in iCloud

    This mode is selected with [`--keep-icloud-recent-days`](keep-icloud-recent-days-parameter) parameter
