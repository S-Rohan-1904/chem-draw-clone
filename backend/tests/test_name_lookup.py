import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient  # noqa: E402

from app import resolver  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def test_name_lookup_cached_and_negative(monkeypatch):
    calls = {"n": 0}

    def fake(key):
        calls["n"] += 1
        return {"iupac": "ethanol", "title": "Ethanol", "cid": 702} if key.startswith("LFQSCWFLJHTTHZ") else None

    monkeypatch.setattr(resolver, "name_for_inchikey", fake)
    with client:
        r = client.get("/api/molecule/name/LFQSCWFLJHTTHZ-UHFFFAOYSA-N").json()
        assert r == {"found": True, "iupac": "ethanol", "title": "Ethanol", "cid": 702, "source": "PubChem"}
        client.get("/api/molecule/name/LFQSCWFLJHTTHZ-UHFFFAOYSA-N")
        assert calls["n"] == 1  # served from cache
        miss = client.get("/api/molecule/name/AAAAAAAAAAAAAA-AAAAAAAAAA-N").json()
        assert miss == {"found": False}
        client.get("/api/molecule/name/AAAAAAAAAAAAAA-AAAAAAAAAA-N")
        assert calls["n"] == 2  # negative result cached for a day


def test_invalid_key_never_hits_network(monkeypatch):
    monkeypatch.setattr(resolver, "enabled", lambda: True)
    assert resolver.name_for_inchikey("not-a-key") is None
