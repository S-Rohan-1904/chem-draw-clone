import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def _auth(username="alice", password="password123"):
    r = client.post("/api/auth/register", json={"username": username, "password": password})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_molecule_endpoint():
    with client:
        r = client.post("/api/molecule", json={"input": "(2E)-but-2-ene"})
        assert r.status_code == 200
        body = r.json()
        assert body["stereo"]["double_bonds"][0]["label"] == "E"
        assert body["stereo"]["unspecified"] is False
        assert body["svg"].startswith("<?xml") or "<svg" in body["svg"]

        r = client.post("/api/molecule", json={"input": "nonsense"})
        assert r.status_code == 400


def test_png_endpoint():
    with client:
        r = client.post("/api/molecule/png", json={"smiles": "C[C@H](N)C(=O)O", "width": 400})
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"


def test_auth_and_saved_flow():
    with client:
        headers = _auth()
        assert client.get("/api/auth/me", headers=headers).json()["username"] == "alice"
        assert client.post("/api/auth/register", json={"username": "alice", "password": "password123"}).status_code == 409
        assert client.post("/api/auth/login", json={"username": "alice", "password": "wrongpass1"}).status_code == 401
        assert client.get("/api/saved").status_code == 401

        r = client.post(
            "/api/saved",
            json={"label": "L-alanine", "input_text": "(S)-alanine", "smiles": "N[C@@H](C)C(=O)O"},
            headers=headers,
        )
        assert r.status_code == 201
        item_id = r.json()["id"]
        assert [s["id"] for s in client.get("/api/saved", headers=headers).json()] == [item_id]

        other = _auth("bob")
        assert client.get("/api/saved", headers=other).json() == []
        assert client.delete(f"/api/saved/{item_id}", headers=other).status_code == 404
        assert client.delete(f"/api/saved/{item_id}", headers=headers).status_code == 204
        assert client.get("/api/saved", headers=headers).json() == []


def test_molecule_cache_hit_and_shared_smiles():
    with client:
        first = client.post("/api/molecule", json={"input": "(2R)-butan-2-ol"}).json()
        assert first["cached"] is False
        second = client.post("/api/molecule", json={"input": "  (2r)-BUTAN-2-ol "}).json()
        assert second["cached"] is True
        assert second["molblock"] == first["molblock"]
        assert second["input_text"] == "(2r)-BUTAN-2-ol"
        # Same molecule via SMILES reuses the molecule-level entry.
        via_smiles = client.post("/api/molecule", json={"input": first["smiles"]}).json()
        assert via_smiles["cached"] is True and via_smiles["source"] == "smiles"
        # Failures are not cached.
        assert client.post("/api/molecule", json={"input": "nonsense"}).status_code == 400
        assert client.post("/api/molecule", json={"input": "nonsense"}).status_code == 400


def test_molfile_input_via_api():
    from tests.test_chem import _butanol_molfile

    with client:
        first = client.post("/api/molecule", json={"input": _butanol_molfile(1)}).json()
        assert first["source"] == "molfile" and first["stereo"]["centers"][0]["label"] in ("R", "S")
        assert first["input_text"] == first["smiles"]
        second = client.post("/api/molecule", json={"input": _butanol_molfile(1)}).json()
        assert second["cached"] is True


def test_dbsync_snapshot_is_consistent_copy(tmp_path):
    import sqlite3

    from app import dbsync

    db = tmp_path / "x.db"
    con = sqlite3.connect(db)
    con.execute("create table t(a)")
    con.execute("insert into t values (1)")
    con.commit()
    snap = dbsync._snapshot(str(db))
    try:
        assert sqlite3.connect(snap).execute("select a from t").fetchall() == [(1,)]
    finally:
        os.unlink(snap)
    assert not dbsync.enabled()  # no HF env in tests


def test_dbsync_race_handling(tmp_path, monkeypatch):
    """New instance re-pulls a newer remote copy while untouched, and never
    overwrites the remote with an unchanged local file on shutdown."""
    import sqlite3

    from app import dbsync

    remote = {"sha": "a", "blob": None}
    calls = {"upload": 0}

    def fake_download(repo, name, repo_type, token, revision=None):
        p = tmp_path / f"remote-{remote['sha']}.db"
        p.write_bytes(remote["blob"])
        return str(p)

    class FakeApi:
        def __init__(self, token=None): ...
        def dataset_info(self, repo):
            return type("I", (), {"sha": remote["sha"]})()
        def create_repo(self, *a, **k): ...
        def upload_file(self, path_or_fileobj, **k):
            calls["upload"] += 1
            remote["blob"] = open(path_or_fileobj, "rb").read()
            remote["sha"] = remote["sha"] + "x"

    import huggingface_hub
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", fake_download)
    monkeypatch.setattr(huggingface_hub, "HfApi", FakeApi)
    monkeypatch.setattr(dbsync, "REPO", "u/r")
    monkeypatch.setattr(dbsync, "TOKEN", "t")

    # remote v1: table with one row
    v1 = tmp_path / "v1.db"
    c = sqlite3.connect(v1); c.execute("create table t(a)"); c.execute("insert into t values (1)"); c.commit(); c.close()
    remote["blob"] = v1.read_bytes()

    local = tmp_path / "local.db"
    dbsync.pull(str(local))
    assert sqlite3.connect(local).execute("select count(*) from t").fetchone()[0] == 1
    assert not dbsync._changed_locally(str(local))

    # old instance uploads v2 after we started; we are untouched, so adopt it
    v2 = tmp_path / "v2.db"
    c = sqlite3.connect(v2); c.execute("create table t(a)"); c.execute("insert into t values (1)"); c.execute("insert into t values (2)"); c.commit(); c.close()
    remote["blob"] = v2.read_bytes(); remote["sha"] = "b"
    assert dbsync._remote_revision() != dbsync._remote_sha
    dbsync.pull(str(local))
    assert sqlite3.connect(local).execute("select count(*) from t").fetchone()[0] == 2

    # unchanged local: shutdown must not upload
    dbsync._stop.clear()
    dbsync.stop(str(local))
    assert calls["upload"] == 0

    # changed local: shutdown uploads
    c = sqlite3.connect(local); c.execute("insert into t values (3)"); c.commit(); c.close()
    os.utime(local, None)
    dbsync.stop(str(local))
    assert calls["upload"] == 1


def test_share_link_lookup():
    with client:
        built = client.post("/api/molecule", json={"input": "(2S)-butan-2-ol"}).json()
        r = client.get(f"/api/molecule/by-key/{built['inchikey']}")
        assert r.status_code == 200 and r.json()["smiles"] == built["smiles"]
        assert client.get("/api/molecule/by-key/XXXXXXXXXXXXXXXXXXXXXXXXXX-N").status_code == 404


def test_missing_column_migration(tmp_path):
    import sqlite3

    from sqlalchemy import create_engine, inspect

    from app import db as dbmod

    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("create table molecule_cache(smiles varchar primary key, result_json text, hits integer, created_at datetime, last_used_at datetime)")
    con.commit(); con.close()
    old_engine = dbmod.engine
    dbmod.engine = create_engine(f"sqlite:///{path}")
    try:
        dbmod.init_db()
        cols = {c["name"] for c in inspect(dbmod.engine).get_columns("molecule_cache")}
        assert "inchikey" in cols
    finally:
        dbmod.engine = old_engine


def test_prewarm_import(tmp_path):
    import json
    import sqlite3

    from app import db as dbmod

    pre = tmp_path / "pre.db"
    con = sqlite3.connect(pre)
    con.execute("create table name_cache(key varchar primary key, smiles text, source varchar, warning text, normalised text, created_at datetime)")
    con.execute("create table molecule_cache(smiles varchar primary key, result_json text, inchikey varchar, hits integer, created_at datetime, last_used_at datetime)")
    con.execute("insert into name_cache values ('prewarmed-name', 'CCO', 'iupac', '', 'prewarmed-name', '2026-01-01')")
    con.execute("insert into molecule_cache values ('CCO', ?, 'LFQSCWFLJHTTHZ-UHFFFAOYSA-N', 0, '2026-01-01', '2026-01-01')", (json.dumps({"inchikey": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N", "smiles": "CCO"}),))
    con.commit(); con.close()
    with client:
        added = dbmod.import_prewarm(str(pre))
        assert added >= 1
        assert dbmod.import_prewarm(str(pre)) == 0  # idempotent
        with dbmod.SessionLocal() as s:
            assert s.get(dbmod.NameCache, "prewarmed-name") is not None


def test_stale_cache_rows_are_rebuilt():
    import json

    from app import db as dbmod

    with client:
        first = client.post("/api/molecule", json={"input": "propan-2-ol"}).json()
        with dbmod.SessionLocal() as s:
            row = s.get(dbmod.MoleculeCache, first["smiles"])
            old = json.loads(row.result_json)
            old.pop("groups"); old["_v"] = 1
            row.result_json = json.dumps(old); s.commit()
        again = client.post("/api/molecule", json={"input": "propan-2-ol"}).json()
        assert again["cached"] is False and "groups" in again
        assert client.post("/api/molecule", json={"input": "propan-2-ol"}).json()["cached"] is True
