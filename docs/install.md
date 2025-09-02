# Install and Run

There are three ways to run `icloudpd`:
1. Download executable for your platform from the GitHub [Release](https://github.com/icloud-photos-downloader/icloud_photos_downloader/releases/tag/v1.32.2) and run it, e.g.:

    ```sh
    icloudpd --username your@email.address --directory photos --watch-with-interval 3600
    ```

1. Use a package manager to install, update, and, in some cases, run ([Docker](#docker), [PyPI](#pypi), [AUR](#aur), [npm](#npm))
1. Build and run from source

(docker)=
## Docker

```sh
docker run -it --rm --name icloudpd -v $(pwd)/Photos:/data -e TZ=America/Los_Angeles icloudpd/icloudpd:latest icloudpd --directory /data --username my@email.address --watch-with-interval 3600
```

The image asset date will be converted to the specified TZ and then used for creating folders (see the [`--folder-structure`](folder-structure-parameter) parameter).

The synchronization logic can be adjusted with command-line parameters. Run the following to get the full list:
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

- Appliances (e.g., NAS) will have their own way to install Docker engines and run containers - see the manufacturer's instructions.
```

(pypi)=
## PyPI

Install:
``` sh
pip install icloudpd
```

Run:

``` sh
icloudpd --directory /data --username my@email.address --watch-with-interval 3600
```

````{note}

on Windows:

``` sh
pip install icloudpd --user
```

Also add `C:\Users\<YourUserAccountHere>\AppData\Roaming\Python\Python<YourPythonVersionHere>\Scripts` to PATH. The exact path will be given at the end of the `icloudpd` installation.
````

```{note}

on MacOS:

Add `/Users/<YourUserAccountHere>/Library/Python/<YourPythonVersionHere>/bin` to PATH. The exact path will be given at the end of `icloudpd` installation.
```

(aur)=
## AUR

AUR packages can be installed on Arch Linux. Installation can be done [manually](https://wiki.archlinux.org/title/Arch_User_Repository#Installing_and_upgrading_packages) or with the use of an [AUR helper](https://wiki.archlinux.org/title/AUR_helpers).

The manual process would look like this:

``` sh
git clone https://aur.archlinux.org/icloudpd-bin.git
cd icloudpd-bin
makepkg -sirc
```

With the use of an AUR helper, e.g., [yay](https://github.com/Jguer/yay), the installation process would look like this:

``` sh
yay -S icloudpd-bin
```

(npm)=
## npm

``` sh
npx --yes icloudpd --directory /data --username my@email.address --watch-with-interval 3600
```

## macOS binary

`icloudpd` is available as an Intel 64-bit binary for macOS, but works on ARM Macs too (M1, M2, M3).

Here are the steps to make it work:
- Download the binary from GitHub [Releases](https://github.com/icloud-photos-downloader/icloud_photos_downloader/releases) into the desired local folder
- Add the executable flag by running `chmod +x icloudpd-1.32.2-macos-amd64`
- Start it from the terminal: `icloudpd-1.32.2-macos-amd64`
- Apple will tell you that it cannot check for malicious software and refuse to run the app; click "OK"
- Open "System Settings"/"Privacy & Security" and find `icloudpd-1.32.2-macos-amd64` as a blocked app; click "Allow"
- Start `icloudpd-1.32.2-macos-amd64` from the terminal again
- Apple will show another warning; click "Open"
- After that, you can run `icloudpd-1.32.2-macos-amd64 --help` or any other supported command/option

## Error on the First Run

When you run the script for the first time, you might see an error message like this:

``` 
Bad Request (400)
```

This error often happens because your account hasn't used the iCloud API before, so Apple's servers need to prepare some information about your photos. This process can take around 5-10 minutes, so please wait a few minutes and try again.

If you are still seeing this message after 30 minutes, then please [open an issue on GitHub](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/new) and post the script output.
