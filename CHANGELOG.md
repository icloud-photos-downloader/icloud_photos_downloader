# Changelog

## Unreleased

## 1.17.3 (2024-01-03)

- improve compatibility for diffeent platforms [#748](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/748)

## 1.17.2 (2023-12-22)

- fix: module not found [#748](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/748)

## 1.17.1 (2023-12-20)

- fix: main macos binary failing [#668](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/668) [#700](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/700)
- fix: debian glibc error [#741](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/741)

## 1.17.0 (2023-12-19)

- fix: macos binary failing [#668](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/668) [#700](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/700)
- fix: 'Invalid email/password combination' exception due to recent iCloud changes [#729](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/729)
- feature: `--auth-only` parameter to independently create/validate session tokens without listing/downloading photos
- feature: 2FA validation merged from `pyicloud`

## 1.16.3 (2023-12-04)

- fix: file date attribute [#714](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/714)
- fix: `icloud --username` parameter reported as not an option [#719](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/719)

## 1.16.2 (2023-09-30)

- fix: send logs to stdout [#697](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/697)

## 1.16.1 (2023-09-27)

- fix: shared libraries throw INTERNAL_ERROR for some users [#690](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/690)

## 1.16.0 (2023-09-25)

- feature: shared library support with `--list-libraries` and `--library` parameters [#455](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/455), [#489](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/489), [#678](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/678)

## 1.15.1 (2023-07-16)

- fix: excessive logging for existing and deduplicated files
- fix: add missing docker platforms back

## 1.15.0 (2023-07-16)

- fix: logs when progress bar enabled
- feature: `--dry-run` parameter to run icloudpd without changes to local files and iCloud
- fix: pypi.org license and description

## 1.14.5 (2023-07-06)

- fix: pypi publishing for macos

## 1.14.4 (2023-07-06)

- fix: docker auth during publishing

## 1.14.3 (2023-07-06)

- add binary wheel without dependencies to pypi
- fix: remove tests from pypi distributions

## 1.14.2 (2023-07-03)

- fix: finite retry on unhandled errors during photo iteration [#642](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/642)
- fix: retry on internal error during deletion [#615](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/615)

## 1.14.1 (2023-07-02)

- fix: retry authN on session error during deletion [#647](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/647)

## 1.14.0 (2023-07-01)

- fix: auto-delete date mismatch [#345](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/345)
- fix: `--version` parameter

## 1.13.4 (2023-06-14)

- experimental: fix npm packaging

## 1.13.4 (2023-06-11)

- experimental: fix npm registry publishing

## 1.13.2 (2023-06-10)

- experimental: fix npm registry publishing

## 1.13.1 (2023-06-10)

- experimental: add support for distributing `icloudpd` with [npm](README_NPM.md) package manager

## 1.13.0 (2023-04-21)

- fix: only delete files successfully downloaded [#614](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/614)

## 1.12.0 (2023-03-10)

- experimental: add macos binary [#551](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/551)
- fix: add `icloud` script to the source distribution [#594](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/594)

## 1.11.0 (2023-02-24)

- feature: add experimental mode for new cli

## 1.10.0 (2023-02-17)

- feature: add `--watch-with-interval` parameter [#568](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/568)
- fix: allow spaces in filenames [#378](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/378)
- feature: add `--notification-email-from` parameter [#496](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/496)

## 1.9.0 (2023-02-10)

- fix: replace invalid chars in filenames with '_' [#378](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/378)
- feature: add `--domain` parameter to support mainland China [#572](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/572), [#545](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/545)
- feature: add `linux/arm/v7` and `linux/arm/v6` docker image [#434](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/434)

## 1.8.1 (2023-02-03)

- fix: avoid crash when downloading over legacy `-original` name [#338](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/338)
- fix: remove mac binary unitl Apple signing is supported [#551](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/551)
- fix: PyPI distribution [#549](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/549)
- fix: keyring error [#539](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/539)

## 1.8.0 (2023-01-27)

- update dependencies to solve [#539](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/539)
- feature: a new command line option `--delete-after-download` to allow user to delete photos in the iCloud right after download is complete. [#431](https://github.com/icloud-photos-downloader/icloud_photos_downloader/pull/431), [#368](https://github.com/icloud-photos-downloader/icloud_photos_downloader/pull/368) [#314](https://github.com/icloud-photos-downloader/icloud_photos_downloader/pull/314) [#124](https://github.com/icloud-photos-downloader/icloud_photos_downloader/pull/124) [#332](https://github.com/icloud-photos-downloader/icloud_photos_downloader/pull/332)

## 1.7.3 (2023-01-20)

- deprecating python 3.6
- experimental: package `icloudpd` & `icloud` as executables [#146](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/146)

## 1.7.2 (2021-01-16)

- fix: smtp server_hostname cannot be an empty [#227](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/227)
- fix: Warning for missing `tzinfo` in Docker image removed by adding `tzinfo`-package.
[#286](https://github.com/icloud-photos-downloader/icloud_photos_downloader/pull/286)

## 1.7.1 (2020-11-15)

- fix: dev Docker build on Windows correctly manages crlf for scripts

## 1.7.1rc1 (2020-11-10)

- fix: --only-print-filenames option displays filenames (live photos) of files that have already been downloaded #200
- fix: docker works on Windows #192

## 1.7.0 (2020-11-1)

- fix: --log-level option [#194](https://github.com/icloud-photos-downloader/icloud_photos_downloader/pull/194)
- feature: Folder structure can be set to 'none' instead of a date pattern,
so all photos will be placed directly into the download directory.
- fix: Empty directory structure being created #185
- feature: removed multi-threaded downloading and added deprecation notice to --threads-num parameter #180, #188
- fix: documentation issues, first addressed in #141 and separated contribution
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
