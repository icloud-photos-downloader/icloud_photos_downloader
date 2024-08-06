# CLI Reference

This is a list of all options available for command line interface (CLI) of the `icloudpd`

(until-found-parameter)=
`--until-found X`
    
:   Checks photos, from most recently added to the oldest, for their local copies. 
    Downloads if not present locally. Whole process stops once X number of subsequent checks result in a local file matching remote.

    This option is a useful optimization for incremental updates: only small portion (X) of the existing local storage will be rechecked for existence, saving on local IO. However, the process will not "fill the gaps" in local storage if any exist (and will not identify them).

    ```{note}
    Photos are checked by the date they were added to iCloud, not by the date they were taken/created.
    ```

(recent-parameter)=
`--recent X`
    
:   Checks X most recently added photos for their local copies. 
    Downloads if not present locally. 

    This option is mostly useful while testing and experimenting with parameters to limit the volume of downloads

    ```{note}
    Photos are checked by the date they were added to iCloud, not by the date they were taken/created.
    ```