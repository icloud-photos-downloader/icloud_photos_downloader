"""Assets that share one CPLMaster (e.g. created with Photos' "Duplicate") must each be yielded exactly once.

The fake server below follows what iCloud returns for CPLAssetAndMasterByAssetDate queries: a page holds up to
page_size CPLAsset records starting at startRank (which counts assets), plus each referenced CPLMaster once.
"""

from typing import Any, Dict, List
from unittest import TestCase

from pyicloud_ipd.services.photos import PhotoAlbum


def make_library(n_assets: int, shared: Dict[int, int]) -> List[Dict[str, Any]]:
    """n_assets assets in rank order; shared maps asset index -> index of the asset whose master it reuses"""
    assets = []
    for i in range(n_assets):
        master = f"M{shared.get(i, i)}"
        assets.append(
            {
                "recordType": "CPLAsset",
                "recordName": f"A{i}",
                "fields": {"masterRef": {"value": {"recordName": master}}},
            }
        )
    return assets


class FakeResponse:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload

    def json(self) -> Dict[str, Any]:
        return self.payload


class FakeAlbum(PhotoAlbum):
    def __init__(self, assets: List[Dict[str, Any]], page_size: int) -> None:
        self.assets = assets
        self.page_size = page_size
        self.offset = 0
        self.requests = 0

    def photos_request(self) -> Any:
        self.requests += 1
        page = self.assets[self.offset : self.offset + self.page_size]
        masters: List[Dict[str, Any]] = []
        seen = set()
        for a in page:
            m = a["fields"]["masterRef"]["value"]["recordName"]
            if m not in seen:
                seen.add(m)
                masters.append({"recordType": "CPLMaster", "recordName": m, "fields": {}})
        return FakeResponse({"records": masters + page})


class SharedMasterAssetsTestCase(TestCase):
    def yielded(self, n: int, shared: Dict[int, int], page_size: int) -> List[str]:
        album = FakeAlbum(make_library(n, shared), page_size)
        return [p._asset_record["recordName"] for p in album.photos]

    def test_no_shared_masters(self) -> None:
        got = self.yielded(25, {}, 10)
        self.assertEqual(got, [f"A{i}" for i in range(25)])

    def test_shared_master_inside_page(self) -> None:
        got = self.yielded(25, {4: 3, 12: 11}, 10)
        self.assertEqual(got, [f"A{i}" for i in range(25)])

    def test_shared_master_across_page_boundary(self) -> None:
        # A10 starts page 2 but its master (M9) was returned only on page 1
        got = self.yielded(25, {10: 9}, 10)
        self.assertEqual(got, [f"A{i}" for i in range(25)])

    def test_missing_master_is_skipped(self) -> None:
        album = FakeAlbum(make_library(25, {}), 10)
        original_request = album.photos_request

        def request_without_m7() -> Any:
            response = original_request()
            records = response.payload["records"]
            response.payload["records"] = [r for r in records if r["recordName"] != "M7"]
            return response

        album.photos_request = request_without_m7  # type: ignore[method-assign]
        with self.assertLogs("pyicloud_ipd.services.photos", level="WARNING") as logs:
            got = [p._asset_record["recordName"] for p in album.photos]
        self.assertEqual(got, [f"A{i}" for i in range(25) if i != 7])
        self.assertIn("Skipping asset A7: its master record M7 was not returned", logs.output[0])

    def test_three_assets_one_master(self) -> None:
        got = self.yielded(30, {5: 4, 6: 4, 20: 19}, 10)
        self.assertEqual(got, [f"A{i}" for i in range(30)])
        self.assertEqual(len(set(got)), 30)
