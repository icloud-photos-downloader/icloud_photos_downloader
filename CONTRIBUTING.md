# Contributing iCloud Photos Downloader

[//]: # (inspired from https://raw.githubusercontent.com/keepassxreboot/keepassxc/develop/.github/CONTRIBUTING.md)

:+1::tada: First off, thanks for taking the time to contribute! :tada::+1:

We'd love your contributions to iCloud Photos Downloader. You don't have to know how to code to be able to help!

Please review the following guidelines before contributing.  Also, feel free to propose changes to these guidelines by updating this file and submitting a pull request.

## Table of contents

[How can I contribute?](#how-can-i-contribute)

* [Feature requests](#feature-requests)
* [Bug reports](#bug-reports)
* [Discuss with the team](#discuss-with-the-team)
* [Your first code contribution](#your-first-code-contribution)
* [Pull request process](#pull-request-process)

[Setting up the development environment](#setting_up_the_development_environment)

Please note we have a [Code of Conduct](CODE_OF_CONDUCT.md), please follow it in all your interactions with the project.

## How can I contribute?

There are several ways to help this project. Let us know about missing features, or report errors. You could even help others by responding to questions about using the project in the [issue tracker on GitHub][issues-section].

### Feature requests

We're always looking for suggestions to improve our application. If you have a suggestion to improve an existing feature, or would like to suggest a completely new feature, please use the [issue tracker on GitHub][issues-section].

### Bug reports

Our software isn't always perfect, but we strive to always improve our work. You may file bug reports in the issue tracker.

Before submitting a bug report, check if the problem has already been reported. Please refrain from opening a duplicate issue. If you want to add further information to an existing issue, simply add a comment on that issue.

### Discuss with the team

When contributing to this repository, please first discuss the change you wish to make via issue,
email, or any other method with the owners of this repository before making a change.

### Your first code contribution

Unsure where to begin contributing to this project? You can start by looking through these `good first issue` and `help-wanted` issues:

* [Good first issues](good+first+issue) – issues which should only require a few lines of code, and a test or two.
* ['Help wanted' issues](help-wanted) – issues which should be a bit more involved than `beginner` issues.

Both issue lists are sorted by total number of comments. While not perfect, looking at the number of comments on an issue can give a general idea of how much an impact a given change will have.

### Pull Request Process

There are some requirements for pull requests:

* All bugfixes should be covered (before/after scenario) with a corresponding
  unit test, refer to [How to write a unit test](#how-to-write-a-unit-test) All other tests pass. Run `./scripts/test`
* 100% test coverage also for new features is expected.
  * After running `./scripts/test`, you will see the test coverage results in the output
  * You can also open the HTML report at: `./htmlcov/index.html`
* Code is formatted with [autopep8](https://github.com/hhatto/autopep8). Run `./scripts/format`
* No [pylint](https://www.pylint.org/) errors. Run `./scripts/lint` (or `pylint icloudpd`)
* If you've added or changed any command-line options,
  please update the [Usage](README.md#usage) section in the README.md.
* Make sure your change is documented in the
[Unreleased](CHANGELOG.md#unreleased) section in the CHANGELOG.md.
* We aim to push out a Release once a week (Fridays),  if there is at least one new change in CHANGELOG.

If you need to make any changes to the `pyicloud` library,
`icloudpd` uses a fork of this library that has been renamed to `pyicloud-ipd`.
Please clone my [pyicloud fork](https://github.com/icloud-photos-downloader/pyicloud)
and check out the [pyicloud-ipd](https://github.com/icloud-photos-downloader/pyicloud/tree/pyicloud-ipd)
branch. PRs should be based on the `pyicloud-ipd` branch and submitted to
[icloud-photos-downloader/pyicloud](https://github.com/icloud-photos-downloader/pyicloud).

## Setting up the development environment

Install dependencies:

``` sh
sudo pip install -r requirements.txt
sudo pip install -r requirements-test.txt
```

Run tests:

``` sh
pytest
```

### Building the Docker image

``` none
git clone https://github.com/icloud-photos-downloader/icloud_photos_downloader.git
cd icloud_photos_downloader
docker build -t icloudpd/icloudpd .
```

## How to write a unit test

The unit tests are a very important asset of this project. Due to our 100% test coverage we can savely use great tools like [Dependabot](dependabot.com) and be sure that the implementation of a new feature or fixing of a bug does not lead to further issues.

We're relying on [pytest](pytest.org) for the creation of our tests and [VCR.py](https://github.com/kevin1024/vcrpy) for automatic mocking of the communication to iCloud. This makes the creation of testcases rather simple as you don't have to deal with the communication to iCloud itself and can just focus on the "real test". Both tools maintain great howtos that can be found here:

* pytest documentation: https://docs.pytest.org/en/stable/
* VCR.py documentation: https://vcrpy.readthedocs.io/en/latest/

It is highly recommented to have a look at those.

The process is mostly like this (assuming we're talking about a bug fix here...)

1. Is there already a related testcase existing? If so you can just check if an existing test needs to check for another situation.
1. If not, then you need to make sure you have correspnding test-data at hand; that means: your iCloud photos library should have a constellation that leads to the error in `icloudpd`.
1. Add a test-function that runs `icloudpd` with the necessary start parameters, referencing to a new cassette file.
1. **VERY IMPORTANT:** the real iCloud response is cached, so every image is saved in the cassette. That means:
   1. Don't use private photos!
   1. keep the dataset small (p.e. using `--recent`)
   1. Remove your personal information from the cached REST-response (Name, email adresses)
1. Go back to the previous step and verify again that you followed the recommendations!
1. Now you can start adding tests.

Refer to the existing tests for inspiration. A very simple test to to understand the basic idea might be the test for the listing of albums option in `tests/test_listing_albums.py`.

When testing a bugfix it is important to test the faulty behavior and also the expected behavior.
