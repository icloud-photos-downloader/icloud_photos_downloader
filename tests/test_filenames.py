from typing import Any, Dict
from unittest import TestCase

from pyicloud_ipd.asset_version import AssetVersion
from pyicloud_ipd.utils import disambiguate_filenames
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize, VersionSize


class PathsTestCase(TestCase):
    def test_disambiguate_filenames_all_diff(self) -> None:
        """want all and they are all different (probably unreal case)"""
        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.DNG", 1, "http", "jpeg"),
            AssetVersionSize.ALTERNATIVE: AssetVersion("IMG_1.HEIC", 1, "http", "jpeg"),
            AssetVersionSize.ADJUSTED: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.MEDIUM: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.THUMB: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.MEDIUM: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.THUMB: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.DNG", 1, "http", "jpeg"),
            AssetVersionSize.ALTERNATIVE: AssetVersion("IMG_1.HEIC", 1, "http", "jpeg"),
            AssetVersionSize.ADJUSTED: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
        }
        _result = disambiguate_filenames(
            _setup,
            [AssetVersionSize.ORIGINAL, AssetVersionSize.ALTERNATIVE, AssetVersionSize.ADJUSTED],
        )
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_orgraw_alt_adj(self) -> None:
        """keep originals as raw, keep alt as well, but edit alt; edits are the same file type - alternative will be renamed"""
        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.DNG", 1, "http", "jpeg"),
            AssetVersionSize.ALTERNATIVE: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.ADJUSTED: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.MEDIUM: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.THUMB: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.MEDIUM: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.THUMB: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.DNG", 1, "http", "jpeg"),
            AssetVersionSize.ALTERNATIVE: AssetVersion("IMG_1-alternative.JPG", 1, "http", "jpeg"),
            AssetVersionSize.ADJUSTED: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
        }
        _result = disambiguate_filenames(
            _setup,
            [AssetVersionSize.ORIGINAL, AssetVersionSize.ALTERNATIVE, AssetVersionSize.ADJUSTED],
        )
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_latest(self) -> None:
        """want to keep just latest"""
        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.HEIC", 1, "http", "jpeg"),
            AssetVersionSize.ADJUSTED: AssetVersion("IMG_1.HEIC", 1, "http", "jpeg"),
            AssetVersionSize.MEDIUM: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.THUMB: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.MEDIUM: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.THUMB: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ADJUSTED: AssetVersion("IMG_1.HEIC", 1, "http", "jpeg"),
        }
        _result = disambiguate_filenames(_setup, [AssetVersionSize.ADJUSTED])
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_org_adj_diff(self) -> None:
        """keep as is"""
        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.HEIC", 1, "http", "jpeg"),
            AssetVersionSize.ADJUSTED: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.MEDIUM: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.THUMB: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.MEDIUM: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.THUMB: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.HEIC", 1, "http", "jpeg"),
            AssetVersionSize.ADJUSTED: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
        }
        _result = disambiguate_filenames(
            _setup, [AssetVersionSize.ORIGINAL, AssetVersionSize.ADJUSTED]
        )
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_org_alt_diff(self) -> None:
        """keep then as is"""
        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.DNG", 1, "http", "jpeg"),
            AssetVersionSize.ALTERNATIVE: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.MEDIUM: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.THUMB: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.MEDIUM: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.THUMB: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.DNG", 1, "http", "jpeg"),
            AssetVersionSize.ALTERNATIVE: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
        }
        _result = disambiguate_filenames(
            _setup, [AssetVersionSize.ORIGINAL, AssetVersionSize.ALTERNATIVE]
        )
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_all_when_org_adj_same(self) -> None:
        """tweak adj"""
        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.ALTERNATIVE: AssetVersion("IMG_1.CR2", 1, "http", "jpeg"),
            AssetVersionSize.ADJUSTED: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.MEDIUM: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.THUMB: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.MEDIUM: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.THUMB: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.ALTERNATIVE: AssetVersion("IMG_1.CR2", 1, "http", "jpeg"),
            AssetVersionSize.ADJUSTED: AssetVersion("IMG_1-adjusted.JPG", 1, "http", "jpeg"),
        }
        _result = disambiguate_filenames(
            _setup,
            [AssetVersionSize.ORIGINAL, AssetVersionSize.ADJUSTED, AssetVersionSize.ALTERNATIVE],
        )
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_org_alt_missing(self) -> None:
        """keep alt when it is missing"""
        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.HEIC", 1, "http", "jpeg"),
            AssetVersionSize.ADJUSTED: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.MEDIUM: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.THUMB: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.MEDIUM: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.THUMB: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.HEIC", 1, "http", "jpeg"),
        }
        _result = disambiguate_filenames(
            _setup, [AssetVersionSize.ORIGINAL, AssetVersionSize.ALTERNATIVE]
        )
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_alt_missing(self) -> None:
        """keep alt when it is missing"""
        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.HEIC", 1, "http", "jpeg"),
            AssetVersionSize.MEDIUM: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.THUMB: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.MEDIUM: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.THUMB: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ALTERNATIVE: AssetVersion("IMG_1.HEIC", 1, "http", "jpeg"),
        }
        _result = disambiguate_filenames(_setup, [AssetVersionSize.ALTERNATIVE])
        self.assertDictEqual(_result, _expect)

    def test_disambiguate_filenames_keep_adj_alt_missing(self) -> None:
        """keep alt when it is missing"""
        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion("IMG_1.HEIC", 1, "http", "jpeg"),
            AssetVersionSize.MEDIUM: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            AssetVersionSize.THUMB: AssetVersion("IMG_1.JPG", 1, "http", "jpeg"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.MEDIUM: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
            LivePhotoVersionSize.THUMB: AssetVersion("IMG_1.MOV", 1, "http", "jpeg"),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ADJUSTED: AssetVersion("IMG_1.HEIC", 1, "http", "jpeg"),
        }
        _result = disambiguate_filenames(
            _setup, [AssetVersionSize.ADJUSTED, AssetVersionSize.ALTERNATIVE]
        )
        self.assertDictEqual(_result, _expect)
