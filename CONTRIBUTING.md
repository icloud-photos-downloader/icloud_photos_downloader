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

[Code of Conduct](#code_of_conduct)

Please note we have a [code of conduct](#code_of_conduct), please follow it in all your interactions with the project.

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
  unit test. All other tests pass. Run `./scripts/test`
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

## Code of Conduct

### Our Pledge

In the interest of fostering an open and welcoming environment, we as
contributors and maintainers pledge to making participation in our project and
our community a harassment-free experience for everyone, regardless of age, body
size, disability, ethnicity, gender identity and expression, level of experience,
nationality, personal appearance, race, religion, or sexual identity and
orientation.

### Our Standards

Examples of behavior that contributes to creating a positive environment
include:

* Using welcoming and inclusive language
* Being respectful of differing viewpoints and experiences
* Gracefully accepting constructive criticism
* Focusing on what is best for the community
* Showing empathy towards other community members

Examples of unacceptable behavior by participants include:

* The use of sexualized language or imagery and unwelcome sexual attention or
advances
* Trolling, insulting/derogatory comments, and personal or political attacks
* Public or private harassment
* Publishing others' private information, such as a physical or electronic
  address, without explicit permission
* Other conduct which could reasonably be considered inappropriate in a
  professional setting

### Our Responsibilities

Project maintainers are responsible for clarifying the standards of acceptable
behavior and are expected to take appropriate and fair corrective action in
response to any instances of unacceptable behavior.

Project maintainers have the right and responsibility to remove, edit, or
reject comments, commits, code, wiki edits, issues, and other contributions
that are not aligned to this Code of Conduct, or to ban temporarily or
permanently any contributor for other behaviors that they deem inappropriate,
threatening, offensive, or harmful.

### Scope

This Code of Conduct applies both within project spaces and in public spaces
when an individual is representing the project or its community. Examples of
representing a project or community include using an official project e-mail
address, posting via an official social media account, or acting as an appointed
representative at an online or offline event. Representation of a project may be
further defined and clarified by project maintainers.

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be
reported by contacting the project team by opening an [issue](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/new). All
complaints will be reviewed and investigated and will result in a response that
is deemed necessary and appropriate to the circumstances. The project team is
obligated to maintain confidentiality with regard to the reporter of an incident.
Further details of specific enforcement policies may be posted separately.

Project maintainers who do not follow or enforce the Code of Conduct in good
faith may face temporary or permanent repercussions as determined by other
members of the project's leadership.

### Attribution

This Code of Conduct is adapted from the [Contributor Covenant][homepage], version 1.4,
available at [http://contributor-covenant.org/version/1/4][version]

[homepage]: http://contributor-covenant.org
[version]: http://contributor-covenant.org/version/1/4/
