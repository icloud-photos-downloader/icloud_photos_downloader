# GitHub Actions workflows

How CI is set up for icloudpd: what runs when, and why it is set up this way.

## What runs when

| Workflow | Runs on | Does |
|---|---|---|
| `quality-checks.yml` | every push, pull request, manual | lint, type check and tests on all supported Python versions (Linux), plus tests on Windows and macOS |
| `produce-artifacts.yml` | pull request, manual | full build: calls `build-package.yml` to build every package and run the compatibility tests, then compiles release notes |
| `create-release.yml` | `v*` tag push | full build like above, then `publish.yml` (PyPI, Docker Hub, npm, GitHub release) |
| `refresh-docs.yml` | `v*` tag push, manual | builds the documentation (`build-docs.yml`) and publishes it to GitHub Pages (`publish-docs.yml`) |
| `codeql-analysis.yml` | push and pull request to `master`, weekly | CodeQL security scan |

`build-package.yml`, `patch-version.yml`, `extract-changelog.yml`, `compile-notes.yml`, `build-docs.yml`, `publish-docs.yml` and `publish.yml` are reusable workflows: they only run when another workflow calls them.

## Versions in one place

- **Python used for builds:** `PYTHON_VERSION` at the top of `build-package.yml`. It is passed to `Dockerfile.build*` as a build argument; the Dockerfiles default to the same version for local builds.
- **Supported Python versions tested:** the `&supported-pythons` list in `quality-checks.yml` (keep it in sync with `requires-python` in `pyproject.toml`).
- **Runners:** `ubuntu-24.04` / `ubuntu-24.04-arm`, `macos-15` / `macos-15-intel` and `windows-2022` / `windows-2025`. Linux binaries and Docker images are built inside `python:<version>` containers, so the runner OS does not change what is built. macOS binaries are built natively: `macos-15` (Apple Silicon) builds `macos-arm64` and `macos-15-intel` builds `macos-amd64`, and the macOS tests run the amd64 entries on `macos-15-intel`. When GitHub retires `macos-15-intel`, the macOS 26 Intel runner can take its place.

## Compatibility tests

`build-package.yml` checks that icloudpd installs and runs (`--version`, and again with a non-default time zone and locale: "tzlc") on many Linux distributions and architectures, through pip, the standalone binaries (glibc and musl), npm/npx and Docker. `scripts/compile_compatibility.py` and `scripts/compile_tzlc.py` turn the results into the two compatibility tables in the release notes. The musl binary is only tested on Alpine: it can't run on glibc distributions, while the glibc binary is tested on both.

Each test kind (for example "binary on apk-based images") runs as **one job per architecture**. The job calls `scripts/compat_test`, which loops over that job's list of images, a few at a time, and for each image:

1. pulls it, and skips it if it does not exist for the platform (Docker pulls an image that only exists for another platform, e.g. `ubuntu:precise` on arm64, but can't run it, so the image's platform is checked too),
2. runs the test command and the tzlc command in the container,
3. writes `compatibility/<kind>.<image>.<arch>.pass|fail` and `tzlc/...` result files.

A failing test does not fail the job, so `scripts/compat_test` makes them visible instead: the job summary gets a table with the test and tzlc result per image, and each job adds a warning annotation listing the images where a test failed.

The image lists are in the job's `Run tests on ... images` step. To add or drop a distribution, edit that list.

Which releases are tested: those that still get free security updates from the distribution itself (Debian including LTS, Ubuntu's standard support without the paid ESM, Alpine's official support), plus releases whose free support ended less than a year ago, since many NAS and Docker setups move to a new release a while later. Check the lists when a new release comes out and once a year: add new releases, and drop releases more than a year past their end of support. https://endoflife.date has the dates. icloudpd may still work on older releases; it just isn't tested there. A release is only tested where icloudpd can work on it at all: Debian 11 is only in the binary test, because its Python (3.9) is older than icloudpd needs (3.11) and its Node.js too old for the npm package.

You can run a kind locally with Docker, for example with binaries in `dist/`:

```sh
scripts/compat_test bin_musl-apk arm64 arm64 "" 1.32.3 <<'EOF'
alpine_3_22 alpine:3.22
alpine_3_21 alpine:3.21
EOF
```

## Keeping runs fast and bounded

- **Concurrency:** `quality-checks.yml` and `produce-artifacts.yml` cancel an older run on the same branch or pull request when a newer one starts.
- **Timeouts:** every job has `timeout-minutes` (15 in Quality Checks; 60 for build jobs and 30 for the rest elsewhere), instead of GitHub's default of 6 hours.
- **No apt on the runner where avoidable:** tests only need one locale each (`de_DE.UTF-8` for the unit tests, `ru_RU.UTF-8` for the tzlc check), so jobs run `sudo locale-gen <locale>` instead of `apt-get install locales-all`, which sometimes took minutes depending on the package mirror.
- **Skipping:** `skip_check` (fkirc/skip-duplicate-actions) skips a run whose content already passed, and runs whose only changes are Markdown, `docs/` or `examples/`.

## History

- 2026-10: runners moved from `macos-14` (retired by GitHub on 2026-11-02) to `macos-15` and from `ubuntu-22.04` to `ubuntu-24.04`; actions moved to their Node 24 releases and CodeQL to v4; concurrency, timeouts and `locale-gen` were added; the 332 per-image Linux compatibility jobs were batched into 29 jobs (376 → 73 jobs per full build), with the same tests and results. Details are in the commit messages.
- 2026-11: end-of-life distributions dropped from the compatibility tests (Debian 6–10, Ubuntu 12.04–20.04, Alpine 3.10–3.19), and the current releases added (Debian 13, Ubuntu 26.04, Alpine 3.23 and 3.24, `python:3.15-alpine3.24` instead of `python:3.13-alpine3.19`). Debian 11 (binary only) and Alpine 3.20/3.21 stay until a year after their end of support.
