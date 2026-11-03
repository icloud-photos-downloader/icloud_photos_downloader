# Operation Modes

```{versionchanged} 1.8.0
Added `--delete-after-download` parameter
```

`icloudpd` works in one of three modes of operation:

Copy
:   Download assets from iCloud that are not in the local storage

    This is the default mode

Sync
:   Download assets from iCloud that are not in the local storage (same as Copy).
    In addition, remove unchanged, tracked local files whose stable asset ID is absent from two
    consecutive complete active-library scans and present in the "Recently Deleted"
    album. The first run initializes the safety manifest and removes nothing.
    Filtered or limited runs keep downloading, but skip auto-delete with a warning
    and leave the complete-scan history unchanged.

    This mode is selected with the [`--auto-delete`](auto-delete-parameter) parameter.
    State is kept in `.icloudpd-autodelete.json` inside the download directory.
    Locally modified files and files shared by multiple asset IDs are preserved.

Move
:   Download assets from iCloud that are not in the local storage (same as Copy). Then delete assets in iCloud that are in local storage, optionally leaving recent ones in iCloud

    This mode is selected with [`--keep-icloud-recent-days`](keep-icloud-recent-days-parameter) parameter

Sync and Move can't be combined: Sync would delete the local copies of the assets Move moves to "Recently Deleted".
