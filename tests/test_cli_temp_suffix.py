from argparse import ArgumentError
from unittest import TestCase

from icloudpd.cli import parse


class TempSuffixOptionTestCase(TestCase):
    def test_default_and_custom_suffix(self) -> None:
        _, user_configs = parse(["--username", "u", "--directory", "d"])
        self.assertEqual(".part", user_configs[0].temp_suffix)
        _, user_configs = parse(
            ["--username", "u", "--directory", "d", "--temp-suffix", ".icloudpd"]
        )
        self.assertEqual(".icloudpd", user_configs[0].temp_suffix)

    def test_suffix_with_a_path_separator_is_rejected(self) -> None:
        for suffix in ("", "a/b", "a\\b"):
            with self.assertRaises(ArgumentError):
                parse(["--username", "u", "--directory", "d", "--temp-suffix", suffix])
