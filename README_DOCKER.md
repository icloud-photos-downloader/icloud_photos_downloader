# iCloud Photos Downloader [![Quality Checks](https://github.com/icloud-photos-downloader/icloud_photos_downloader/workflows/Quality%20Checks/badge.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/actions/workflows/quality-checks.yml) [![Build and Package](https://github.com/icloud-photos-downloader/icloud_photos_downloader/workflows/Produce%20Artifacts/badge.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/actions/workflows/produce-artifacts.yml) [![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/blob/master/LICENSE.md)

A command-line tool to download all your iCloud photos.

## Install, Run, and Use

``` sh
docker run -it --rm --name icloudpd -v $(pwd)/Photos:/data -v $(pwd)/icloudpd-config:/config -e TZ=America/Los_Angeles icloudpd/icloudpd:latest icloudpd --directory /data --cookie-directory /config --username my@email.address --watch-with-interval 3600
```

- `-v ...:/config` with `--cookie-directory /config` keeps the session on the host. Without it, the session is stored in `/root/.pyicloud` inside the container and is lost every time the container is recreated (e.g. after an image update), so you have to do 2FA again.
- `-it` is needed to type the password and 2FA code in the console. Without a terminal, use the [web UI](https://icloud-photos-downloader.github.io/icloud_photos_downloader/webui.html) (`--password-provider webui --mfa-provider webui`) and publish its port with `-p 8080:8080`. The web UI has no login, so do not expose the port to the internet.
- Image asset date will be converted to specified TZ and then used for creating folders (see `--folder-structure` parameter)
- Files are written as `root`, so on Linux hosts the downloaded files and the session folder are owned by `root`.

On Windows:

- use `%cd%` instead of `$(pwd)` in Command Prompt, and `${PWD}` in PowerShell
- or full path, e.g. `-v c:/photos/icloud:/data`
- only Linux containers are supported

To update, run `docker pull icloudpd/icloudpd:latest` and recreate the container.

Synchronization logic can be adjusted with command-line parameters. Run the following to get full list:
``` sh 
docker run -it --rm icloudpd/icloudpd:latest icloudpd --help
``` 

## Getting Docker

On Windows and Mac Docker is available as [Docker Desktop](https://www.docker.com/products/docker-desktop/) app.

On Linux, see the [Docker Engine install guide](https://docs.docker.com/engine/install/) for your distribution.

Appliance (e.g. NAS) will have their own way to install Docker engines and running containers - see manufacturer's instructions.

## More

See [Project page](https://github.com/icloud-photos-downloader/icloud_photos_downloader/) for more details.
