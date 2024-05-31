from typing import Any, Dict
from unittest import TestCase

from pyicloud_ipd.utils import disambiguate_filenames

class PathsTestCase(TestCase):
    def test_disambiguate_filenames_all_different(self) -> None:
        """probably unreal use case """
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
            "medium": {
                "filename": "IMG_1-medium.JPG"
            },
            "thumb": {
                "filename": "IMG_1-thumb.JPG"
            },
            "originalVideo": {
                "filename": "IMG_1.MOV"
            },
            "mediumVideo": {
                "filename": "IMG_1-medium.MOV"
            },
            "thumbVideo": {
                "filename": "IMG_1-thumb.MOV"
            },
        }
        _result = disambiguate_filenames(_setup)
        self.assertDictEqual(_result, _expect)
    
    def test_disambiguate_filenames_adj_alt_same(self) -> None:
        """ keep adj the same name as org, so it is picked by soft matching names """
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
            "medium": {
                "filename": "IMG_1-medium.JPG"
            },
            "thumb": {
                "filename": "IMG_1-thumb.JPG"
            },
            "originalVideo": {
                "filename": "IMG_1.MOV"
            },
            "mediumVideo": {
                "filename": "IMG_1-medium.MOV"
            },
            "thumbVideo": {
                "filename": "IMG_1-thumb.MOV"
            },
        }
        _result = disambiguate_filenames(_setup)
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_org_adj_same(self) -> None:
        """ tweak adj """
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
            "original": {
                "filename": "IMG_1.HEIC"
            },
            "adjusted": {
                "filename": "IMG_1-adjusted.HEIC"
            },
            "medium": {
                "filename": "IMG_1-medium.JPG"
            },
            "thumb": {
                "filename": "IMG_1-thumb.JPG"
            },
            "originalVideo": {
                "filename": "IMG_1.MOV"
            },
            "mediumVideo": {
                "filename": "IMG_1-medium.MOV"
            },
            "thumbVideo": {
                "filename": "IMG_1-thumb.MOV"
            },
        }
        _result = disambiguate_filenames(_setup)
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_org_adj_diff(self) -> None:
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
            "medium": {
                "filename": "IMG_1-medium.JPG"
            },
            "thumb": {
                "filename": "IMG_1-thumb.JPG"
            },
            "originalVideo": {
                "filename": "IMG_1.MOV"
            },
            "mediumVideo": {
                "filename": "IMG_1-medium.MOV"
            },
            "thumbVideo": {
                "filename": "IMG_1-thumb.MOV"
            },
        }
        _result = disambiguate_filenames(_setup)
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_org_alt_diff(self) -> None:
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
            "medium": {
                "filename": "IMG_1-medium.JPG"
            },
            "thumb": {
                "filename": "IMG_1-thumb.JPG"
            },
            "originalVideo": {
                "filename": "IMG_1.MOV"
            },
            "mediumVideo": {
                "filename": "IMG_1-medium.MOV"
            },
            "thumbVideo": {
                "filename": "IMG_1-thumb.MOV"
            },
        }
        _result = disambiguate_filenames(_setup)
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_org_adj_same_with_alt_diff(self) -> None:
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
            "medium": {
                "filename": "IMG_1-medium.JPG"
            },
            "thumb": {
                "filename": "IMG_1-thumb.JPG"
            },
            "originalVideo": {
                "filename": "IMG_1.MOV"
            },
            "mediumVideo": {
                "filename": "IMG_1-medium.MOV"
            },
            "thumbVideo": {
                "filename": "IMG_1-thumb.MOV"
            },
        }
        _result = disambiguate_filenames(_setup)
        self.assertDictEqual(_result, _expect)
