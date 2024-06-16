# Install and Run

There are three ways to run `icloudpd`:
1. Download executable for your platform from the Github [Releases](https://github.com/icloud-photos-downloader/icloud_photos_downloader/releases) and run it
1. Use package manager to install, update, and, in some cases, run ([Docker](#docker), [PyPI](#pypi), [AUR](#aur), [Npm](#npm))
1. Build and run from the source

## Docker

```sh
docker run -it --rm --name icloudpd -v $(pwd)/Photos:/data -e TZ=America/Los_Angeles icloudpd/icloudpd:latest icloudpd --directory /data --username my@email.address --watch-with-interval 3600
```

Image asset date will be convered to specified TZ and then used for creating folders (see `--folder-stucture` param)

Synchronization logic can be adjusted with command-line parameters. Run the following to get full list:
``` sh 
docker run -it --rm icloudpd/icloudpd:latest icloudpd --help
``` 

```{note}
On Windows:

- use `%cd%` instead of `$(pwd)`
- or full path, e.g. `-v c:/photos/icloud:/data`
- only Linux containers are supported
```

```{note} 

Getting Docker:

- On Windows and Mac Docker is available as [Docker Desktop](https://www.docker.com/products/docker-desktop/) app.

- On Linux, Docker engine and client can be installed using platform package managers, e.g. [Installing on Ubuntu](https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-20-04)

- Appliance (e.g. NAS) will have their own way to install Docker engines and running containers - see manufacturer's instructions.
```

## PyPI

TBD

## AUR

TBD

## NPM

TBD
