from setuptools import setup, find_packages

with open("requirements.txt") as f:
    required = f.read().splitlines()

# read the contents of your README file
from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="icloudpd",
    version="1.12.0",
    url="https://github.com/icloud-photos-downloader/icloud_photos_downloader",
    description=(
        "icloudpd is a command-line tool to download photos and videos from iCloud."
    ),
    maintainer="The iCloud Authors",
    maintainer_email=" ",
    license="MIT",
    packages=find_packages(),
    install_requires=required,
    python_requires=">=3.7,<3.12",
    classifiers=[
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
    entry_points={"console_scripts": ["icloudpd = icloudpd.base:main", "icloud = pyicloud.cmdline:main"]},
    long_description=long_description,
    long_description_content_type='text/markdown'
)
