# Operation Modes

```{versionchanged} 1.8.0
Added `--delete-after-download` parameter
```

`icloudpd` works in one of three modes of operation. All three download assets from iCloud that are not in local storage yet; they differ in what they delete afterwards.

| Mode | Option | What is deleted | Where | When |
|------|--------|-----------------|-------|------|
| Copy | (default) | Nothing | - | - |
| Sync | [`--auto-delete`](auto-delete-parameter) | Local files of assets that are in iCloud's "Recently Deleted" album | Local | After the download pass |
| Move | [`--keep-icloud-recent-days X`](keep-icloud-recent-days-parameter) | Assets that are present locally and at least X days old | iCloud (moved to "Recently Deleted") | During the download pass, asset by asset |

Sync and Move can't be combined: Sync would delete the local copies of the assets Move moves to "Recently Deleted".

(copy-mode)=
## Copy

Download assets from iCloud that are not in local storage. Nothing is deleted, neither locally nor in iCloud.

This is the default mode.

```sh
icloudpd --directory /data/photos --username my@email.address
```

(sync-mode)=
## Sync

Download assets from iCloud that are not in local storage (same as Copy). In addition, delete local files of assets that were deleted in iCloud.

This mode is selected with the [`--auto-delete`](auto-delete-parameter) parameter.

- When a photo is deleted in iCloud, Apple moves it to the "Recently Deleted" album. After the download pass, icloudpd goes through that album and deletes the matching local files.
- This only works while the asset is still in "Recently Deleted". Apple keeps assets there for about 30 days, or until the album is emptied. Once it is gone from there, icloudpd no longer knows about it and the local files stay.
- The whole "Recently Deleted" album of the selected [`--library`](library-parameter) is checked. [`--album`](album-parameter), [`--recent`](recent-parameter), [`--until-found`](until-found-parameter), [`--skip-videos`](skip-videos-parameter), [`--skip-photos`](skip-photos-parameter) and the `--skip-created-*` filters don't limit it.
- Local files are found by the name and folder icloudpd would download them to, so keep [`--folder-structure`](folder-structure-parameter) and the naming options the same as when you downloaded. Files you renamed or moved are not found.
- Matching `.xmp` sidecar files (see [`--xmp-sidecar`](xmp-sidecar-parameter)) are deleted as well.
- With [`--dry-run`](dry-run-parameter), the files that would be deleted are only logged.

```sh
icloudpd --directory /data/photos --username my@email.address --auto-delete
```

(move-mode)=
## Move

Download assets from iCloud that are not in local storage (same as Copy). Then delete assets in iCloud that are in local storage, optionally leaving recent ones in iCloud.

This mode is selected with the [`--keep-icloud-recent-days X`](keep-icloud-recent-days-parameter) parameter.

- Deleting means the asset is moved to "Recently Deleted" in iCloud, the same as deleting it on your phone. It is removed from the whole library and from every album it is in, not only from the album given with [`--album`](album-parameter).
- The age of an asset is calculated from its creation date (when it was taken, as reported by iCloud) in the local time zone. Assets younger than X days stay in iCloud. With `0`, every asset that is present locally is deleted from iCloud.
- Deletion happens asset by asset while the download pass runs.

Safety rules. An asset is only deleted from iCloud if:

- every file that was requested for it is present locally, after downloading or because it was already there. This includes the video of a Live Photo and every size given with [`--size`](size-parameter). If a size requested with [`--force-size`](force-size-parameter) doesn't exist, or the requested [`--live-photo-size`](live-photo-size-parameter) doesn't exist, the asset is kept;
- iCloud reports a creation date for it. Assets without one are kept, with a warning;
- it is not excluded by filters such as [`--skip-videos`](skip-videos-parameter), [`--skip-photos`](skip-photos-parameter), [`--skip-created-before`](skip-created-before-parameter) or [`--skip-created-after`](skip-created-after-parameter);
- the run looks at it. With [`--recent`](recent-parameter) or [`--until-found`](until-found-parameter) the run stops early, and the remaining assets stay in iCloud. icloudpd logs a warning at startup for these combinations;
- the run is not using [`--only-print-filenames`](only-print-filenames-parameter), which never deletes anything.

If iCloud refuses a deletion with `TRY_AGAIN_LATER` (for example because the library was changed at the same time), that asset stays in iCloud, an error is logged and the run continues. The next run tries again.

With [`--dry-run`](dry-run-parameter), the assets that would be deleted are only logged.

```{warning}
With [`--skip-live-photos`](skip-live-photos-parameter), the video part of a Live Photo is never downloaded, but the asset is still deleted from iCloud, video included. Don't combine it with `--keep-icloud-recent-days` if you want to keep the videos.
```

```sh
icloudpd --directory /data/photos --username my@email.address --keep-icloud-recent-days 30
```

(delete-after-download-mode)=
## `--delete-after-download`

[`--delete-after-download`](delete-after-download-parameter) is deprecated since 1.26.0; use `--keep-icloud-recent-days 0` instead. It only deletes assets from iCloud that were downloaded in that same run. Assets that were already in local storage are not deleted.

## Shared library mirror

[`--prune-orphans`](prune-orphans-parameter) is a separate option for a shared library: it moves local downloads out of the mirror when their photos disappear from that shared library, also when they don't pass through "Recently Deleted". It never deletes anything in iCloud. See its [reference entry](prune-orphans-parameter) for the requirements.

## Rejected combinations

icloudpd refuses to start and exits with code 2 when one configuration combines:

- `--auto-delete` and `--keep-icloud-recent-days`
- `--auto-delete` and `--delete-after-download`
- `--keep-icloud-recent-days` and `--delete-after-download`
- `--prune-orphans` and `--delete-after-download`, `--keep-icloud-recent-days` or `--only-print-filenames`, or `--prune-orphans` without `--library`
- `--watch-with-interval` and `--only-print-filenames`, `--list-albums`, `--list-libraries` or `--auth-only`

## Previewing and watching

- [`--dry-run`](dry-run-parameter) signs in and compares iCloud with local storage, but downloads and deletes nothing; it logs what it would do, deletions included.
- [`--only-print-filenames`](only-print-filenames-parameter) only prints the paths of files that would be downloaded. It deletes nothing and doesn't run Sync either.
- [`--watch-with-interval`](watch-with-interval-parameter) repeats the run every X seconds, including the deletions of the selected mode.
