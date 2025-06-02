import datetime
import random
import string
from unittest import TestCase

from icloudpd.string_helpers import parse_timestamp_or_timedelta, truncate_middle


class TruncateMiddleTestCase(TestCase):
    def test_truncate_middle(self) -> None:
        assert truncate_middle("test_filename.jpg", 50) == "test_filename.jpg"
        assert truncate_middle("test_filename.jpg", 17) == "test_filename.jpg"
        assert truncate_middle("test_filename.jpg", 16) == "test_f...me.jpg"
        assert truncate_middle("test_filename.jpg", 10) == "tes...jpg"
        assert truncate_middle("test_filename.jpg", 5) == "t...g"
        assert truncate_middle("test_filename.jpg", 4) == "...g"
        assert truncate_middle("test_filename.jpg", 3) == "..."
        assert truncate_middle("test_filename.jpg", 2) == ".."
        assert truncate_middle("test_filename.jpg", 1) == "."
        assert truncate_middle("test_filename.jpg", 0) == ""
        with self.assertRaises(ValueError):
            truncate_middle("test_filename.jpg", -1)


class ParseTimestampeOrTimeDeltaTestCase(TestCase):
    def test_totality(self) -> None:
        characters = string.ascii_letters + string.digits
        for _case in range(500):
            target_length = random.randint(0, 100)
            target_string = "".join(random.choice(characters) for i in range(target_length))
            _result = parse_timestamp_or_timedelta(target_string)
            #  not throwing is okay

    def test_naive(self) -> None:
        assert parse_timestamp_or_timedelta("2025-01-02T03:04:05.0006") == datetime.datetime(
            2025, 1, 2, 3, 4, 5, 600
        )

    def test_aware(self) -> None:
        assert parse_timestamp_or_timedelta("2025-01-02T03:04:05.0006Z") == datetime.datetime(
            2025, 1, 2, 3, 4, 5, 600, datetime.timezone.utc
        )

    def test_aware_8(self) -> None:
        assert parse_timestamp_or_timedelta("2025-01-02T03:04:05.0006+0800") == datetime.datetime(
            2025, 1, 2, 3, 4, 5, 600, datetime.timezone(datetime.timedelta(hours=8))
        )

    def test_timestamp_invalid(self) -> None:
        assert isinstance(parse_timestamp_or_timedelta("2025-01"), ValueError)

    def test_delta_totality(self) -> None:
        digits = string.digits
        characters = ["d", "D"]
        for _case in range(500):
            target_length = random.randint(1, 5)
            target_string = "".join(
                random.choice(digits) for i in range(target_length)
            ) + random.choice(characters)
            result = parse_timestamp_or_timedelta(target_string)
            assert isinstance(result, datetime.timedelta)

    def test_delta(self) -> None:
        assert parse_timestamp_or_timedelta("1d") == datetime.timedelta(days=1)
        assert parse_timestamp_or_timedelta("0d") == datetime.timedelta(days=0)

    def test_delta_invalid(self) -> None:
        assert isinstance(parse_timestamp_or_timedelta("-1d"), ValueError)
