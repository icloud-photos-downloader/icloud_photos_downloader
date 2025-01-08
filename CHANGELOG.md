# Change log

## Unreleased

- feature: add `--keep-icloud-recent-days` parameter to keep photos newer than this many days in iCloud. Deletes the rest.

## 1.25.1 (2024-12-28)

- chore: bump max/default python version 3.12->3.13
- chore: bump min python version 3.8->3.9
- fix: fallback to old raw password auth if srp auth fails [#975](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/975)

## 1.25.0 (2024-12-03)

- fix: failed to authenticate for accounts with srp s2k_fo auth protocol [#975](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/975)
- fix: failed to login non-2FA account for the first attempt [#1012](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/1012)
- fix: log more information for authentication error [#1010](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/1010)
- feature: add support for XMP files with `--xmp-sidecar` parameter [#448](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/448), [#102](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/102), [#789](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/789)

## 1.24.4 (2024-11-18)

- fix: deprecate macos-12 [#1000](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/1000)
- fix: sms MFA dropping leading zeros [#993](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/993)

## 1.24.3 (2024-11-03)

- fix: crashes when no imagetype sent by Apple [ref](https://github.com/boredazfcuk/docker-icloudpd/issues/680)

## 1.24.2 (2024-11-02)

- fix: errors for accounts with salt started with zero byte [#975](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/975)

## 1.24.1 (2024-10-28)

- fix: accounts without 2fa are supported [#959](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/959)

## 1.24.0 (2024-10-25)

- fix: new AppleID auth with srp [#970](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/970)
- feature: when ran without parameters, `icloudpd` shows help [#963](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/963)
- fix: force_size should not skip subsequent sizes [#955](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/955)

## 1.23.4 (2024-09-02)

- fix: support plain text encoding for filename in addition to base64 [ref](https://github.com/boredazfcuk/docker-icloudpd/issues/641)

## 1.23.3 (2024-09-01)

- more debug added for parsing filenameEnc [#935](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/935) and [ref](https://github.com/boredazfcuk/docker-icloudpd/issues/641)

## 1.23.2 (2024-08-31)

- dump encoded filename in exception when there is an error in decoding it [#935](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/935) and [ref](https://github.com/boredazfcuk/docker-icloudpd/issues/641)

## 1.23.1 (2024-08-22)

- fix: use a-z for sms mfa index to disambiguate with mfa code with leading zeros [#925](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/925)
- fix: report proper error on bad `--folder-structure` value [#937](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/937)

## 1.23.0 (2024-07-25)

- feature: update webui and allow to cancel and resume sync 
- deprecate linux 386 and arm v6 support
- add linux musl builds

## 1.22.0 (2024-07-12)

- feature: support for using locale from OS with `--use-os-locale` flag [#897](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/897)
- fix: swallow keyring errors [#871](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/871)

## 1.21.0 (2024-07-05)

- feature: add webui for entering password with `--password-provider webui` parameter [#805](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/805)
- feature: add webui for entering MFA code with `--mfa-provider webui` parameter [#805](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/805)
- fix: allow MFA with leading zeros [ref](https://github.com/boredazfcuk/docker-icloudpd/issues/599)

## 1.20.4 (2024-06-30)

- fix: SMS MFA [#803](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/803)

## 1.20.3 (2024-06-29)

- fix: release to PyPi [#883](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/883)

## 1.20.2 (2024-06-28)

- fix: match SMS MFA to icloud.com behavior [#803](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/803)

## 1.20.1 (2024-06-18)

- fix: keyring handling in `icloud` [#871](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/871)

## 1.20.0 (2024-06-16)

- feature: customize choice and the order of checking for password with `--password-provider` parameter
- feature: support multiple file naming and de-deplication policies with `--file-match-policy` parameter. Rel to [#346](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/346)

## 1.19.1 (2024-06-02)

- fix: KeyError alternative [#859](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/859)

## 1.19.0 (2024-05-31)

- fix: release notes [#849](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/849)
- fix: auto deletion when `--folder-structure` is set to `none` [#831](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/831)
- fix: Apple/Adobe DNG raw photos are recognised as images [#662](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/662)
- feature: support multiple `--size` parameter specifications in command line
- fix: file extensions for non-original version matching type of the asset in the version
- feature: support downloading adjusted files with `--size adjusted` parameter (portraits, edits, etc) with fallback to `original` [#769](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/769) [#704](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/704) [#350](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/350) [#249](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/249)
- feature: support for CR2,CR3,CRW,ARW,RAF,RW2,NRF,PEF,NEF,ORF raw image formats [#675](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/675)
- feature: support `--size alternative` for alternative originals, e.g. raw+jpeg, with fallback to `original` [#675](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/675)
- feature: add `--align-raw` param to treat raw in raw+jpeg as original, alternative (jpeg+raw), or as-is, default to as-is

## 1.18.0 (2024-05-27)

- feature: add parameter `--live-photo-mov-filename-policy` to control naming of video portion of live photos with default `suffix` for compatibility [#500](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/500)
- feature: add parameter `--keep-unicode-in-filenames` with default `false` for compatibility [#845](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/845)
- fix: avoid parsing json from empty responses [#837](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/837)

## 1.17.7 (2024-05-25)

- fix: keyring exception [#841](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/841)
- fix: delete iCloud asset in respective shared library [#802](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/802)

## 1.17.6 (2024-05-23)

- fix: missing exception [#836](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/836)

## 1.17.5 (2024-04-27)

- experimental: fix errors in npm packages
- fix: allow calls for trusted devices to fail silently [#819](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/819)

## 1.17.4 (2024-04-10)

- fix: restore support for SMS MFA [#803](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/803)

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
