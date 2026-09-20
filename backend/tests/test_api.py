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
