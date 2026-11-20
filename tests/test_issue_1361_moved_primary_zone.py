"""Test for issue #1361: ZONE_NOT_FOUND on accounts whose library moved to another zone

https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/1361

On some accounts Apple moved the primary photo library from the PrimarySync zone to a zone such
as PrimarySync1, and PrimarySync no longer exists. Based on the zone discovery in #1367 by
Tural Ali.
"""

import json
from typing import Any, Dict, List
from unittest import TestCase, mock

from pyicloud_ipd.exceptions import PyiCloudServiceNotActivatedException
from pyicloud_ipd.services.photos import PhotosService
from tests.helpers import run_main

ROOT = "https://example.com"
PRIVATE = f"{ROOT}/database/1/com.apple.photos.cloud/production/private"


def zone(name: str) -> Dict[str, Any]:
    return {"zoneName": name, "ownerRecordName": "_owner", "zoneType": "REGULAR_CUSTOM_ZONE"}


def finished() -> Dict[str, Any]:
    return {
        "records": [
            {
                "recordType": "CheckIndexingState",
                "fields": {"state": {"value": "FINISHED", "type": "STRING"}},
            }
        ]
    }


class FakeICloud:
    """Answers the indexing state query per zone, and zones/list with the given entries"""

    def __init__(
        self,
        existing_zones: List[str],
        zones_list: List[Dict[str, Any]] | Exception,
        error_code: str = "ZONE_NOT_FOUND",
    ):
        self.existing_zones = existing_zones
        self.zones_list = zones_list
        self.error_code = error_code
        self.urls: List[str] = []
        self.session = mock.MagicMock()
        self.session.post.side_effect = self.post

    def post(self, url: str, data: str = "", **_: Any) -> Any:
        self.urls.append(url)
        if url.endswith("/zones/list"):
            if isinstance(self.zones_list, Exception):
                raise self.zones_list
            return mock.MagicMock(**{"json.return_value": {"zones": self.zones_list}})
        zone_name = json.loads(data)["zoneID"]["zoneName"]
        if zone_name not in self.existing_zones:
            raise PyiCloudServiceNotActivatedException(
                "Apple iCloud setup is not complete", self.error_code
            )
        return mock.MagicMock(**{"json.return_value": finished()})

    def photos(self) -> PhotosService:
        return PhotosService(ROOT, self.session, {})

    def zones_list_calls(self) -> int:
        return sum(1 for url in self.urls if url.endswith("/zones/list"))


class Issue1361MovedPrimaryZoneTest(TestCase):
    def test_primary_sync_is_used_without_listing_zones(self) -> None:
        icloud = FakeICloud(["PrimarySync"], [{"zoneID": zone("PrimarySync1")}])

        photos = icloud.photos()

        self.assertEqual(photos.zone_id, {"zoneName": "PrimarySync"})
        self.assertEqual(icloud.zones_list_calls(), 0)

    def test_moved_zone_is_used_when_primary_sync_does_not_exist(self) -> None:
        icloud = FakeICloud(
            ["PrimarySync1"],
            [{"zoneID": zone("CMM-shared-zone")}, {"zoneID": zone("PrimarySync1")}],
        )

        with self.assertLogs("pyicloud_ipd.services.photos", level="INFO") as logs:
            photos = icloud.photos()

        self.assertEqual(photos.zone_id, zone("PrimarySync1"))
        self.assertIn("using photo library zone PrimarySync1", "\n".join(logs.output))

    def test_deleted_and_failed_zones_are_skipped(self) -> None:
        icloud = FakeICloud(
            ["PrimarySync2"],
            [
                {"zoneID": zone("PrimarySync1"), "deleted": True},
                {
                    "zoneID": zone("PrimarySync1"),
                    "reason": "Zone Fetch Error",
                    "serverErrorCode": "INTERNAL_ERROR",
                },
                {"zoneID": zone("PrimarySync2")},
            ],
        )

        photos = icloud.photos()

        self.assertEqual(photos.zone_id, zone("PrimarySync2"))

    def test_zone_not_found_stays_when_no_other_primary_zone_exists(self) -> None:
        icloud = FakeICloud([], [{"zoneID": zone("CMM-shared-zone")}])

        with self.assertRaises(PyiCloudServiceNotActivatedException) as raised:
            icloud.photos()

        self.assertEqual(raised.exception.code, "ZONE_NOT_FOUND")

    def test_zone_not_found_stays_when_the_zone_list_fails(self) -> None:
        icloud = FakeICloud([], ValueError("not JSON"))

        with self.assertRaises(PyiCloudServiceNotActivatedException) as raised:
            icloud.photos()

        self.assertEqual(raised.exception.code, "ZONE_NOT_FOUND")

    def test_other_errors_are_not_retried(self) -> None:
        icloud = FakeICloud([], [{"zoneID": zone("PrimarySync1")}], "AUTHENTICATION_FAILED")

        with self.assertRaises(PyiCloudServiceNotActivatedException) as raised:
            icloud.photos()

        self.assertEqual(raised.exception.code, "AUTHENTICATION_FAILED")
        self.assertEqual(icloud.zones_list_calls(), 0)

    def test_moved_zone_is_listed_as_the_primary_library(self) -> None:
        icloud = FakeICloud(["PrimarySync1"], [{"zoneID": zone("PrimarySync1")}])
        photos = icloud.photos()
        queries_before = len(icloud.urls)

        libraries = photos.private_libraries

        self.assertIs(libraries["PrimarySync1"], photos)
        # only the zone list, no second indexing state check of the same zone
        self.assertEqual(len(icloud.urls), queries_before + 1)

    def test_default_library_is_the_moved_zone(self) -> None:
        """The default --library PrimarySync selects the primary library (#1361)"""
        photos = mock.MagicMock()
        photos.private_libraries = {"PrimarySync1": photos}
        photos.shared_libraries = {}
        photos.albums.values.return_value = ["Favorites"]
        icloud = mock.MagicMock(photos=photos)

        with mock.patch("icloudpd.base.authenticator", return_value=icloud):
            result = run_main(
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--list-albums",
                    "--no-progress-bar",
                ]
            )

        self.assertNotIn("Unknown library", result.output)
        self.assertIn("Favorites", result.output)
        self.assertEqual(result.exit_code, 0)
