# Changelog

## Unreleased

- fix: docker works on Windows #192

## 1.7.0 (2020-11-1)

- fix: --log-level option [#194](https://github.com/icloud-photos-downloader/icloud_photos_downloader/pull/194)
- feature: Folder structure can be set to 'none' instead of a date pattern,
so all photos will be placed directly into the download directory.
- fix: Empty directory structure being created #185
- feature: removed multi-threaded downloading and added deprecation notice to --threads-num parameter #180, #188
- fix: documentation issues, first adressed in #141 and seperated contribution
info from README.md into CONTRIBUTING.md

## 1.6.2 (2020-10-23)

- Began recording updates in `CHANGELOG.md`
- fix: reduce chances of IOErrors by changing default --threads_num to 1 #155, #163
- fix: reduce chances of errors due to missing required parameters #175
- fix: missing downloading process by upgrading tqdm dependency #167

--------------------------------------------

## Earlier Versions

Please refer to the commit history in GitHub:
<https://github.com/icloud-photos-downloader/icloud_photos_downloader/commits/master>
