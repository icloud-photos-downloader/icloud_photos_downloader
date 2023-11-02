.github/workflows￼Enter
README_PYPI.md
Skip to content

Code
Issues
82
More
Breadcrumbsicloud_photos_downloader
/README_PYPI.md
Latest commit
AndreyNikiforov
AndreyNikiforov
4 months ago
History
78 lines (49 loc) · 2.28 KB
File metadata and controls

Preview

Code

Blame
iCloud Photos Downloader Quality Checks Multi Platform Docker Build MIT License
A command-line tool to download all your iCloud photos.

Install
pip install icloudpd
Windows
pip install icloudpd --user
Plus add C:\Users\<YourUserAccountHere>\AppData\Roaming\Python\Python<YourPythonVersionHere>\Scripts to PATH. The exact path will be given at the end of icloudpd installation.

MacOS
Add /Users/<YourUserAccountHere>/Library/Python/<YourPythonVersionHere>/bin to PATH. The exact path will be given at the end of icloudpd installation.

Usage
icloudpd --directory /data --username my@email.address --watch-with-interval 3600
Synchronization logic can be adjusted with command-line parameters. Run the following to get full list:

icloudpd --help
Getting Python & Pip
You can get Python with accompanying Pip from Official site.

Alternatives for Mac
Command Line Tools from Apple
Apple provices Python & Pip as part of the Command Line Tools for XCode. They can be downloaded from Apple Developer portal or installed with

xcode-select --install
Use pip3 to install icloudpd:

pip3 install icloudpd
Homebrew package manager
Homebrew is open source package manager for MacOS. Install Homebrew (if not already installed):

which brew > /dev/null 2>&1 || /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
Install Python (includes pip):

brew install python
Alternative for Linux (Ubuntu)
sudo apt-get update
sudo apt-get install -y python
More
See Project page for more details.

icloud_photos_downloader/README_PYPI.md at master · icloud-photos-downloader/icloud_photos_downloader
