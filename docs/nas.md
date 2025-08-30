# Network Attached Storage

The following are example setups for NAS.

## TrueNAS

Use the [`Install Custom App` button](https://www.truenas.com/docs/scale/23.10/scaletutorials/apps/usingcustomapp/) to set up `icloudpd`:
| Field | Value | Note |
|-------|-------|------|
Application Name | `icloudpd` |
Version | N/A | Leave default
Container Images/Image repository | `icloudpd/icloudpd` |
Container Images/Image tag | `latest` |
Container Entrypoint/Container Args | `icloudpd` `-u` `your@email.address` `-d` `/data` `--password-provider` `webui` `--mfa-provider` `webui` `--watch-with-interval` `3600` | each as a separate arg (param name and param value become two separate args)
Port Forwarding/Container Port | `8080` |
Port Forwarding/Node Port | `9090` | or other available port on your host
Storage/Host Path Volumes/Host Path | /mnt/my_pool/photos | or another location on your host
Storage/Host Path Volumes/Mount Path | /data | 
Portal Configuration/Enable Portal Configuration | checked | 
Portal Configuration/Portal Name | `icloudpd` | 
Portal Configuration/Protocol to Portal | `HTTP Protocol` | 
Portal Configuration/Use Node IP for Portal IP/Domain | checked | 
Portal Configuration/Port | `9090` | Same as "Port Forwarding/Host Port" above

Once the app has started, connect to the [WebUI](webui) to enter the password and MFA code in one of two ways:
- Using a browser from your PC to port 9090 of your NAS
- Clicking on the `icloudpd` button in the Detail/Application Info section of the TrueNAS portal

## Running on Synology NAS

The error `Failed to execv() /tmp/staticx-kJmNbp` has a workaround by running `sudo mount /tmp -o remount,exec` (from an SSH terminal). [#788](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/788)

CPU/Arch [used by Synology](https://kb.synology.com/en-me/DSM/tutorial/What_kind_of_CPU_does_my_NAS_have) other than amd64 (from x12 onwards):
| Models | CPU | Arch | 
|-------|-------|------|
DS124, DS423, DS223j, DS223 | Realtek RTD1619B | arm64 | 
DS220j, RS819, DS418, DS218, DS218play, DS118 | Realtek RTD1296 | arm64 | 
DS418j | Realtek RTD1293 | arm64 | 
DS120j, DS119j | Marvell A3720 | arm64 | 
DS419slim, DS218j, RS217, RS816, DS416slim, DS216, DS216j, DS116 | Marvell Armada 385 88F6820 | arm32v7 | 
DS1817, DS1517 | Annapurna Labs Alpine AL-314 | arm32v7 | 
DS416 | Annapurna Labs Alpine AL-212 | arm32v7 | 
DS416j | Marvell Armada 388 88F6828 | arm32v7 | 
DS216play | STM STiH412 | arm32v7 | 
DS216se | Marvell Armada 370 88F6707 | arm32v7 | 
RS815, RS814, DS414, DS214, DS214+ | Marvell Armada XP MV78230 | arm32v7 | 
DS2015xs | Annapurna Labs Alpine AL-514 | arm32v7 | 
DS1515 | Annapurna Labs Alpine AL-314 | arm32v7 | 
DS215+ | Annapurna Labs Alpine AL-212 | arm32v7 | 
DS215j, D115j, D115 | Marvell Armada 370 88F6720 | arm32v7 | 
DS214, DS414slim, DS214se, DS114, DS213j | Marvell Armada 370 88F6707 | arm32v7 | 
DS414j | Mindspeed Comcerto C200 | arm32v7
DS413, DS213+ | Freescale P1022 | power (Unsupported) | 
DS413j, DS213, DS213air | Marvell Kirkwood 88F6282 | arm32v5 (Unsupported) | 

Non-x86 64-bit models from x12 and earlier are not supported.

[Additional info on Marvell](https://www.kernel.org/doc/html/v6.1/arm/marvell.html)
