# Experimental Mode

Goal is to try new things and get feedback from users without breaking existing behavior.

Anything in this section can change without backward compatibity or even completely removed.

DANGER ZONE: Code may not work as expected.

## CLI format

Goal: reduce user confusion and maintanence burden by restructuring CLI interface for better matching use cases and related options

### New Structure

Ideas:
- Each use case is matched to command
- Customizations are available as options

Use Cases:
- Maintain local copy/backup of iCloud: **COPY** command
- Use iCloud as a transfer meduim to local storage (and clean iCloud afterwards): **MOVE** command

Othrogonal Needs:
- Scheduled sync: **WATCH** command
- management of persistent credentials: **AUTH** command
- monitoring/notification/alerting: TBD


### How to Use

Legacy command (compatible with prior versions):

`docker run -it --rm icloudpd:icloudpd icloudpd --help`

`docker run -it --rm icloudpd:icloudpd icloud --help`

`icloudpd-1.17.3-windows-amd64 --help`

Help:

`docker run -it --rm icloudpd:icloudpd`

`icloudpd-ex-1.17.3-windows-amd64 --help`

Example:

`docker run -it --rm icloudpd:icloudpd copy my@email.address /path/to/{album}/{date_created:%Y/%Y-%m}`

`icloudpd-ex-1.17.3-windows-amd64 copy my@email.address /path/to/{album}/{date_created:%Y/%Y-%m}`

