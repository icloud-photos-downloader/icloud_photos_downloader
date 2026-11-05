# Install and Run

There are three ways to run `icloudpd`:
1. Download the executable for your platform from the GitHub [Release](https://github.com/icloud-photos-downloader/icloud_photos_downloader/releases/tag/v1.33.0) (see [Which file do I download?](which-file)) and run it, e.g.:

    ```sh
    ./icloudpd-1.33.0-linux-amd64 --username your@email.address --directory photos --watch-with-interval 3600
    ```

1. Use a package manager to install, update, and, in some cases, run ([Docker](#docker), [PyPI](#pypi), [AUR](#aur), [npm](#npm))
1. Build and run from source

## iCloud Prerequisites

Check these settings on your iPhone or iPad first, otherwise Apple's servers return an `ACCESS_DENIED` error:

- **Access iCloud Data on the Web:** enable `Settings > [your name] > iCloud > Access iCloud Data on the Web`
- **Advanced Data Protection (ADP):** either disable `Settings > [your name] > iCloud > Advanced Data Protection`, or keep it enabled and run with [`--adp-web-access`](adp-web-access-parameter) (see [Authentication](authentication))

(which-file)=
## Which file do I download?

Each [release](https://github.com/icloud-photos-downloader/icloud_photos_downloader/releases) has many files. Pick the one for your system:

| System | File |
|--------|------|
| Windows, 64-bit Intel/AMD | `icloudpd-<version>-windows-amd64.exe` |
| macOS, Apple Silicon (M1 and later) | `icloudpd-<version>-macos-arm64` |
| macOS, Intel | `icloudpd-<version>-macos-amd64` |
| Linux (glibc: Debian, Ubuntu, Fedora, ...), 64-bit Intel/AMD | `icloudpd-<version>-linux-amd64` |
| Linux (glibc), 64-bit ARM | `icloudpd-<version>-linux-arm64` |
| Linux (glibc), 32-bit ARM (armv7) | `icloudpd-<version>-linux-arm32v7` |
| Linux (musl: Alpine 3.20 and newer) | `icloudpd-<version>-linux-musl-<arch>`, same `<arch>` values as above |

There is no Windows build for ARM.

Ignore the other files unless you know you need them:

- `icloud-<version>-...` is a different, small tool (`icloud`) for Find My devices and for managing the password in the system keyring (see [Authentication](authentication)). It does not download photos.
- `*.whl` are Python packages; install them with [pip or pipx](#pypi) instead.
- `icloudpd-<version>-oci.tar` is the Docker image as a file; use [Docker](#docker) instead.
- `*.md` files are release notes and test results.

If you are not sure whether your Linux uses glibc or musl, use the glibc file; only Alpine and a few small distributions use musl. See [Linux binaries](linux-binaries) for details.

(windows-binary)=
## Windows binary

`icloudpd` is a command-line program. Double-clicking the `.exe` only prints the help text, and the window closes right away. Open a terminal (Command Prompt or PowerShell) in the folder with the file and run it from there:

```powershell
.\icloudpd-1.33.0-windows-amd64.exe --username your@email.address --directory C:\photos\icloud
```

(linux-binaries)=
## Linux binaries

Linux binaries are available for amd64, arm64 and arm32v7, in two variants:

- `icloudpd-<version>-linux-<arch>` for distributions based on glibc, e.g. Debian, Ubuntu, Fedora
- `icloudpd-<version>-linux-musl-<arch>` for distributions based on musl, e.g. Alpine

The musl variant needs musl 1.2.5 or newer, which is Alpine 3.20 and newer. On older Alpine releases it fails to start (`Error relocating ...` or a segmentation fault). The same applies to the musl wheels on PyPI (`musllinux`), which contain the same binary.

Make the downloaded file executable and start it with `./` from the folder it is in:

```sh
chmod +x icloudpd-1.33.0-linux-amd64
./icloudpd-1.33.0-linux-amd64 --username your@email.address --directory photos
```

## macOS binary

`icloudpd` is available as a binary for Apple Silicon Macs (`icloudpd-<version>-macos-arm64`) and for Intel Macs (`icloudpd-<version>-macos-amd64`). The Intel binary is built for as long as GitHub provides Intel macOS build machines; on Intel Macs after that, use [Docker](#docker) or [PyPI](#pypi).

```{note}
In 1.32.3, `icloudpd-1.32.3-macos-amd64` was built for Apple Silicon by mistake and does not run on Intel Macs (`bad CPU type in executable`). Use 1.32.2 or 1.33.0 and later on Intel Macs.
```

Here are the steps to make it work (the examples use the Apple Silicon binary):
- Download the binary from GitHub [Releases](https://github.com/icloud-photos-downloader/icloud_photos_downloader/releases) into the desired local folder
- Add the executable flag by running `chmod +x icloudpd-1.33.0-macos-arm64`
- Start it from the terminal: `./icloudpd-1.33.0-macos-arm64`
- Apple will tell you that it cannot check for malicious software and refuse to run the app; click "OK"
- Open "System Settings"/"Privacy & Security" and find `icloudpd-1.33.0-macos-arm64` as a blocked app; click "Allow"
- Start `./icloudpd-1.33.0-macos-arm64` from the terminal again
- Apple will show another warning; click "Open"
- After that, you can run `./icloudpd-1.33.0-macos-arm64 --help` or any other supported command/option

Instead of the "Privacy & Security" steps, you can remove the download quarantine flag in the terminal:

```sh
xattr -d com.apple.quarantine icloudpd-1.33.0-macos-arm64
```

(docker)=
## Docker

```sh
docker run -it --rm --name icloudpd \
  -v $(pwd)/Photos:/data \
  -v $(pwd)/icloudpd-config:/config \
  -e TZ=America/Los_Angeles \
  icloudpd/icloudpd:latest \
  icloudpd --directory /data --cookie-directory /config --username my@email.address --watch-with-interval 3600
```

- `-v ...:/config` with [`--cookie-directory /config`](cookie-directory-parameter) keeps the session on the host. Without it, the session is stored in `/root/.pyicloud` inside the container and is lost every time the container is recreated (e.g. after an image update), so you have to do 2FA again.
- `-it` is needed to type the password and 2FA code in the console. Without a terminal, use the [web UI](webui) instead.
- The image asset date is converted to the specified `TZ` and then used for creating folders (see the [`--folder-structure`](folder-structure-parameter) parameter).
- Files are written as `root`, so on Linux hosts the downloaded files and the session folder are owned by `root`.

To use the [web UI](webui) (`--password-provider webui` and/or `--mfa-provider webui`), publish its port, e.g. `-p 8080:8080`; the web UI then is at `http://localhost:8080`. It has no login, so do not expose the port to the internet.

To update, pull the new image and recreate the container:

```sh
docker pull icloudpd/icloudpd:latest
```

The synchronization logic can be adjusted with command-line parameters. Run the following to get the full list:
``` sh 
docker run -it --rm icloudpd/icloudpd:latest icloudpd --help
``` 

```{note}
On Windows:

- use `%cd%` instead of `$(pwd)` in Command Prompt, and `${PWD}` in PowerShell
- or a full path, e.g. `-v c:/photos/icloud:/data`
- only Linux containers are supported
- the `\` line continuations above are for Linux/macOS shells; put the command on one line on Windows
```

```{note} 

Getting Docker:

- On Windows and Mac Docker is available as [Docker Desktop](https://www.docker.com/products/docker-desktop/) app.

- On Linux, see the [Docker Engine install guide](https://docs.docker.com/engine/install/) for your distribution.

- Appliances (e.g., NAS) will have their own way to install Docker engines and run containers - see the manufacturer's instructions and [NAS](nas).
```

(pypi)=
## PyPI

[pipx](https://pipx.pypa.io/) installs `icloudpd` in its own environment and is the recommended way:

``` sh
pipx install icloudpd
```

Update:

``` sh
pipx upgrade icloudpd
```

Run:

``` sh
icloudpd --directory /data --username my@email.address --watch-with-interval 3600
```

You can also use pip (`pip install icloudpd`, update with `pip install --upgrade icloudpd`), preferably inside a virtual environment. On Debian 12+, Ubuntu 23.04+ and other distributions that mark the system Python as externally managed (PEP 668), `pip install` outside a virtual environment fails with `externally-managed-environment`; use pipx or a virtual environment.

````{note}

on Windows with pip:

``` sh
pip install icloudpd --user
```

Also add `C:\Users\<YourUserAccountHere>\AppData\Roaming\Python\Python<YourPythonVersionHere>\Scripts` to PATH. The exact path will be given at the end of the `icloudpd` installation.
````

```{note}

on MacOS with pip:

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

## Supported platforms

- **Python:** 3.11 to 3.15 (for PyPI installs; the binaries and the Docker image include their own Python).
- **Operating systems:** Linux (amd64, arm64, arm32v7), macOS (Apple Silicon and Intel) and Windows (amd64).
- **Linux distributions:** each release is tested on the Debian, Ubuntu and Alpine releases that still get free security updates, plus those whose support ended less than a year ago (currently Debian 11 (binary only), 12 and 13, Ubuntu 22.04, 24.04 and 26.04, Alpine 3.20 to 3.24). The `compatibility-<version>.md` file of each [release](https://github.com/icloud-photos-downloader/icloud_photos_downloader/releases) has the full results. `icloudpd` may work on older releases, but they are not tested.

## Error on the First Run

When you run the script for the first time, you might see an error message like this:

``` 
Bad Request (400)
```

This error often happens because your account hasn't used the iCloud API before, so Apple's servers need to prepare some information about your photos. This process can take around 5-10 minutes, so please wait a few minutes and try again.

If you are still seeing this message after 30 minutes, then please [open an issue on GitHub](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/new) and post the script output.
