# Operation Modes

```{versionchanged} 1.8.0
Added `--delete-after-download` parameter
```

`icloudpd` works in one of three modes of operation:

Copy
:   Download assets from iCloud that are are not in the local storage

    This is the default mode

Sync
:   Download assets from iCloud that are are not in the local storage (same as Copy). In addition, delete local files that were removed in iCloud (moved into "Recently Deleted" album)

    This mode is selected with `--auto-delete` parameter

Move
:   Download assets from iCloud that are are not in the local storage (same as Copy). Then delete assets in iCloud that were just downloaded 

    This mode is selected with `--delete-after-download` parameter

    ```{note}
    If remote assets were not downloaded, e.g. because they were already in local storage, they will NOT be deleted in iCloud.
    ```