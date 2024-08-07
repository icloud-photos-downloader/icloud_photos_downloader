# CLI Reference

This is a list of all options available for command line interface (CLI) of the `icloudpd`

(until-found-parameter)=
`--until-found X`
    
:   Checks assets, from most recently added to the oldest, for their local copies. 
    Downloads if not present locally. Whole process stops once X number of subsequent checks result in a local file matching remote.

    This option is a useful optimization for incremental updates: only small portion (X) of the existing local storage will be rechecked for existence, saving on local IO. However, the process will not "fill the gaps" in local storage if any exist (and will not identify them).

    ```{note}
    Assets are checked by the date they were added to iCloud, not by the date they were taken/created.
    ```

(recent-parameter)=
`--recent X`
    
:   Checks X most recently added assets for their local copies. 
    Downloads if not present locally. 

    This option is mostly useful while testing and experimenting with parameters to limit the volume of downloads

    ```{note}
    Assets are checked by the date they were added to iCloud, not by the date they were taken/created.
    ```

(album-parameter)=
`--album X`
    
:   Specifies what Album to download. 

    Default: "All Photos" - Special album where all assets are automatically added.

    ```{note}
    Only one album can be downloaded by `icloudpd`
    ```    

(list-albums-parameter)=
`--list-albums`
    
:   Lists all available albums 

(library-parameter)=
`--library X`
    
:   Specifies what Libarary to use. 

    Default: "Personal Library".

    ```{note}
    Only one library can be used by `icloudpd`
    ```    

(list-libraries-parameter)=
`--list-libraries`
    
:   Lists all libraries available for account 

(watch-with-interval-parameter)=
`--watch-with-interval X`
    
:   Runs `icloudpd` forever, periodically re-checking iCloud for changes ("watch"). Interval is specified in seconds, e.g. 3600 will be 1hr interval.

    Too short interval may trigger throttling on Apple side, although no evidence has been reported.

(version-parameter)=
`--version`
    
:   Reports current version and commit hash & date that version was build from.

    ```{note}
    If `--use-os-locale` was specified before `--version`, then date is formatted according to OS locale.
    ```    

(use-os-locale-parameter)=
`--use-os-locale`
    
:   Instructs `icloudpd` to use OS locale. If not specified (and by default), US English is used.

    ```{seealso}
    [File Naming](naming) section discusses affected behavior
    ```    

(dry-run-parameter)=
`--dry-run`
    
:   If specified, no changes to local storage or iCloud remote storage is made.

    Authentication will be performed and remote files will be checked against local storage. Any difference will be reported instead of performing download.

    This parameter is useful for experimenting with new parameters

(domain-parameter)=
`--domain X`
    
:   Access to Apple servers is blocked from mainland China. As an alternative, iCloud service is available on internal .cn domain, which can be specified for `icloudpd` to work from mainland China.

    Default is ".com". ".cn" is the only other option available.

(password-parameter)=
`--password X`
    
:   Specifies iCloud password to use for authentication

    ```{note}
    Supplying credentials through command line parameters is considered not a good practice since they can be logged and/or otherwise exposed. Consider using other [password providers](authentication).
    ``` 

(directory-parameter)=
`--directory X`
    
:   Specifies root folder where [folder structure](naming) will start and files will be downloaded.

(file-match-policy-parameter)=
`--file-match-policy X`
    
:   Specifies an algorithm (policy) to match remote to local files.

    ```{seealso}
    Discussion on [File Naming and Deduplication](naming)
    ``` 

