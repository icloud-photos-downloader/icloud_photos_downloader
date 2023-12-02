# iCloud Photos Downloader [![Quality Checks](https://github.com/icloud-photos-downloader/icloud_photos_downloader/workflows/Quality%20Checks/badge.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/actions/workflows/quality-checks.yml) [![Multi Platform Docker Build](https://github.com/icloud-photos-downloader/icloud_photos_downloader/workflows/Docker%20Build/badge.svg)](https://github.com/icloud-photos-downloader/icloud_photos_downloader/actions/workflows/docker-build.yml) [![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE.md)

A command-line tool to download all your iCloud photos.

## Install, Run, and Use

``` sh
docker run -it --rm --name icloudpd -v $(pwd)/Photos:/data -e TZ=America/Los_Angeles icloudpd/icloudpd:latest icloudpd --directory /data --username my@email.address --watch-with-interval 3600
```

Image asset date will be convered to specified TZ and then used for creating folders (see `--folder-stucture` param)

On Windows:

- use `%cd%` instead of `$(pwd)`
- or full path, e.g. `-v c:/photos/icloud:/data`
- only Linux containers are supported

Synchronization logic can be adjusted with command-line parameters. Run the following to get full list:
``` sh 
docker run -it --rm icloudpd/icloudpd:latest icloudpd --help
``` 

## Getting Docker

On Windows and Mac Docker is available as [Docker Desktop](https://www.docker.com/products/docker-desktop/) app.

On Linux, Docker engine and client can be installed using platform package managers, e.g. [Installing on Ubuntu](https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-20-04)

Appliance (e.g. NAS) will have their own way to install Docker engines and running containers - see manufacturer's instructions.

## More

See [Project page](https://github.com/icloud-photos-downloader/icloud_photos_downloader/) for more details.
