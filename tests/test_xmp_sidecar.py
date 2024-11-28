from datetime import datetime
from typing import Any, Dict
from unittest import TestCase

from foundation import version_info
from icloudpd.xmp_sidecar import XMPMetadata, build_metadata


class BuildXMPMetadata(TestCase):
    def test_build_metadata(self) -> None:
        assetRecordStub: Dict[str, Dict[str, Any]] = {
            "fields": {
                "captionEnc": {"value": "VGl0bGUgSGVyZQ==", "type": "ENCRYPTED_BYTES"},
                "extendedDescEnc": {"value": "Q2FwdGlvbiBIZXJl", "type": "ENCRYPTED_BYTES"},
                "adjustmentSimpleDataEnc": {
                    "type": "ENCRYPTED_BYTES",
                    "value": "PU67DoIwFP2XMzemBRKxo5Mummiig3G4QJEaCqS9sBD+XRDjdnLeI5xhKogJeoSjwMYfjH1VDB3LKBE/7m4LrqATGUcCrbemYWLbNtDpJFC23hHfjA9fSgkMKz42ZbsUZ72ti1PvMuOhESX7nYIAdd0/g61SG7lRqZyFkFfG0cUMdhWlQFcTLzOz01F+vmKepeLdB3bzlwD9eE4f",
                },
                "assetSubtypeV2": {"value": 2, "type": "INT64"},
                "keywordsEnc": {
                    "value": "YnBsaXN0MDChAVxzb21lIGtleXdvcmQICgAAAAAAAAEBAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAX",
                    "type": "ENCRYPTED_BYTES",
                },
                "locationEnc": {
                    "value": "YnBsaXN0MDDYAQIDBAUGBwgJCQoLCQwNCVZjb3Vyc2VVc3BlZWRTYWx0U2xvbld2ZXJ0QWNjU2xhdFl0aW1lc3RhbXBXaG9yekFjYyMAAAAAAAAAACNAdG9H6P0fpCNAWL2oZnRhiiNAMtKmTC+DezMAAAAAAAAAAAgZICYqLjY6RExVXmdwAAAAAAAAAQEAAAAAAAAADgAAAAAAAAAAAAAAAAAAAHk=",
                    "type": "ENCRYPTED_BYTES",
                },
                "assetDate": {"value": 1532951050176, "type": "TIMESTAMP"},
                "isHidden": {"value": 0, "type": "INT64"},
                "isDeleted": {"value": 0, "type": "INT64"},
                "isFavorite": {"value": 0, "type": "INT64"},
            },
        }

        # Test full metadata record
        metadata: XMPMetadata = build_metadata(assetRecordStub)
        self.assertCountEqual(
            metadata,
            XMPMetadata(
                XMPToolkit="icloudpd " + version_info.version + "+" + version_info.commit_sha,
                Title="Title Here",
                Description="Caption Here",
                Orientation=8,
                Make=None,
                DigitalSourceType=None,
                Keywords=["some keyword"],
                GPSAltitude=326.9550561797753,
                GPSLatitude=18.82285,
                GPSLongitude=98.96340333333333,
                GPSSpeed=0.0,
                GPSTimeStamp=datetime.strptime(
                    "2001:01:01 00:00:00.000000+00:00", "%Y:%m:%d %H:%M:%S.%f%z"
                ).replace(tzinfo=None),
                CreateDate=datetime.strptime(
                    "2018:07:30 11:44:10.176000+00:00", "%Y:%m:%d %H:%M:%S.%f%z"
                ),
                Rating=None,
            ),
        )

        # Test Screenshot Tagging
        assetRecordStub["fields"]["assetSubtypeV2"]["value"] = 3
        metadata = build_metadata(assetRecordStub)
        assert metadata.Make == "Screenshot"
        assert metadata.DigitalSourceType == "screenCapture"

        # Test Favorites
        assetRecordStub["fields"]["isFavorite"]["value"] = 1
        metadata = build_metadata(assetRecordStub)
        assert metadata.Rating == 5

        # Test Deleted
        assetRecordStub["fields"]["isDeleted"]["value"] = 1
        metadata = build_metadata(assetRecordStub)
        assert metadata.Rating == -1

        # Test Hidden
        assetRecordStub["fields"]["isDeleted"]["value"] = 0
        assetRecordStub["fields"]["isHidden"]["value"] = 1
        metadata = build_metadata(assetRecordStub)
        assert metadata.Rating == -1
