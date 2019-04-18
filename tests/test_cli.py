# coding=utf-8
from unittest import TestCase
from vcr import VCR
import os
import click
from click.testing import CliRunner
from icloudpd.base import main

vcr = VCR(decode_compressed_response=True)


class CliTestCase(TestCase):
    def test_cli(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0

    def test_log_levels(self):
        if not os.path.exists("tests/fixtures/Photos"):
            os.makedirs("tests/fixtures/Photos")
        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            # Pass fixed client ID via environment variable
            os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "0",
                    "--log-level",
                    "info",
                    "-d"
                    "tests/fixtures/Photos",
                ],
            )
            assert result.exit_code == 0
        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            result = runner.invoke(
                main,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "0",
                    "--log-level",
                    "error",
                    "-d",
                    "tests/fixtures/Photos",
                ],
            )
            assert result.exit_code == 0

    def test_tqdm(self):
        if not os.path.exists("tests/fixtures/Photos"):
            os.makedirs("tests/fixtures/Photos")
        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            # Force tqdm progress bar via ENV var
            os.environ["FORCE_TQDM"] = "yes"
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "0",
                    "-d",
                    "tests/fixtures/Photos",
                ],
            )
            del os.environ["FORCE_TQDM"]
            assert result.exit_code == 0

    def test_unicode_directory(self):
        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            # Pass fixed client ID via environment variable
            os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "0",
                    "--log-level",
                    "info",
                    "-d",
                    "tests/fixtures/相片",
                ],
            )
            assert result.exit_code == 0
