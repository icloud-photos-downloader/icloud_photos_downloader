from typing import Any, Dict
from unittest import TestCase

from pyicloud_ipd.utils import disambiguate_filenames
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize, VersionSize

class PathsTestCase(TestCase):
    def test_disambiguate_filenames_all_diff(self) -> None:
        """ want all and they are all different (probably unreal case) """
        _setup: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.DNG"
            },
            AssetVersionSize.ALTERNATIVE: {
                "filename": "IMG_1.HEIC"
            },
            AssetVersionSize.ADJUSTED: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.MEDIUM: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.THUMB: {
                "filename": "IMG_1.JPG"
            },
            LivePhotoVersionSize.ORIGINAL: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.MEDIUM: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.THUMB: {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.DNG"
            },
            AssetVersionSize.ALTERNATIVE: {
                "filename": "IMG_1.HEIC"
            },
            AssetVersionSize.ADJUSTED: {
                "filename": "IMG_1.JPG"
            },
        }
        _result = disambiguate_filenames(_setup, [AssetVersionSize.ORIGINAL, AssetVersionSize.ALTERNATIVE, AssetVersionSize.ADJUSTED])
        self.assertDictEqual(_result, _expect)
    
    def test_disambiguate_filenames_keep_orgraw_alt_adj(self) -> None:
        """ keep originals as raw, keep alt as well, but edit alt; edits are the same file type - alternative will be renamed """
        _setup: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.DNG"
            },
            AssetVersionSize.ALTERNATIVE: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.ADJUSTED: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.MEDIUM: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.THUMB: {
                "filename": "IMG_1.JPG"
            },
            LivePhotoVersionSize.ORIGINAL: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.MEDIUM: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.THUMB: {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.DNG"
            },
            AssetVersionSize.ALTERNATIVE: {
                "filename": "IMG_1-alternative.JPG"
            },
            AssetVersionSize.ADJUSTED: {
                "filename": "IMG_1.JPG"
            },
        }
        _result = disambiguate_filenames(_setup, [AssetVersionSize.ORIGINAL, AssetVersionSize.ALTERNATIVE, AssetVersionSize.ADJUSTED])
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_latest(self) -> None:
        """ want to keep just latest """
        _setup: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.HEIC"
            },
            AssetVersionSize.ADJUSTED: {
                "filename": "IMG_1.HEIC"
            },
            AssetVersionSize.MEDIUM: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.THUMB: {
                "filename": "IMG_1.JPG"
            },
            LivePhotoVersionSize.ORIGINAL: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.MEDIUM: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.THUMB: {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ADJUSTED: {
                "filename": "IMG_1.HEIC"
            },
        }
        _result = disambiguate_filenames(_setup, [AssetVersionSize.ADJUSTED])
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_org_adj_diff(self) -> None:
        """ keep as is """
        _setup: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.HEIC"
            },
            AssetVersionSize.ADJUSTED: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.MEDIUM: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.THUMB: {
                "filename": "IMG_1.JPG"
            },
            LivePhotoVersionSize.ORIGINAL: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.MEDIUM: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.THUMB: {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.HEIC"
            },
            AssetVersionSize.ADJUSTED: {
                "filename": "IMG_1.JPG"
            },
        }
        _result = disambiguate_filenames(_setup, [AssetVersionSize.ORIGINAL, AssetVersionSize.ADJUSTED])
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_org_alt_diff(self) -> None:
        """ keep then as is """
        _setup: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.DNG"
            },
            AssetVersionSize.ALTERNATIVE: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.MEDIUM: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.THUMB: {
                "filename": "IMG_1.JPG"
            },
            LivePhotoVersionSize.ORIGINAL: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.MEDIUM: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.THUMB: {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.DNG"
            },
            AssetVersionSize.ALTERNATIVE: {
                "filename": "IMG_1.JPG"
            },
        }
        _result = disambiguate_filenames(_setup, [AssetVersionSize.ORIGINAL, AssetVersionSize.ALTERNATIVE])
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_all_when_org_adj_same(self) -> None:
        """ tweak adj """
        _setup: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.ALTERNATIVE: {
                "filename": "IMG_1.CR2"
            },
            AssetVersionSize.ADJUSTED: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.MEDIUM: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.THUMB: {
                "filename": "IMG_1.JPG"
            },
            LivePhotoVersionSize.ORIGINAL: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.MEDIUM: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.THUMB: {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.ALTERNATIVE: {
                "filename": "IMG_1.CR2"
            },
            AssetVersionSize.ADJUSTED: {
                "filename": "IMG_1-adjusted.JPG"
            },
        }
        _result = disambiguate_filenames(_setup, [AssetVersionSize.ORIGINAL, AssetVersionSize.ADJUSTED, AssetVersionSize.ALTERNATIVE])
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_org_alt_missing(self) -> None:
        """ keep alt when it is missing """
        _setup: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.HEIC"
            },
            AssetVersionSize.ADJUSTED: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.MEDIUM: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.THUMB: {
                "filename": "IMG_1.JPG"
            },
            LivePhotoVersionSize.ORIGINAL: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.MEDIUM: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.THUMB: {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.HEIC"
            },
        }
        _result = disambiguate_filenames(_setup, [AssetVersionSize.ORIGINAL, AssetVersionSize.ALTERNATIVE])
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_alt_missing(self) -> None:
        """ keep alt when it is missing """
        _setup: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.HEIC"
            },
            AssetVersionSize.MEDIUM: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.THUMB: {
                "filename": "IMG_1.JPG"
            },
            LivePhotoVersionSize.ORIGINAL: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.MEDIUM: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.THUMB: {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ALTERNATIVE: {
                "filename": "IMG_1.HEIC"
            },
        }
        _result = disambiguate_filenames(_setup, [AssetVersionSize.ALTERNATIVE])
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_adj_alt_missing(self) -> None:
        """ keep alt when it is missing """
        _setup: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ORIGINAL: {
                "filename": "IMG_1.HEIC"
            },
            AssetVersionSize.MEDIUM: {
                "filename": "IMG_1.JPG"
            },
            AssetVersionSize.THUMB: {
                "filename": "IMG_1.JPG"
            },
            LivePhotoVersionSize.ORIGINAL: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.MEDIUM: {
                "filename": "IMG_1.MOV"
            },
            LivePhotoVersionSize.THUMB: {
                "filename": "IMG_1.MOV"
            },
        }
        _expect: Dict[VersionSize, Dict[str, Any]] = {
            AssetVersionSize.ADJUSTED: {
                "filename": "IMG_1.HEIC"
            },
        }
        _result = disambiguate_filenames(_setup, [AssetVersionSize.ADJUSTED, AssetVersionSize.ALTERNATIVE])
        self.assertDictEqual(_result, _expect)        