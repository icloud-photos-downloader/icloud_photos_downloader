from icloudpd.truncate_middle import truncate_middle

def test_truncate_middle():
    assert truncate_middle("test_filename.jpg", 50) == "test_filename.jpg"
    assert truncate_middle("test_filename.jpg", 10) == "tes...jpg"
