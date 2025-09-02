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

[Setting up the development environment](#setting-up-the-development-environment)

[How to write a unit test](#how-to-write-a-unit-test)

Please note we have a [Code of Conduct](CODE_OF_CONDUCT.md), please follow it in all your interactions with the project.

Chore:
- [How to release](#how-to-release)


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

## Pull Request Process

There are some requirements for pull requests:

* All bug fixes should be covered (before/after scenario) with a corresponding
  unit test, refer to [How to write a unit test](#how-to-write-a-unit-test) All other tests pass. Run `./scripts/test`
* 100% test coverage also for new features is expected.
  * After running `./scripts/test`, you will see the test coverage results in the output
  * You can also open the HTML report at: `./htmlcov/index.html`
* Code is formatted with [ruff](https://github.com/astral-sh/ruff). Run `./scripts/format`
* No lint errors. Run `./scripts/lint`
* If you've added or changed any command-line options,
  please update the [Usage](README.md#usage) section in the README.md.
* Make sure your change is documented in the
[Unreleased](CHANGELOG.md#unreleased) section in the CHANGELOG.md.
* We aim to push out a Release once a week (Fridays), if there is at least one new change in CHANGELOG.

If you need to make any changes to the `pyicloud` library,
`icloudpd` uses a fork of this library that has been added as a subfolder `pyicloud_ipd`.

## Setting up the development environment

### Dev Containers

Easy way to isolate development from the rest of host system is by using Docker containers (devcontainers). VS Code & GitHub Codespaces support this workflow and repository is configured for their use.

VS Code supports local devcontainers (running on the same host as VS Code; require Docker on the host, obviously) as well as remote ones.

### Install Python dependencies

``` sh
scripts/install_deps
```

Installs project for editing mode (install all dev and test dependencies too). You can use `icloudpd` script from terminal as well.

### Formatting Python code

``` sh
scripts/format
```

### Validating app behavior

Run lint & tests:

``` sh
scripts/lint
```

``` sh
scripts/test
```

### Building packages

Building Python wheel (with python source files):

``` sh
scripts/build
```

Building platform executables:

``` sh
scripts/build_bin1 icloudpd
scripts/build_bin1 icloud
```
Note: that command is for Linux, including devcontainers. Windows & macOS scripts must be executed on respective platforms.

Building Linux static executables:

``` sh
scripts/build_static icloudpd
scripts/build_static icloud
```

Building Python wheels (with executable):

``` sh
scripts/build_whl
```
Note: that the step expects executables to be already prepared by previous steps

Building NPM packages (with single executables; platform-specific):

``` sh
scripts/build_npm 1.32.2
```
Note: that the step expects executables to be already prepared by previous steps

### Building packages (alternative for Linux)

``` sh
docker buildx create --use --driver=docker-container --name container --bootstrap
docker buildx build . --cache-to type=local,dest=.cache,mode=max --cache-from type=local,src=.cache --platform=linux/amd64 --builder=container --progress plain -o dist -f Dockerfile.build
```

Note: command will produce binaries and .whl for selected platform in dist folder

For `musl` binaries, use `Dockerfile.build-musl`

### Building the Docker

``` sh
docker build -t icloudpd_dev_ .
```
Note: command packs existing musl binaries from dist folder

### Developing Documentation

To compile docs and start web server with hot reloading:

``` sh
sphinx-autobuild docs docs/_build/html
```

## How to write a unit test

The unit tests are a very important asset of this project. Due to our 100% test coverage we can safely use great tools like [Dependabot](dependabot.com) and be sure that the implementation of a new feature or fixing of a bug does not lead to further issues.

We're relying on [pytest](pytest.org) for the creation of our tests and [VCR.py](https://github.com/kevin1024/vcrpy) for automatic mocking of the communication to iCloud. This makes the creation of test cases rather simple as you don't have to deal with the communication to iCloud itself and can just focus on the "real test". Both tools maintain great howtos that can be found here:

* pytest documentation: https://docs.pytest.org/en/stable/
* VCR.py documentation: https://vcrpy.readthedocs.io/en/latest/

It is highly recommended having a look at those.

The process is mostly like this (assuming we're talking about a bug fix here...)

1. Is there already a related test case existing? If so you can just check if an existing test needs to check for another situation.
1. If not, then you need to make sure you have corresponding test-data at hand; that means: your iCloud photos library should have a constellation that leads to the error in `icloudpd`.
1. Add a test-function that runs `icloudpd` with the necessary start parameters, referencing to a new cassette file.
1. **VERY IMPORTANT:** the real iCloud response is cached, so every image is saved in the cassette. That means:
   1. Don't use private photos!
   1. Keep the dataset small (p.e. using `--recent`)
   1. Remove your personal information from the cached REST-response (Name, email addresses)
1. Go back to the previous step and verify again that you followed the recommendations!
1. Now you can start adding tests.

Refer to the existing tests for inspiration. A very simple test to understand the basic idea might be the test for the listing of albums option in `tests/test_listing_albums.py`.

When testing a bug fix it is important to test the faulty behavior and also the expected behavior.

## How to release

We have GitHub actions taking care for building, testing, and releasing software. Building and testing are happening automatically on git pushed, pull requests, and merges. For releases the following steps are manual:
- Bump version in all files, including all source files
- Update CHANGELOG.md with release changes if they were not added with commits
- Update CHANGELOG.md with date of the release
- Commit & push changes (either directly or through pull requests)
- Add version tag to head (`git tag v1.32.2`) and push it to master (`git push origin v1.32.2`) -- there seems to be no way to do that in UI
