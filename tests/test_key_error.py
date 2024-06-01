import json
from sys import path
from typing import Any, Dict
from unittest import TestCase


class PathsTestCase(TestCase):
    def test_load(self) -> None:
        with open (path.join("data", "key_error1.json"), "r") as _file:
            _data = json.loads(_file.read())
