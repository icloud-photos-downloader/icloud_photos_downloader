#!/bin/bash
set -e
rm -rf ./vendor/pyicloud-*.zip
pip download --no-deps --dest ./vendor \
  git+https://github.com/ndbroadbent/pyicloud.git#egg=pyicloud
