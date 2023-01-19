# coding=utf-8
from unittest import TestCase
import os
import shutil
from vcr import VCR
import pytest
from click.testing import CliRunner
from icloudpd.base import main
import inspect

vcr = VCR(decode_compressed_response=True)


class CliTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def test_cli(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0

    def test_log_levels(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

        parameters = [
            ("debug", ["DEBUG", "INFO"], []),
            ("info", ["INFO"], ["DEBUG"]),
            ("error", [], ["DEBUG", "INFO"]),
        ]
        for log_level, expected, not_expected in parameters:
            self._caplog.clear()
            with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
                # Pass fixed client ID via environment variable
                runner = CliRunner(env={
                    "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
                })
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
                        log_level,
                        "-d",
                        base_dir,
                    ],
                )
                assert result.exit_code == 0
            for text in expected:
                self.assertIn(text, self._caplog.text)
            for text in not_expected:
                self.assertNotIn(text, self._caplog.text)

    def test_tqdm(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            # Force tqdm progress bar via ENV var
            runner = CliRunner(env={
                "FORCE_TQDM": "yes",
                "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
            })
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
                    base_dir,
                ],
            )
            assert result.exit_code == 0

    def test_unicode_directory(self):
        base_dir = os.path.normpath(f"tests/fixtures/相片")
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            # Pass fixed client ID via environment variable
            runner = CliRunner(env={
                "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
            })
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

    def test_missing_directory(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)

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
                base_dir
            ],
        )
        assert result.exit_code == 2

    def test_missing_directory_param(self):
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
            ],
        )
        assert result.exit_code == 2
