# Changelog

## Unreleased

## 1.7.2 (2021-01-16)

- fix: smtp server_hostname cannot be an empty [#227](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/227)
- fix: Warning for missing `tzinfo` in Docker image removed by adding `tzinfo`-package.
[#286](https://github.com/icloud-photos-downloader/icloud_photos_downloader/pull/286)

## 1.7.1 (2020-11-15)

- fix: dev docker build on windows correctly manages crlf for scripts

## 1.7.1rc1 (2020-11-10)

- fix: --only-print-filenames option displays filenames (live photos) of files that have already been downloaded #200
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
