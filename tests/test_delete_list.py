import datetime
import os
import tempfile
from typing import Any, Generator, List
from unittest import TestCase, mock

from icloudpd.base import (
    _assets_around,
    _first_rank_at_or_before,
    delete_from_list,
    read_delete_list,
)
from icloudpd.cli import parse
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.services.photos import apply_file_match_policy

UTC = datetime.timezone.utc
BASE = datetime.datetime(2026, 1, 1, tzinfo=UTC)


class FakeAsset:
    def __init__(self, asset_id: str, filename: str, size: int, date: datetime.datetime) -> None:
        self.id = asset_id
        self.filename = filename
        self.size = size
        self.asset_date = date


class FakeAlbum:
    """Library ordered newest first, like iCloud. Counts how many assets were pulled."""

    def __init__(self, assets: List[FakeAsset]) -> None:
        self.assets = sorted(assets, key=lambda a: a.asset_date, reverse=True)
        self.offset = 0
        self.page_size = 100
        # shared with the copies that delete_from_list makes (copy.copy keeps this same list)
        self._requests = [0]

    @property
    def requests(self) -> int:
        return self._requests[0]

    def __len__(self) -> int:
        return len(self.assets)

    def __iter__(self) -> Generator[FakeAsset, Any, None]:
        return self.photos

    @property
    def photos(self) -> Generator[FakeAsset, Any, None]:
        self._requests[0] += 1
        for asset in self.assets[self.offset :]:
            yield asset


class FakeLibrary:
    def __init__(self, album: FakeAlbum) -> None:
        self.all = album


def make_library(count: int = 500) -> FakeLibrary:
    # one asset per hour, IMG_0000 is the oldest
    assets = [
        FakeAsset(f"id{i}", f"IMG_{i:04d}.HEIC", 1000 + i, BASE + datetime.timedelta(hours=i))
        for i in range(count)
    ]
    return FakeLibrary(FakeAlbum(assets))


def write_list(content: str) -> str:
    handle, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(handle, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def unix(i: int) -> int:
    return int((BASE + datetime.timedelta(hours=i)).timestamp())


class ReadDeleteListTestCase(TestCase):
    def test_parses_name_size_and_dates(self) -> None:
        path = write_list(
            "# comment\n\nimg_1.heic\t100\t1700000000\nIMG_2.HEIC\t200\t2026-01-02T03:04:05+00:00\nIMG_3.HEIC\t300\n"
        )
        entries = read_delete_list(path)
        self.assertEqual(
            entries,
            {
                ("IMG_1.HEIC", 100): (3, 1700000000.0),
                ("IMG_2.HEIC", 200): (4, datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC).timestamp()),
                ("IMG_3.HEIC", 300): (5, None),
            },
        )

    def test_rejects_line_without_tab(self) -> None:
        with self.assertRaises(ValueError):
            read_delete_list(write_list("IMG_1.HEIC 100\n"))

    def test_rejects_non_numeric_size(self) -> None:
        with self.assertRaises(ValueError):
            read_delete_list(write_list("IMG_1.HEIC\tbig\n"))

    def test_rejects_invalid_date(self) -> None:
        with self.assertRaises(ValueError):
            read_delete_list(write_list("IMG_1.HEIC\t100\tyesterday\n"))


class DateSearchTestCase(TestCase):
    def test_first_rank_at_or_before(self) -> None:
        album = make_library(100).all
        # newest asset (i=99) is rank 0
        self.assertEqual(_first_rank_at_or_before(album, 100, unix(99)), 0)  # type: ignore[arg-type]
        self.assertEqual(_first_rank_at_or_before(album, 100, unix(50)), 49)  # type: ignore[arg-type]
        self.assertEqual(_first_rank_at_or_before(album, 100, unix(0)), 99)  # type: ignore[arg-type]
        # newer than everything -> rank 0, older than everything -> past the end
        self.assertEqual(_first_rank_at_or_before(album, 100, unix(1000)), 0)  # type: ignore[arg-type]
        self.assertEqual(_first_rank_at_or_before(album, 100, unix(0) - 10**6), 100)  # type: ignore[arg-type]

    def test_assets_around_returns_only_nearby_assets(self) -> None:
        album = make_library(200).all
        found = [a.filename for a in _assets_around(album, 200, unix(120))]  # type: ignore[arg-type]
        self.assertIn("IMG_0120.HEIC", found)
        # a handful of neighbours is fine, but nothing far from the date
        self.assertNotIn("IMG_0100.HEIC", found)
        self.assertNotIn("IMG_0140.HEIC", found)
        self.assertLess(len(found), 15)


class DeleteFromListTestCase(TestCase):
    def run_delete(
        self, library: FakeLibrary, content: str, dry_run: bool = False, max_entries: int = 50
    ) -> tuple[int, mock.Mock, mock.Mock]:
        with (
            mock.patch("icloudpd.base.delete_photo") as real,
            mock.patch("icloudpd.base.delete_photo_dry_run") as dry,
        ):
            status = delete_from_list(
                mock.Mock(),
                library,  # type: ignore[arg-type]
                write_list(content),
                max_entries,
                dry_run,
                lambda asset: asset.filename,
            )
        return status, real, dry

    def test_deletes_matching_asset_using_date_search(self) -> None:
        library = make_library(500)
        status, real, dry = self.run_delete(library, f"IMG_0250.HEIC\t1250\t{unix(250)}\n")
        self.assertEqual(status, 0)
        dry.assert_not_called()
        real.assert_called_once()
        self.assertEqual(real.call_args.args[2].id, "id250")
        # binary search + one page, far fewer requests than the 500 assets
        self.assertLess(library.all.requests, 30)

    def test_recent_entries_cost_a_single_request(self) -> None:
        library = make_library(500)
        # the two newest photos: found in the first page, no binary search at all
        content = f"IMG_0499.HEIC\t1499\t{unix(499)}\nIMG_0497.HEIC\t1497\t{unix(497)}\n"
        status, real, _ = self.run_delete(library, content)
        self.assertEqual(status, 0)
        self.assertEqual(real.call_count, 2)
        self.assertEqual(library.all.requests, 1)

    def test_old_entries_share_lookups(self) -> None:
        library = make_library(2000)
        content = f"IMG_0100.HEIC\t1100\t{unix(100)}\nIMG_0102.HEIC\t1102\t{unix(102)}\n"
        status, real, _ = self.run_delete(library, content)
        self.assertEqual(status, 0)
        self.assertEqual(real.call_count, 2)
        one = make_library(2000)
        self.run_delete(one, f"IMG_0100.HEIC\t1100\t{unix(100)}\n")
        # the second entry costs far less than the first because positions are remembered
        self.assertLess(library.all.requests, one.all.requests + 6)

    def test_dry_run_does_not_delete(self) -> None:
        status, real, dry = self.run_delete(
            make_library(50), f"IMG_0010.HEIC\t1010\t{unix(10)}\n", dry_run=True
        )
        self.assertEqual(status, 0)
        real.assert_not_called()
        dry.assert_called_once()

    def test_name_or_size_mismatch_deletes_nothing(self) -> None:
        # wrong size, and wrong name for an existing size
        for content in (
            f"IMG_0010.HEIC\t9999\t{unix(10)}\n",
            f"IMG_9999.HEIC\t1010\t{unix(10)}\n",
        ):
            status, real, dry = self.run_delete(make_library(50), content)
            self.assertEqual(status, 0)
            real.assert_not_called()
            dry.assert_not_called()

    def test_entry_without_date_scans_whole_library(self) -> None:
        status, real, _ = self.run_delete(make_library(300), "img_0007.heic\t1007\n")
        self.assertEqual(status, 0)
        real.assert_called_once()
        self.assertEqual(real.call_args.args[2].id, "id7")

    def test_matches_name_id7_filenames(self) -> None:
        library = make_library(50)
        asset = library.all.assets[0]
        id7_name = apply_file_match_policy(FileMatchPolicy.NAME_ID7, asset.id)(asset.filename)
        status, real, _ = self.run_delete(library, f"{id7_name}\t{asset.size}\t{int(asset.asset_date.timestamp())}\n")
        self.assertEqual(status, 0)
        real.assert_called_once()
        self.assertEqual(real.call_args.args[2].id, asset.id)

    def test_ambiguous_match_is_skipped_and_reported(self) -> None:
        library = make_library(20)
        twin = FakeAsset("twin", "IMG_0005.HEIC", 1005, BASE + datetime.timedelta(hours=5, seconds=30))
        library.all.assets.append(twin)
        library.all.assets.sort(key=lambda a: a.asset_date, reverse=True)
        status, real, _ = self.run_delete(library, f"IMG_0005.HEIC\t1005\t{unix(5)}\n")
        self.assertEqual(status, 1)
        real.assert_not_called()

    def test_refuses_list_longer_than_max(self) -> None:
        content = "".join(f"IMG_{i:04d}.HEIC\t{1000 + i}\t{unix(i)}\n" for i in range(3))
        status, real, dry = self.run_delete(make_library(10), content, max_entries=2)
        self.assertEqual(status, 1)
        real.assert_not_called()
        dry.assert_not_called()

    def test_empty_list_is_a_noop(self) -> None:
        status, real, dry = self.run_delete(make_library(10), "# nothing\n")
        self.assertEqual(status, 0)
        real.assert_not_called()
        dry.assert_not_called()


class DeleteListCliTestCase(TestCase):
    def test_defaults(self) -> None:
        _, users = parse(["-d", "/x", "-u", "a@b.c"])
        self.assertIsNone(users[0].delete_list)
        self.assertEqual(users[0].delete_list_max, 50)

    def test_options_are_parsed(self) -> None:
        _, users = parse(
            ["-d", "/x", "-u", "a@b.c", "--delete-list", "/tmp/l.txt", "--delete-list-max", "5"]
        )
        self.assertEqual(str(users[0].delete_list), "/tmp/l.txt")
        self.assertEqual(users[0].delete_list_max, 5)
