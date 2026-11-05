import inspect
import os
from typing import Any, Dict
from unittest import TestCase, mock

from pyicloud_ipd.services.photos import PhotoLibrary
from tests.helpers import path_from_project_root, run_icloudpd_test


def empty_album_first(library: PhotoLibrary) -> Dict[str, Any]:
    empty = mock.MagicMock(
        **{
            "__len__.return_value": 0,
            "__iter__.side_effect": lambda: iter([]),
            "__str__.return_value": "Empty",
        }
    )
    return {"Empty": empty, "Library": library.all}


class OnlyPrintFilenamesAlbumsTestCase(TestCase):
    def setUp(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_only_print_filenames_goes_on_after_the_first_album(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        with mock.patch.object(PhotoLibrary, "albums", property(empty_album_first)):
            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos.yml",
                [],
                [],
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--album",
                    "Empty",
                    "--album",
                    "Library",
                    "--recent",
                    "1",
                    "--only-print-filenames",
                    "--no-progress-bar",
                ],
            )

        self.assertEqual(result.exit_code, 0)
        # the second album is listed too; before, the run ended after the first one
        self.assertEqual(
            result.output.splitlines(),
            [
                os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.JPG")),
                os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.MOV")),
            ],
        )
