# Experimental Mode

Substential, uncertain, big, uncomplete, or otherwise not immidiately considered safe and available to everybody, are tagged as experiemental.

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

`icloudpd-1.11.0-windows-amd64 --help`

Help:

`docker run -it --rm icloudpd:icloudpd`

`icloudpd-ex-1.11.0-windows-amd64 --help`

Example:

`docker run -it --rm icloudpd:icloudpd copy my@email.address /path/to/{album}/{date_created:%Y/%Y-%m}`

`icloudpd-ex-1.11.0-windows-amd64 copy my@email.address /path/to/{album}/{date_created:%Y/%Y-%m}`

## MacOS binary

Experiemental binary is available as MacOS binary. It is available as Intel 64bit binary, but works on M1 macs too.

Here are the steps to make it working:
- download into desired folder
- add executable flag by running `chmod +x icloudpd-ex-1.11.0-macos-amd64`
- start it from the terminal: `icloudpd-ex-1.11.0-macos-amd64`
- Apple will tell you that it cannot check for malicous software and refuse to run the app; click "Ok"
- Open "System Settings"/"Privacy & Security" and find `icloudpd-ex-1.11.0-macos-amd64` as blocked app; Click "Allow"
- Start `icloudpd-ex-1.11.0-macos-amd64` from the terminal again
- Apple will show another warning; click "Open"
- After that you can run `icloudpd-ex-1.11.0-macos-amd64 icloudpd --username my@email.address --list-albums` or any other supported command/option
