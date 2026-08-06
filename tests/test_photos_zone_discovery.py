import unittest
from unittest.mock import Mock

from pyicloud_ipd.exceptions import PyiCloudServiceNotActivatedException
from pyicloud_ipd.services.photos import PhotosService


def response(payload: dict) -> Mock:
    result = Mock()
    result.json.return_value = payload
    return result


class PhotosZoneDiscoveryTestCase(unittest.TestCase):
    def test_uses_discovered_primary_zone(self) -> None:
        session = Mock()
        primary_zone = {"zoneName": "PrimarySync1", "ownerRecordName": "owner"}
        session.post.side_effect = [
            response({"zones": [{"zoneID": primary_zone}]}),
            response(
                {"records": [{"fields": {"state": {"value": "FINISHED"}}}]}
            ),
        ]

        photos = PhotosService("https://example.invalid", session, {})

        self.assertEqual(photos.zone_id, primary_zone)
        self.assertEqual(session.post.call_args_list[0].args[0], (
            "https://example.invalid/database/1/com.apple.photos.cloud/"
            "production/private/zones/list"
        ))

    def test_rejects_accounts_without_primary_zone(self) -> None:
        session = Mock()
        session.post.return_value = response(
            {"zones": [{"zoneID": {"zoneName": "OtherZone"}}]}
        )

        with self.assertRaises(PyiCloudServiceNotActivatedException):
            PhotosService("https://example.invalid", session, {})
