from typing import Any, Dict
from unittest import TestCase

from pyicloud_ipd.utils import disambiguate_filenames

class PathsTestCase(TestCase):
    def test_disambiguate_filenames_all_diff(self) -> None:
        """ want all and they are all different (probably unreal case) """
        _setup: Dict[str, Dict[str, Any]] = {
            "original": {
                "filename": "IMG_1.DNG"
            },
            "alternative": {
                "filename": "IMG_1.HEIC"
            },
            "adjusted": {
                "filename": "IMG_1.JPG"
            },
            "medium": {
                "filename": "IMG_1.JPG"
            },
            "thumb": {
                "filename": "IMG_1.JPG"
            },
            "originalVideo": {
                "filename": "IMG_1.MOV"
            },
            "mediumVideo": {
                "filename": "IMG_1.MOV"
            },
            "thumbVideo": {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[str, Dict[str, Any]] = {
            "original": {
                "filename": "IMG_1.DNG"
            },
            "alternative": {
                "filename": "IMG_1.HEIC"
            },
            "adjusted": {
                "filename": "IMG_1.JPG"
            },
        }
        _result = disambiguate_filenames(_setup, ["original", "alternative", "adjusted"])
        self.assertDictEqual(_result, _expect)
    
    def test_disambiguate_filenames_keep_orgraw_alt_adj(self) -> None:
        """ keep originals as raw, keep alt as well, but edit alt; edits are the same file type - alternative will be renamed """
        _setup: Dict[str, Dict[str, Any]] = {
            "original": {
                "filename": "IMG_1.DNG"
            },
            "alternative": {
                "filename": "IMG_1.JPG"
            },
            "adjusted": {
                "filename": "IMG_1.JPG"
            },
            "medium": {
                "filename": "IMG_1.JPG"
            },
            "thumb": {
                "filename": "IMG_1.JPG"
            },
            "originalVideo": {
                "filename": "IMG_1.MOV"
            },
            "mediumVideo": {
                "filename": "IMG_1.MOV"
            },
            "thumbVideo": {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[str, Dict[str, Any]] = {
            "original": {
                "filename": "IMG_1.DNG"
            },
            "alternative": {
                "filename": "IMG_1-alternative.JPG"
            },
            "adjusted": {
                "filename": "IMG_1.JPG"
            },
        }
        _result = disambiguate_filenames(_setup, ["original", "alternative", "adjusted"])
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_latest(self) -> None:
        """ want to keep just latest """
        _setup: Dict[str, Dict[str, Any]] = {
            "original": {
                "filename": "IMG_1.HEIC"
            },
            "adjusted": {
                "filename": "IMG_1.HEIC"
            },
            "medium": {
                "filename": "IMG_1.JPG"
            },
            "thumb": {
                "filename": "IMG_1.JPG"
            },
            "originalVideo": {
                "filename": "IMG_1.MOV"
            },
            "mediumVideo": {
                "filename": "IMG_1.MOV"
            },
            "thumbVideo": {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[str, Dict[str, Any]] = {
            "adjusted": {
                "filename": "IMG_1.HEIC"
            },
        }
        _result = disambiguate_filenames(_setup, ["adjusted"])
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_org_adj_diff(self) -> None:
        """ keep as is """
        _setup: Dict[str, Dict[str, Any]] = {
            "original": {
                "filename": "IMG_1.HEIC"
            },
            "adjusted": {
                "filename": "IMG_1.JPG"
            },
            "medium": {
                "filename": "IMG_1.JPG"
            },
            "thumb": {
                "filename": "IMG_1.JPG"
            },
            "originalVideo": {
                "filename": "IMG_1.MOV"
            },
            "mediumVideo": {
                "filename": "IMG_1.MOV"
            },
            "thumbVideo": {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[str, Dict[str, Any]] = {
            "original": {
                "filename": "IMG_1.HEIC"
            },
            "adjusted": {
                "filename": "IMG_1.JPG"
            },
        }
        _result = disambiguate_filenames(_setup, ["original", "adjusted"])
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_org_alt_diff(self) -> None:
        """ keep then as is """
        _setup: Dict[str, Dict[str, Any]] = {
            "original": {
                "filename": "IMG_1.DNG"
            },
            "alternative": {
                "filename": "IMG_1.JPG"
            },
            "medium": {
                "filename": "IMG_1.JPG"
            },
            "thumb": {
                "filename": "IMG_1.JPG"
            },
            "originalVideo": {
                "filename": "IMG_1.MOV"
            },
            "mediumVideo": {
                "filename": "IMG_1.MOV"
            },
            "thumbVideo": {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[str, Dict[str, Any]] = {
            "original": {
                "filename": "IMG_1.DNG"
            },
            "alternative": {
                "filename": "IMG_1.JPG"
            },
        }
        _result = disambiguate_filenames(_setup, ["original", "alternative"])
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_all_when_org_adj_same(self) -> None:
        """ tweak adj """
        _setup: Dict[str, Dict[str, Any]] = {
            "original": {
                "filename": "IMG_1.JPG"
            },
            "alternative": {
                "filename": "IMG_1.CR2"
            },
            "adjusted": {
                "filename": "IMG_1.JPG"
            },
            "medium": {
                "filename": "IMG_1.JPG"
            },
            "thumb": {
                "filename": "IMG_1.JPG"
            },
            "originalVideo": {
                "filename": "IMG_1.MOV"
            },
            "mediumVideo": {
                "filename": "IMG_1.MOV"
            },
            "thumbVideo": {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[str, Dict[str, Any]] = {
            "original": {
                "filename": "IMG_1.JPG"
            },
            "alternative": {
                "filename": "IMG_1.CR2"
            },
            "adjusted": {
                "filename": "IMG_1-adjusted.JPG"
            },
        }
        _result = disambiguate_filenames(_setup, ["original", "adjusted", "alternative"])
        self.assertDictEqual(_result, _expect)
