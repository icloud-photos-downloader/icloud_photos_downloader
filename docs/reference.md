# Reference

This page describes the command line options of `icloudpd`.

Options are of three kinds:

- **Global options** apply to the whole run and may appear anywhere on the command line:
  [`--help`](help-parameter), [`--version`](version-parameter),
  [`--use-os-locale`](use-os-locale-parameter),
  [`--only-print-filenames`](only-print-filenames-parameter),
  [`--log-level`](log-level-parameter), [`--no-progress-bar`](no-progress-bar-parameter),
  [`--threads-num`](threads-num-parameter), [`--domain`](domain-parameter),
  [`--watch-with-interval`](watch-with-interval-parameter),
  [`--password-provider`](password-provider-parameter) and
  [`--mfa-provider`](mfa-provider-parameter). Their entries below say "Global option."
- **User options** are [`--username`](username-parameter) and [`--password`](password-parameter).
  Each `--username` starts a new configuration.
- **All other options** belong to a configuration. Given after a `--username`, they apply to that
  configuration only. Given before the first `--username`, they are defaults for all
  configurations. See [Using Multiple Accounts and Config](multiple-accounts-and-configs).

When options are combined in a way that can't work, `icloudpd` prints a message and exits with
code 2 without doing anything. The rejected combinations are listed with each option.

(until-found-parameter)=
`--until-found X`
    
:   Checks assets, from most recently added to the oldest, for their local copies. 
    Downloads if not present locally. The whole process stops once X number of subsequent checks result in a local file matching the remote.

    This option is a useful optimization for incremental updates: only a small portion (X) of the existing local storage will be rechecked for existence, saving on local I/O. However, the process will not "fill the gaps" in local storage if any exist (and will not identify them).

    With several [`--album`](album-parameter) options, the count applies to each album separately.

    ```{note}
    Assets are checked by the date they were added to iCloud, not by the date they were taken/created.
    ```

(recent-parameter)=
`--recent X`
    
:   Checks X most recently added assets for their local copies. 
    Downloads if not present locally. 

    This option is mostly useful while testing and experimenting with parameters to limit the volume of downloads.

    With several [`--album`](album-parameter) options, X assets are checked in each album.

    ```{note}
    Assets are checked by the date they were added to iCloud, not by the date they were taken/created.
    ```

(album-parameter)=
`--album X`, `-a X`
    
:   Specifies which album(s) to download.

    When not specified, the whole asset collection is considered.

    ```{versionchanged} 1.31.0
    Option may be specified multiple times to download from different albums
    ```    

    An album in a folder is named by its path, as shown by
    [`--list-albums`](list-albums-parameter), e.g. `--album "Trips/2024/Italy"`.

(list-albums-parameter)=
`--list-albums`, `-l`
    
:   Lists all available albums.

    Albums in folders are listed with the folder names in front, e.g. `Trips/2024/Italy`
    for the album "Italy" in the folder "2024" in the folder "Trips". Folders themselves
    are not listed, since they hold no photos of their own.

(library-parameter)=
`--library X`
    
:   Specifies which library to use.

    Default: `PrimarySync` (the personal library). Use the name exactly as printed by [`--list-libraries`](list-libraries-parameter), e.g. `SharedSync-…` for a shared library.

    ```{note}
    Each configuration downloads from one library. To download from several, repeat `--username` with a different `--library` for each, see [Using Multiple Accounts and Config](multiple-accounts-and-configs).
    ```    

    ```{versionadded} 1.16.0
    Shared library support added for iOS 16 shared libraries
    ```

(prune-orphans-parameter)=
`--prune-orphans`

:   Moves unchanged, tracked local downloads out of the active mirror when their photos disappear from
    the selected shared library, including photos moved to a participant's
    personal library without entering Recently Deleted. This is separate from
    `--auto-delete`, whose behavior is unchanged.

    ```{versionadded} 1.33.0
    ```

    Use `--library` to select a shared library and a dedicated `--directory` that
    is not shared with other accounts, libraries, or downloader processes.
    Overlapping destinations in the same command are rejected.

    Files are tracked only when icloudpd writes them while this option
    is enabled. The first successful run saves a baseline in `.icloudpd-prune.json`;
    it does not move anything. Later runs compare the library's current photo IDs
    with the recorded IDs and quarantine only recorded files whose content has not changed.
    Actual download paths are recorded, including deduplicated filenames, Live
    Photo videos and newly created XMP sidecars. Existing untracked files are kept
    even if their names match a current photo. Old orphans predating tracking are
    not cleaned by this option.

    Each managed file is fingerprinted with its size and SHA-256. This reads new
    downloads once more, which can be
    noticeable for large videos. Candidates are hashed again before being moved;
    locally changed files are kept.

    A separate, full inventory is read even when downloads are limited by
    `--recent`, `--until-found`, albums or date/type filters. Hidden photos count
    as present, and files are retained while any asset referencing the same
    original remains in the library. Empty, count-mismatched, duplicate or
    changing-count listings, cancellation and failed downloads prevent pruning
    and baseline updates. Count checks cannot detect an Apple index that is
    consistently incomplete: a matching count is not proof that a photo was removed.
    For that reason, pruning never permanently deletes files.
    `--dry-run` reports candidates without changing files or tracking state.

    Files are moved to `.icloudpd-pruned/<unique-batch>/` inside the destination,
    preserving their relative paths and never overwriting an earlier batch.
    **Exclude `.icloudpd-pruned/` and its contents from external photo-library or
    gallery scans**; do not assume every scanner ignores hidden directories.
    There is no automatic restoration or purge, and quarantine does not reclaim disk space.
    Periodically check its disk usage (for example, `du -sh .icloudpd-pruned` on
    POSIX systems) and review old batches before manually removing them.
    To restore a file, stop the downloader and move it from its batch back to the
    same relative path under the destination, without overwriting a newer file.
    If a photo reappears in iCloud, normal downloading may create another active
    copy; the quarantined copy is still retained. Review batches before removing them manually.

    The snapshot is bound to the account, library, time zone and output settings,
    not download limits or filters such as `--recent` and `--until-found`.
    Context mismatches, busy or unsupported locks, inventory errors and tracking
    failures warn and skip pruning without failing or stopping the download run.
    They do not migrate or advance the baseline. Use a new dedicated directory
    for a different output configuration. Removing the snapshot explicitly
    resets tracking; previously downloaded files then become untracked and are kept.
    Do not edit the snapshot or run other
    downloaders against its destination.

    The option is rejected (exit code 2) without a shared library selected with `--library`
    (the default `PrimarySync` is not accepted), when combined with `--delete-after-download`,
    `--keep-icloud-recent-days` or `--only-print-filenames`, and when its `--directory`
    is inside, or contains, the `--directory` of another configuration in the same command.
    An empty shared library is deliberately not pruned; remove its local files manually if intended.

    An OS lock on `.icloudpd-prune.lock` prevents overlapping pruning runs
    (`flock` on POSIX, byte-range locking on Windows). The OS releases it when
    the process exits, including after a crash; the lock file intentionally remains
    and does not need removing. Never delete it while another run might hold it.
    A filesystem that cannot provide the lock only disables pruning, not downloads.
    The snapshot is atomically replaced after a successful pruning run.
    Interrupted or failed runs can leave new files untracked or some files already
    quarantined, but no bytes are permanently deleted. Those untracked files are
    preserved rather than guessed to be safe to move.

(prune-orphans-adopt-existing-parameter)=
`--prune-orphans-adopt-existing`

:   Explicitly adopts an existing dedicated shared-library mirror on the first
    successful `--prune-orphans` run. Unlike normal tracking, this also handles
    old orphans that disappeared from iCloud before tracking was enabled.

    ```{versionadded} 1.33.0
    ```

    **This declares that all recognized photo/video files and associated
    `.<media-extension>.xmp` sidecars directly in `--directory` belong exclusively
    to the selected shared-library mirror.** Ownership cannot be inferred from
    filenames. Do not use it on a directory containing personal files, multiple
    libraries or files from other size/naming settings. Existing local edits are
    taken as the adoption baseline; they cannot be identified retroactively.

    Bootstrap is deliberately limited to `--folder-structure none`, original
    photo and Live Photo video sizes, Live Photos enabled, `--align-raw as-is`,
    `--file-match-policy name-size-dedup-with-suffix` and
    `--live-photo-mov-filename-policy suffix`. Keep the same filename-cleaning and
    output settings that produced the existing mirror. Other layouts are not migrated.

    The option is rejected (exit code 2) without `--prune-orphans`, and when any of these
    settings differ: `--folder-structure` other than `none`, a `--size` other than `original`,
    `--live-photo-size` other than `original`, `--skip-live-photos`, or another
    `--align-raw`, `--file-match-policy` or `--live-photo-mov-filename-policy`.

    A validated full inventory, including Hidden, is matched using the downloader's
    filename selection in an inspection-only mode, without fetching media or
    writing metadata. Matching is **name-first, not size-first**: current canonical
    names, known legacy `-original` names and current size-suffixed collision names
    are retained even if EXIF rewriting or another tool changed their size.
    Live Photo videos and associated sidecars use the same protection. Only media
    whose name matches no current photo is quarantined in the bootstrap run.

    Ambiguous matches are deliberately retained: if multiple current photos share
    a filename, the base file is kept while any of them remains. This can preserve
    an old orphan with a colliding name rather than risk moving a current file.
    Adoption does not change the normal downloader's size-based deduplication or
    fix its existing EXIF-related duplicate-download behavior.

    Matching existing files are fingerprinted with their current size/SHA-256 and
    enrolled for future tracked pruning. This reads each adopted file, including
    large videos, once more. Non-media files, temporary files and subdirectories
    (including NAS metadata and previous quarantine batches) are left alone.
    Unsafe or symlinked candidates stop bootstrap with a warning rather than
    following them. Quarantine and restoration work as described above.

    Preview using your existing command and unchanged settings, for example:

    ```sh
    icloudpd --username user@icloud.com --library 'SharedSync-YOUR-LIBRARY-ID' \
      --directory ./shared-library --folder-structure none --size original \
      --prune-orphans --prune-orphans-adopt-existing --dry-run
    ```

    Back up the mirror and review every candidate before repeating without
    `--dry-run`. Once a baseline exists, this option does not rescan or adopt
    additional untracked media, even in watch mode. Remove it after successful
    adoption and keep `--prune-orphans` for ordinary runs. If the snapshot is later
    removed while the bootstrap flag remains enabled, adoption will run again.

(list-libraries-parameter)=
`--list-libraries`
    
:   Lists all libraries available for the account.

    ```{versionadded} 1.16.0
    Shared library support added for iOS 16 shared libraries
    ``` 

(watch-with-interval-parameter)=
`--watch-with-interval X`
    
:   Runs `icloudpd` forever, periodically re-checking iCloud for changes ("watch"). The interval is specified in seconds, e.g. 3600 will be a 1-hour interval.

    Global option.

    Too short an interval may trigger throttling on Apple's side, although no evidence has been reported.

    Can't be combined with [`--list-albums`](list-albums-parameter),
    [`--list-libraries`](list-libraries-parameter),
    [`--only-print-filenames`](only-print-filenames-parameter) or
    [`--auth-only`](auth-only-parameter) (exit code 2).

    ```{versionadded} 1.10.0
    ```

(version-parameter)=
`--version`
    
:   Reports the current version and commit hash & date that the version was built from, and exits.

    Global option. Can't be combined with [`--help`](help-parameter).

    ```{note}
    If `--use-os-locale` is also specified, then the date is formatted according to the OS locale.
    ```    

(use-os-locale-parameter)=
`--use-os-locale`
    
:   Instructs `icloudpd` to use the OS locale. If not specified (and by default), US English is used.

    Global option.

    ```{versionadded} 1.22.0
    ```

    ```{seealso}
    The [File Naming](naming) section discusses the affected behavior
    ```    

(dry-run-parameter)=
`--dry-run`
    
:   If specified, no changes to local storage or iCloud remote storage are made.

    Authentication will be performed and remote files will be checked against local storage. Any differences will be reported instead of performing downloads.

    This parameter is useful for experimenting with new parameters.

    ```{versionadded} 1.15.0
    ```

(domain-parameter)=
`--domain X`
    
:   Access to Apple servers is blocked from mainland China. As an alternative, the iCloud service is available on an internal `.cn` domain, which can be specified for `icloudpd` to work from mainland China.

    Global option. Default is `com`. `cn` is the only other option available (`--domain cn`).

    ```{versionadded} 1.9.0
    ```

(password-parameter)=
`--password X`, `-p X`
    
:   Specifies the iCloud password to use for authentication. User option: it applies to the
    configuration started by the `--username` before it. It is used only when
    [`--password-provider`](password-provider-parameter) includes `parameter` (the default does).

    ```{note}
    Supplying credentials through command line parameters is not considered a good practice since they can be logged and/or otherwise exposed. Consider using other [password providers](password-providers).
    ``` 

(directory-parameter)=
`--directory X`, `-d X`
    
:   Specifies the root folder where the [folder structure](folder-structure-parameter) will start and files will be downloaded.

    Required for each configuration, unless [`--auth-only`](auth-only-parameter),
    [`--list-albums`](list-albums-parameter) or [`--list-libraries`](list-libraries-parameter)
    is given. Without it, `icloudpd` exits with code 2.

(file-match-policy-parameter)=
`--file-match-policy X`
    
:   Specifies an algorithm (policy) to match remote files to local files: `name-size-dedup-with-suffix` (default) or `name-id7`.

    ```{versionadded} 1.20.0
    ```

    ```{seealso}
    Discussion of [File Naming and Deduplication](naming)
    ``` 

(username-parameter)=
`--username X`, `-u X`
    
:   Specifies the Apple ID (email address) used for authenticating to iCloud. The value is
    converted to lower case.

    Required: without a `--username`, `icloudpd` downloads nothing.

    Each `--username` starts a new configuration. Options after it, up to the next `--username`,
    apply to that configuration only. May be used multiple times to introduce different
    configurations and/or accounts. See [Using Multiple Accounts and Config](multiple-accounts-and-configs).

    ```{versionchanged} 1.32.0
    Option may be specified multiple times
    ```

(adp-web-access-parameter)=
`--adp-web-access`
    
:   Requests iCloud web access consent after authentication, which is required for accounts with Advanced Data Protection (ADP). Needs `Access iCloud Data on the Web` enabled on the account. The first run asks you to approve a notification on an Apple device. See [ADP](authentication.md).

    ```{versionadded} 1.33.0
    ```

(auth-only-parameter)=
`--auth-only`
    
:   Performs authentication, persists authentication results (tokens/cookies), and exits without processing assets.

    ```{versionadded} 1.17.0
    ```

(cookie-directory-parameter)=
`--cookie-directory X`
    
:   Customizes the folder used for persisting authentication results (cookies/tokens). If not specified, `~/.pyicloud` is used.

(size-parameter)=
`--size X`
    
:   Customizes the size of the asset to download: `original` (default), `medium`, `thumb`,
    `adjusted` or `alternative`. May be specified multiple times to download several sizes.

    ```{versionchanged} 1.19.0
    Option may be specified multiple times. `adjusted` and `alternative` added
    ```

    ```{seealso}
    Details on [Asset sizes](size)
    ```

(force-size-parameter)=
`--force-size`
    
:   If specified, only the requested size will be downloaded. Otherwise, the `original` size will be downloaded instead of the missing size.

    ```{seealso}
    [`--size` parameter](size-parameter)
    ```

(live-photo-size-parameter)=
`--live-photo-size X`
    
:   Customizes the size of the video part of Live Photos to download: `original` (default),
    `medium` or `thumb`.

    ```{versionchanged} 1.33.0
    `thumb` works; before, it stopped `icloudpd` at startup
    ```

(skip-videos-parameter)=
`--skip-videos`
    
:   If specified, video assets will not be processed.

    Can't be combined with [`--skip-photos`](skip-photos-parameter) in the same configuration (exit code 2).

(skip-photos-parameter)=
`--skip-photos`
    
:   If specified, photo assets will not be processed.

    Can't be combined with [`--skip-videos`](skip-videos-parameter) in the same configuration (exit code 2).

    ```{versionadded} 1.30.0
    ```

(skip-live-photos-parameter)=
`--skip-live-photos`
    
:   If specified, the video part of Live Photos is not downloaded. The still image is still downloaded.

(auto-delete-parameter)=
`--auto-delete`
    
:   If specified, assets deleted in iCloud (actually moved to the Recently Deleted album) will also be deleted locally.

    Can't be combined with [`--keep-icloud-recent-days`](keep-icloud-recent-days-parameter) or
    [`--delete-after-download`](delete-after-download-parameter) (exit code 2): the assets they
    move to Recently Deleted would then be deleted locally as well.

    ```{seealso}
    [Modes of operation](mode)
    ```

(delete-after-download-parameter)=
`--delete-after-download`
    
:   If specified, assets downloaded locally will be deleted in iCloud (actually moved to the Recently Deleted album). Deprecated, use [`--keep-icloud-recent-days`](keep-icloud-recent-days-parameter) instead.

    Can't be combined with [`--auto-delete`](auto-delete-parameter),
    [`--keep-icloud-recent-days`](keep-icloud-recent-days-parameter) or
    [`--prune-orphans`](prune-orphans-parameter) (exit code 2).

    ```{note}
    If remote assets were not downloaded, e.g., because they were already in local storage, they will NOT be deleted in iCloud.
    ```

    ```{versionadded} 1.8.0
    ```

    ```{deprecated} 1.26.0
    ```

(keep-icloud-recent-days-parameter)=
`--keep-icloud-recent-days X`
    
:   Deletes assets in iCloud after they were downloaded or confirmed to be present locally, except for the ones taken within the specified number of days. If set to 0, all photos will be deleted from iCloud.

    If any filters are used, e.g., [`--skip-videos`](skip-videos-parameter), then assets excluded from processing by filters are not subject to deletion from iCloud. For example, running icloudpd with [`--skip-videos`](skip-videos-parameter) on a huge iCloud collection of videos will download and delete nothing.

    The timestamp when the asset was taken (aka "created date") as reported by iCloud is used for calculating the age of the asset. For example, an asset taken in 2000, but added to iCloud in 2024, will be 25 years old in 2025. The same timestamp is used for the folder structure in the current system.

    Assets for which iCloud reports no creation date are not deleted, because their age is unknown. icloudpd logs a warning for each of them.

    If the parameter is not specified, then nothing is deleted from iCloud.

    Can't be combined with [`--auto-delete`](auto-delete-parameter), which would delete the local copies of the assets this moves to Recently Deleted, or with [`--delete-after-download`](delete-after-download-parameter) or [`--prune-orphans`](prune-orphans-parameter) (exit code 2).

    Only assets that the run looks at are considered for deletion. With [`--recent`](recent-parameter), assets beyond the first X are not checked, and with [`--until-found`](until-found-parameter), assets after the point where the run stops are not checked, so they stay in iCloud. icloudpd logs a warning at startup when these are combined.

    ```{versionadded} 1.26.0
    ```

    ```{seealso}
    [Modes of operation](mode)

    [Folder Structure](folder-structure)
    ```

(only-print-filenames-parameter)=
`--only-print-filenames`
    
:   If specified, no downloading will occur, but only file paths will be printed in the output (no other info goes into the output either). Nothing is deleted, locally or in iCloud.

    Global option. Can't be combined with [`--watch-with-interval`](watch-with-interval-parameter)
    or [`--prune-orphans`](prune-orphans-parameter) (exit code 2).

    ```{seealso}
    [`--dry-run` parameter](dry-run-parameter)
    ```

(folder-structure-parameter)=
`--folder-structure X`
    
:   Specifies the subfolder naming scheme, applied to the creation date of each asset.
    Default: `{:%Y/%m/%d}`. Use `none` to put all files directly into
    [`--directory`](directory-parameter). A format that can't be applied to a date is rejected
    at startup.

    ```{seealso}
    Details in the [Folder structure](folder-structure) section.
    ```

(set-exif-datetime-parameter)=
`--set-exif-datetime`
    
:   If specified, the date/time the asset was taken/created is written into the EXIF tags
    `DateTime`, `DateTimeOriginal` and `DateTimeDigitized` of newly downloaded JPEG files that have
    no `DateTimeOriginal` tag yet. Other files are not changed.

(no-progress-bar-parameter)=
`--no-progress-bar`
    
:   If specified, the progress bar is suppressed. This is valuable when streaming output to a file.
    The progress bar is also suppressed when no terminal is attached.

    Global option.

(log-level-parameter)=
`--log-level X`

:   Sets the level of log messages: `debug` (default), `info` or `error`.

    Global option. Ignored with [`--only-print-filenames`](only-print-filenames-parameter),
    which turns off all log messages.

(keep-unicode-in-filenames-parameter)=
`--keep-unicode-in-filenames`
    
:   If specified, Unicode characters will be preserved in filenames. Otherwise they are removed (default).

    ```{versionadded} 1.18.0
    ```

(live-photo-mov-filename-policy-parameter)=
`--live-photo-mov-filename-policy X`
    
:   Customizes the naming of the video portion of live photos: `suffix` (default) adds `_HEVC`
    to the name, `original` keeps the name as is.

    ```{versionadded} 1.18.0
    ```

    ```{seealso}
    Details in the [Live Photo](naming) section.
    ```

(align-raw-parameter)=
`--align-raw X`
    
:   Customizes the treatment of RAW+JPEG assets: `as-is` (default), `original` or `alternative`.

    ```{versionadded} 1.19.0
    ```

    ```{seealso}
    Details in the [RAW+JPEG](raw) section.
    ```

(password-provider-parameter)=
`--password-provider X`
    
:   Customizes the intake of the password for iCloud authentication: `parameter`, `keyring`,
    `console` or `webui`. May be specified multiple times; providers are tried in the given order.
    Default: `parameter`, `keyring`, `console`.

    Global option.

    ```{versionadded} 1.20.0
    ```

    ```{versionchanged} 1.21.0
    `webui` added
    ```

    ```{seealso}
    Details in the [Password providers](password-providers) section.
    ```

(mfa-provider-parameter)=
`--mfa-provider X`
    
:   Customizes the intake of the multi-factor authentication (MFA) code for iCloud authentication:
    `console` (default) or `webui`.

    Global option.

    ```{versionadded} 1.21.0
    ```

    ```{seealso}
    Details in the [MFA providers](authentication) section.
    ```

(xmp-sidecar-parameter)=
`--xmp-sidecar`

:   Exports additional data as XMP sidecar files (default: don't export).

    ```{versionadded} 1.25.0
    ```

(smtp-parameter)=
`--smtp-username X`, `--smtp-password X`, `--smtp-host X`, `--smtp-port X`, `--smtp-no-tls`
    
:   Settings for email notifications when two-factor authentication is required.
    An email is sent whenever iCloud asks for a code, if `--smtp-username` or
    [`--notification-email`](notification-email-parameter) is set.

    - `--smtp-username`, `--smtp-password`: account for the SMTP server. `icloudpd` logs in
      only when both are set.
    - `--smtp-host`: default `smtp.gmail.com`.
    - `--smtp-port`: default `587`.
    - `--smtp-no-tls`: turns off STARTTLS, which is used by default.

(notification-email-parameter)=
`--notification-email X`, `--notification-email-from X`
    
:   Settings for email notification addressing.

    - `--notification-email`: recipient. Default: the SMTP username.
    - `--notification-email-from`: sender. Default: `iCloud Photos Downloader <SMTP username>`,
      or the recipient if there is no SMTP username.

(notification-script-parameter)=
`--notification-script X`
    
:   Path to a script that is run, without arguments, whenever iCloud asks for a
    two-factor authentication code, before `icloudpd` waits for the code.

(skip-created-before-parameter)=
`--skip-created-before X`

:   Does not process assets created before the specified timestamp. The timestamp is an ISO date or date-time, e.g., `2025-06-01` or `2025-06-01T12:00:00+02:00`, or an interval in days backwards from the current date, e.g., `5d` (5 days ago). Only days are supported as interval unit. If an ISO timestamp has no time zone, the local time zone is used.

    ```{versionadded} 1.28.0
    ```

    ```{note}
    The date is when the asset was created, not when it was added to iCloud.
    ```

(skip-created-after-parameter)=
`--skip-created-after X`

:   Does not process assets created after the specified timestamp. The timestamp is an ISO date or date-time, e.g., `2025-06-01` or `2025-06-01T12:00:00+02:00`, or an interval in days backwards from the current date, e.g., `5d` (5 days ago). Only days are supported as interval unit. If an ISO timestamp has no time zone, the local time zone is used.

    ```{versionadded} 1.29.0
    ```

    ```{note}
    To process a date range, combine it with `--skip-created-before`, which sets the start of the range: `--skip-created-before 2025-04-01 --skip-created-after 2025-10-01` processes assets created between April 1 and October 1, 2025. `--skip-created-before` must be earlier than `--skip-created-after`, otherwise `icloudpd` exits with code 2.
    ```

    ```{note}
    The date is when the asset was created, not when it was added to iCloud.
    ```

(help-parameter)=
`--help`, `-h`

:   Shows a summary of all options and exits. Also shown when `icloudpd` is run without any options.

    Global option. Can't be combined with [`--version`](version-parameter).

(threads-num-parameter)=
`--threads-num X`

:   Has no effect: downloads always use one thread. Kept for compatibility and will be removed in a future version.

    Global option.

    ```{deprecated} 1.7.0
    ```
