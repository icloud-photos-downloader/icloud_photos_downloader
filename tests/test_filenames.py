from typing import Any, Callable, Dict
from unittest import TestCase
from unittest.mock import Mock

from icloudpd.base import lp_filename_concatinator as mock_lp_filename_generator
from pyicloud_ipd.asset_version import AssetVersion
from pyicloud_ipd.utils import disambiguate_filenames
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize, VersionSize


def create_mock_photo_asset(base_filename: str = "IMG_1") -> Any:
    """Create a mock PhotoAsset for testing."""
    mock_photo = Mock()

    def mock_calculate_filename(
        version: AssetVersion,
        size: VersionSize,
        lp_filename_generator: Callable[[str], str],
        filename_override: str | None = None,
    ) -> str:
        """Mock implementation of calculate_version_filename."""
        if filename_override is not None:
            return filename_override

        # Simple mock logic - use type to determine extension
        if version.type == "com.apple.quicktime-movie":
            return f"{base_filename}.MOV"
        elif version.type == "public.heic":
            return f"{base_filename}.HEIC"
        elif version.type == "public.jpeg":
            return f"{base_filename}.JPG"
        elif version.type == "com.adobe.raw-image":
            return f"{base_filename}.DNG"
        elif version.type == "com.canon.cr2-raw-image":
            return f"{base_filename}.CR2"
        else:
            return f"{base_filename}.JPG"  # default

    mock_photo.calculate_version_filename = mock_calculate_filename
    return mock_photo


class PathsTestCase(TestCase):
    def test_disambiguate_filenames_all_diff(self) -> None:
        """want all and they are all different (probably unreal case)"""
        mock_photo = create_mock_photo_asset()

        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "com.adobe.raw-image", "blah"),
            AssetVersionSize.ALTERNATIVE: AssetVersion(1, "http", "public.heic", "blah"),
            AssetVersionSize.ADJUSTED: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.MEDIUM: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.THUMB: AssetVersion(1, "http", "public.jpeg", "blah"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.MEDIUM: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.THUMB: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "com.adobe.raw-image", "blah"),
            AssetVersionSize.ALTERNATIVE: AssetVersion(1, "http", "public.heic", "blah"),
            AssetVersionSize.ADJUSTED: AssetVersion(1, "http", "public.jpeg", "blah"),
        }
        _result, _overrides = disambiguate_filenames(
            _setup,
            [AssetVersionSize.ORIGINAL, AssetVersionSize.ALTERNATIVE, AssetVersionSize.ADJUSTED],
            mock_photo,
            mock_lp_filename_generator,
        )
        self.assertEqual(_result, _expect)
        self.assertEqual(_overrides, {})

    def test_disambiguate_filenames_keep_orgraw_alt_adj(self) -> None:
        """keep originals as raw, keep alt as well, but edit alt; edits are the same file type - alternative will be renamed"""
        mock_photo = create_mock_photo_asset()

        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "com.adobe.raw-image", "blah"),
            AssetVersionSize.ALTERNATIVE: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.ADJUSTED: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.MEDIUM: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.THUMB: AssetVersion(1, "http", "public.jpeg", "blah"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.MEDIUM: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.THUMB: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "com.adobe.raw-image", "blah"),
            AssetVersionSize.ALTERNATIVE: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.ADJUSTED: AssetVersion(1, "http", "public.jpeg", "blah"),
        }
        _result, _overrides = disambiguate_filenames(
            _setup,
            [AssetVersionSize.ORIGINAL, AssetVersionSize.ALTERNATIVE, AssetVersionSize.ADJUSTED],
            mock_photo,
            mock_lp_filename_generator,
        )

        # Check that alternative version gets renamed due to filename conflict
        self.assertEqual(len(_result), 3)
        self.assertIn(AssetVersionSize.ORIGINAL, _result)
        self.assertIn(AssetVersionSize.ALTERNATIVE, _result)
        self.assertIn(AssetVersionSize.ADJUSTED, _result)

        # Alternative should have filename override to disambiguate
        self.assertIsNotNone(_overrides.get(AssetVersionSize.ALTERNATIVE))

    def test_disambiguate_filenames_keep_latest(self) -> None:
        """just get the latest version"""
        mock_photo = create_mock_photo_asset()

        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "public.heic", "blah"),
            AssetVersionSize.ADJUSTED: AssetVersion(1, "http", "public.heic", "blah"),
            AssetVersionSize.MEDIUM: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.THUMB: AssetVersion(1, "http", "public.jpeg", "blah"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.MEDIUM: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.THUMB: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ADJUSTED: AssetVersion(1, "http", "public.heic", "blah"),
        }
        _result, _overrides = disambiguate_filenames(
            _setup, [AssetVersionSize.ADJUSTED], mock_photo, mock_lp_filename_generator
        )
        self.assertEqual(_result, _expect)
        self.assertEqual(_overrides, {})

    def test_disambiguate_filenames_keep_org_adj_diff(self) -> None:
        """keep then as is"""
        mock_photo = create_mock_photo_asset()

        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "public.heic", "blah"),
            AssetVersionSize.ADJUSTED: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.MEDIUM: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.THUMB: AssetVersion(1, "http", "public.jpeg", "blah"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.MEDIUM: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.THUMB: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "public.heic", "blah"),
            AssetVersionSize.ADJUSTED: AssetVersion(1, "http", "public.jpeg", "blah"),
        }
        _result, _overrides = disambiguate_filenames(
            _setup,
            [AssetVersionSize.ORIGINAL, AssetVersionSize.ADJUSTED],
            mock_photo,
            mock_lp_filename_generator,
        )
        self.assertEqual(_result, _expect)
        self.assertEqual(_overrides, {})

    def test_disambiguate_filenames_keep_org_alt_diff(self) -> None:
        """keep then as is"""
        mock_photo = create_mock_photo_asset()

        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "com.adobe.raw-image", "blah"),
            AssetVersionSize.ALTERNATIVE: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.MEDIUM: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.THUMB: AssetVersion(1, "http", "public.jpeg", "blah"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.MEDIUM: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.THUMB: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "com.adobe.raw-image", "blah"),
            AssetVersionSize.ALTERNATIVE: AssetVersion(1, "http", "public.jpeg", "blah"),
        }
        _result, _overrides = disambiguate_filenames(
            _setup,
            [AssetVersionSize.ORIGINAL, AssetVersionSize.ALTERNATIVE],
            mock_photo,
            mock_lp_filename_generator,
        )
        self.assertEqual(_result, _expect)
        self.assertEqual(_overrides, {})

    def test_disambiguate_filenames_keep_all_when_org_adj_same(self) -> None:
        """tweak adj"""
        mock_photo = create_mock_photo_asset()

        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.ALTERNATIVE: AssetVersion(
                1, "http", "com.canon.cr2-raw-image", "blah"
            ),
            AssetVersionSize.ADJUSTED: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.MEDIUM: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.THUMB: AssetVersion(1, "http", "public.jpeg", "blah"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.MEDIUM: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.THUMB: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.ALTERNATIVE: AssetVersion(
                1, "http", "com.canon.cr2-raw-image", "blah"
            ),
            AssetVersionSize.ADJUSTED: AssetVersion(1, "http", "public.jpeg", "blah"),
        }
        _result, _overrides = disambiguate_filenames(
            _setup,
            [AssetVersionSize.ORIGINAL, AssetVersionSize.ADJUSTED, AssetVersionSize.ALTERNATIVE],
            mock_photo,
            mock_lp_filename_generator,
        )

        # Check that adjusted version gets renamed due to filename conflict with original
        self.assertEqual(len(_result), 3)
        self.assertIn(AssetVersionSize.ORIGINAL, _result)
        self.assertIn(AssetVersionSize.ALTERNATIVE, _result)
        self.assertIn(AssetVersionSize.ADJUSTED, _result)

        # Adjusted should have filename override to disambiguate from original
        self.assertIsNotNone(_overrides.get(AssetVersionSize.ADJUSTED))

    def test_disambiguate_filenames_keep_org_alt_missing(self) -> None:
        """keep alt when it is missing"""
        mock_photo = create_mock_photo_asset()

        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "public.heic", "blah"),
            AssetVersionSize.ADJUSTED: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.MEDIUM: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.THUMB: AssetVersion(1, "http", "public.jpeg", "blah"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.MEDIUM: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.THUMB: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
        }
        _expect: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "public.heic", "blah"),
        }
        _result, _overrides = disambiguate_filenames(
            _setup,
            [AssetVersionSize.ORIGINAL, AssetVersionSize.ALTERNATIVE],
            mock_photo,
            mock_lp_filename_generator,
        )
        self.assertEqual(_result, _expect)
        self.assertEqual(_overrides, {})

    def test_disambiguate_filenames_keep_alt_missing(self) -> None:
        """keep alt when it is missing"""
        mock_photo = create_mock_photo_asset()

        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "public.heic", "blah"),
            AssetVersionSize.MEDIUM: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.THUMB: AssetVersion(1, "http", "public.jpeg", "blah"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.MEDIUM: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.THUMB: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
        }
        _result, _overrides = disambiguate_filenames(
            _setup, [AssetVersionSize.ALTERNATIVE], mock_photo, mock_lp_filename_generator
        )

        # Should get original as alternative since alternative is missing
        self.assertEqual(len(_result), 1)
        self.assertIn(AssetVersionSize.ALTERNATIVE, _result)
        self.assertEqual(_overrides, {})

    def test_disambiguate_filenames_keep_adj_alt_missing(self) -> None:
        """keep alt when it is missing"""
        mock_photo = create_mock_photo_asset()

        _setup: Dict[VersionSize, AssetVersion] = {
            AssetVersionSize.ORIGINAL: AssetVersion(1, "http", "public.heic", "blah"),
            AssetVersionSize.MEDIUM: AssetVersion(1, "http", "public.jpeg", "blah"),
            AssetVersionSize.THUMB: AssetVersion(1, "http", "public.jpeg", "blah"),
            LivePhotoVersionSize.ORIGINAL: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.MEDIUM: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
            LivePhotoVersionSize.THUMB: AssetVersion(
                1, "http", "com.apple.quicktime-movie", "blah"
            ),
        }
        _result, _overrides = disambiguate_filenames(
            _setup,
            [AssetVersionSize.ADJUSTED, AssetVersionSize.ALTERNATIVE],
            mock_photo,
            mock_lp_filename_generator,
        )

        # Should get original as both adjusted and alternative since both are missing
        self.assertEqual(len(_result), 2)
        self.assertIn(AssetVersionSize.ADJUSTED, _result)
        self.assertIn(AssetVersionSize.ALTERNATIVE, _result)
        self.assertEqual(_overrides, {})
