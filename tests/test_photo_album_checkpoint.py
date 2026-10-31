import json

from pyicloud_ipd.services.photos import PhotoAlbum


def test_photo_album_checkpoint_restores_and_updates_offset(tmp_path, monkeypatch):
    monkeypatch.setenv("ICLOUDPD_CHECKPOINT_DIR", str(tmp_path))
    kwargs = {
        "params": {},
        "session": object(),
        "service_endpoint": "https://example.test/photos",
        "name": "",
        "list_type": "CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted",
        "obj_type": "CPLAssetByAssetDateWithoutHiddenOrDeleted",
        "zone_id": {"zoneName": "PrimarySync"},
    }

    album = PhotoAlbum(**kwargs)
    album.increment_offset(100)
    checkpoint = next(tmp_path.glob("*.json"))
    assert json.loads(checkpoint.read_text()) == {"offset": 100}

    resumed = PhotoAlbum(**kwargs)
    assert resumed.offset == 100
