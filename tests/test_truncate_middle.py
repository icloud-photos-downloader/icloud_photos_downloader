from unittest import TestCase
from icloudpd.truncate_middle import truncate_middle

class TruncateMiddleTestCase(TestCase):
    def test_truncate_middle(self):
        assert truncate_middle("test_filename.jpg", 50) == "test_filename.jpg"
        assert truncate_middle("test_filename.jpg", 17) == "test_filename.jpg"
        assert truncate_middle("test_filename.jpg", 16) == "test_f...me.jpg"
        assert truncate_middle("test_filename.jpg", 10) == "tes...jpg"
        assert truncate_middle("test_filename.jpg", 5) == "t...g"
        assert truncate_middle("test_filename.jpg", 4) == "...g"
        assert truncate_middle("test_filename.jpg", 3) == "..."
        assert truncate_middle("test_filename.jpg", 2) == ".."
        assert truncate_middle("test_filename.jpg", 1) == "."
        with self.assertRaises(ValueError):
            truncate_middle("test_filename.jpg", 0)
        with self.assertRaises(ValueError):
            truncate_middle("test_filename.jpg", -1)
