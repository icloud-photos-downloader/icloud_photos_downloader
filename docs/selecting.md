# Selecting Assets

By default `icloudpd` downloads every photo and video in the personal library, except hidden and recently deleted ones. The options below narrow that down. They can be combined.

## Libraries

Besides the personal library, an account can have access to a [Shared Library](https://support.apple.com/en-us/102503). [`--list-libraries`](list-libraries-parameter) prints the names of the available libraries, and [`--library`](library-parameter) selects one:

```shell
icloudpd --username my@email.address --list-libraries
icloudpd --username my@email.address --directory /photos/shared --library 'SharedSync-YOUR-LIBRARY-ID'
```

The default is `PrimarySync`, the personal library. Each configuration downloads from one library.

## Albums

[`--list-albums`](list-albums-parameter) prints the albums of the selected library, and [`--album`](album-parameter) downloads only the assets in an album. `--album` can be given more than once to download several albums in one run:

```shell
icloudpd --username my@email.address --list-albums
icloudpd --username my@email.address --directory /photos --album "Favorites" --album "Trips/2024/Italy"
```

```{versionchanged} 1.33.0
Albums in folders are listed and selected by their path, e.g. `Trips/2024/Italy` for the album "Italy" in the folder "2024" in the folder "Trips"
```

The list also contains the albums iCloud makes itself, such as `Favorites`, `Videos`, `Screenshots` and `Hidden`. Hidden photos are only downloaded with `--album Hidden`. A shared library only has these iCloud albums, not albums of its own.

Album names are not used for folders: assets from all albums go into the normal [folder structure](folder-structure).

## Recent Assets

- [`--recent X`](recent-parameter) only checks the first X assets of the listing, newest first.
- [`--until-found X`](until-found-parameter) checks assets newest first and stops once X files in a row were already downloaded. This keeps regular runs on a large library short.

With several `--album` options, both apply to each album separately.

`--recent` counts the assets before the filters below are applied, so `--recent 10 --skip-videos` checks the 10 newest assets and downloads the photos among them.

## Asset Types

- [`--skip-videos`](skip-videos-parameter) skips videos.
- [`--skip-photos`](skip-photos-parameter) skips photos. Only one of `--skip-videos` and `--skip-photos` can be used.
- [`--skip-live-photos`](skip-live-photos-parameter) skips the video part of Live Photos; the still image is still downloaded.

## Creation Date

[`--skip-created-before`](skip-created-before-parameter) and [`--skip-created-after`](skip-created-after-parameter) skip assets by the date they were created. Both accept:

- an ISO date or timestamp, e.g. `2025-06-01` or `2025-06-01T08:00:00+02:00`; without a time zone, the local time zone is used
- a number of days back from now, e.g. `30d`

Together they select a range; `--skip-created-before` must be earlier than `--skip-created-after`:

```shell
icloudpd --username my@email.address --directory /photos --skip-created-before 2025-04-01 --skip-created-after 2025-10-01
```
