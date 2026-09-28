import os
import sqlite3

import huggingface_hub

from app import dbsync


class _FlakyApi:
    fail = True
    uploads = 0

    def __init__(self, token=None):
        pass

    def upload_file(self, **kw):
        if _FlakyApi.fail:
            raise OSError("network down")
        _FlakyApi.uploads += 1

    def dataset_info(self, repo):
        return type("Info", (), {"sha": "abc"})()


def test_failed_upload_is_retried(tmp_path, monkeypatch):
    db = tmp_path / "data.db"
    sqlite3.connect(db).execute("create table t(x)").connection.close()
    monkeypatch.setattr(dbsync, "REPO", "user/data")
    monkeypatch.setattr(dbsync, "TOKEN", "token")
    monkeypatch.setattr(dbsync, "_last_mtime", 0.0)
    monkeypatch.setattr(huggingface_hub, "HfApi", _FlakyApi)

    dbsync.push(str(db))
    assert dbsync._changed_locally(str(db))  # still unsynced, so the loop tries again
    _FlakyApi.fail = False
    dbsync.push(str(db))
    assert _FlakyApi.uploads == 1 and not dbsync._changed_locally(str(db))
    assert dbsync._last_mtime == os.path.getmtime(db)
