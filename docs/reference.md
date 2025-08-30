# Reference

This is a list of all options available for the command line interface (CLI) of `icloudpd`

(until-found-parameter)=
`--until-found X`
    
:   Checks assets, from most recently added to the oldest, for their local copies. 
    Downloads if not present locally. The whole process stops once X number of subsequent checks result in a local file matching the remote.

    This option is a useful optimization for incremental updates: only a small portion (X) of the existing local storage will be rechecked for existence, saving on local I/O. However, the process will not "fill the gaps" in local storage if any exist (and will not identify them).

    ```{note}
    Assets are checked by the date they were added to iCloud, not by the date they were taken/created.
    ```

(recent-parameter)=
`--recent X`
    
:   Checks X most recently added assets for their local copies. 
    Downloads if not present locally. 

    This option is mostly useful while testing and experimenting with parameters to limit the volume of downloads.

    ```{note}
    Assets are checked by the date they were added to iCloud, not by the date they were taken/created.
    ```

(album-parameter)=
`--album X`
    
:   Specifies which album(s) to download.

    When not specified, the whole asset collection is considered.

    ```{versionchanged} 1.31.0
    Option may be specified multiple times to download from different albums
    ```    

(list-albums-parameter)=
`--list-albums`
    
:   Lists all available albums.

(library-parameter)=
`--library X`
    
:   Specifies which library to use.

    Default: "Personal Library".

    ```{note}
    Only one library can be used by `icloudpd`.
    ```    

    ```{versionadded} 1.16.0
    Shared library support added for iOS 16 shared libraries
    ```

(list-libraries-parameter)=
`--list-libraries`
    
:   Lists all libraries available for the account.

    ```{versionadded} 1.16.0
    Shared library support added for iOS 16 shared libraries
    ``` 

(watch-with-interval-parameter)=
`--watch-with-interval X`
    
:   Runs `icloudpd` forever, periodically re-checking iCloud for changes ("watch"). The interval is specified in seconds, e.g. 3600 will be a 1-hour interval.

    Too short an interval may trigger throttling on Apple's side, although no evidence has been reported.

    ```{versionadded} 1.10.0
    ```

(version-parameter)=
`--version`
    
:   Reports the current version and commit hash & date that the version was built from.

    ```{note}
    If `--use-os-locale` was specified before `--version`, then the date is formatted according to the OS locale.
    ```    

(use-os-locale-parameter)=
`--use-os-locale`
    
:   Instructs `icloudpd` to use the OS locale. If not specified (and by default), US English is used.

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
    
:   Access to Apple servers is blocked from mainland China. As an alternative, the iCloud service is available on an internal .cn domain, which can be specified for `icloudpd` to work from mainland China.

    Default is ".com". ".cn" is the only other option available.

    ```{versionadded} 1.9.0
    ```

(password-parameter)=
`--password X`
    
:   Specifies the iCloud password to use for authentication.

    ```{note}
    Supplying credentials through command line parameters is not considered a good practice since they can be logged and/or otherwise exposed. Consider using other [password providers](password-providers).
    ``` 

(directory-parameter)=
`--directory X`
    
:   Specifies the root folder where the [folder structure](folder-structure-parameter) will start and files will be downloaded.

(file-match-policy-parameter)=
`--file-match-policy X`
    
:   Specifies an algorithm (policy) to match remote files to local files.

    ```{versionadded} 1.20.0
    ```

    ```{seealso}
    Discussion of [File Naming and Deduplication](naming)
    ``` 

(username-parameter)=
`--username X`
    
:   Specifies the AppleID (email address) used for authenticating to iCloud. May be used multiple times to introduce different configurations and/or accounts. See [Using Multiple Accounts and Config](multiple-accounts-and-configs).

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
    
:   Customizes the size of the asset to download.

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
    
:   Customizes the size of the live photo assets to download.

(skip-videos-parameter)=
`--skip-videos`
    
:   If specified, video assets will not be processed.

(skip-photos-parameter)=
`--skip-photos`

    ```{versionadded} 1.30.0
    ```

    
:   If specified, photo assets will not be processed.

(skip-live-photos-parameter)=
`--skip-live-photos`
    
:   If specified, live photo assets will not be processed.

(auto-delete-parameter)=
`--auto-delete`
    
:   If specified, assets deleted in iCloud (actually moved to the Recently Deleted album) will also be deleted locally.

    ```{seealso}
    [Modes of operation](mode)
    ```

(delete-after-download-parameter)=
`--delete-after-download`
    
:   If specified, assets downloaded locally will be deleted in iCloud (actually moved to the Recently Deleted album). Deprecated, use [`--keep-icloud-recent-days`](keep-icloud-recent-days-parameter) instead.

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

:   If any filters are used, e.g., [`--skip-videos`](skip-videos-parameter), then assets excluded from processing by filters are not subject to deletion from iCloud. For example, running icloudpd with [`--skip-videos`](skip-videos-parameter) on a huge iCloud collection of videos will download and delete nothing.

:   The timestamp when the asset was taken (aka "created date") as reported by iCloud is used for calculating the age of the asset. For example, an asset taken in 2000, but added to iCloud in 2024, will be 25 years old in 2025. The same timestamp is used for the folder structure in the current system.

:   If the parameter is not specified, then nothing is deleted from iCloud.

    ```{versionadded} 1.26.0
    ```

    ```{seealso}
    [Modes of operation](mode)

    [Folder Structure](folder-structure)
    ```

(only-print-filenames-parameter)=
`--only-print-filenames`
    
:   If specified, no downloading will occur, but only file paths will be printed in the output (no other info goes into the output either).

    ```{seealso}
    [`--dry-run` parameter](dry-run-parameter)
    ```
(folder-structure-parameter)=
`--folder-structure X`
    
:   Specifies the subfolder naming scheme.

    ```{seealso}
    Details in the [Folder structure](folder-structure) section.
    ```

(set-exif-datetime-parameter)=
`--set-exif-datetime`
    
:   If specified, EXIF data for the image will be updated with the date/time the asset was taken/created. Only if EXIF does not already exist in the asset.

(no-progress-bar-parameter)=
`--no-progress-bar`
    
:   If specified, the progress bar is suppressed. This is valuable when streaming output to a file.

(keep-unicode-in-filenames-parameter)=
`--keep-unicode-in-filenames`
    
:   If specified, Unicode characters will be preserved in filenames. Otherwise they are removed (default).

    ```{versionadded} 1.18.0
    ```

(live-photo-mov-filename-policy-parameter)=
`--live-photo-mov-filename-policy X`
    
:   Customizes the naming of the video portion of live photos.

    ```{versionadded} 1.18.0
    ```

    ```{seealso}
    Details in the [Live Photo](naming) section.
    ```

(align-raw-parameter)=
`--align-raw X`
    
:   Customizes the treatment of RAW+JPEG assets.

    ```{versionadded} 1.19.0
    ```

    ```{seealso}
    Details in the [RAW+JPEG](raw) section.
    ```

(password-provider-parameter)=
`--password-provider X`
    
:   Customizes the intake of the password for iCloud authentication.

    ```{versionadded} 1.20.0
    ```

    ```{seealso}
    Details in the [Password providers](password-providers) section.
    ```
(mfa-provider-parameter)=
`--mfa-provider X`
    
:   Customizes the intake of the multi-factor authentication (MFA) code for iCloud authentication.

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
    
:   Settings for SMTP notifications for expired/needed authentication.

(notification-email-parameter)=
`--notification-email X`, `--notification-email-from X`
    
:   Settings for email notification addressing.

(notification-script-parameter)=
`--notification-script X`
    
:   Script to be executed for notifications on expired MFA.

(skip-created-before-parameter)=
`--skip-created-before`

:   Does not process assets created before the specified timestamp. The timestamp is in ISO format, e.g., 2025-06-01, or as an interval backwards from the current date, e.g., 5d (5 days ago). If the timezone is not specified for ISO format, then the local timezone is used.

    ```{versionadded} 1.28.0
    ```

    ```{note}
    The date is when the asset was created, not when it was added to iCloud.
    ```

(skip-created-after-parameter)=
`--skip-created-after`

:   Does not process assets created after the specified timestamp. The timestamp is in ISO format, e.g., 2025-06-01, or as an interval backwards from the current date, e.g., 5d (5 days ago). If the timezone is not specified for ISO format, then the local timezone is used.

    ```{versionadded} 1.29.0
    ```

    ```{note}
    The date is when the asset was created, not when it was added to iCloud.
    ```
