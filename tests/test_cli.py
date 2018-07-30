from unittest import TestCase
import click
from click.testing import CliRunner
from icloudpd.base import main

class CliTestCase(TestCase):
    def test_cli(self):
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        assert result.exit_code == 0
