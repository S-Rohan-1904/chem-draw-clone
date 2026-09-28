import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import ratelimit  # noqa: E402
from app.chem import ChemError, build  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def test_too_large_rejected(monkeypatch):
    from app import chem

    monkeypatch.setattr(chem, "MAX_HEAVY_ATOMS", 5)
    with pytest.raises(ChemError, match="too large"):
        build("hexane")
    assert build("butane").smiles


def _tight(monkeypatch, limiter, burst):
    monkeypatch.setattr(limiter, "burst", burst)
    monkeypatch.setattr(limiter, "per_min", 60.0)
    limiter.reset()


def test_rate_limit(monkeypatch):
    _tight(monkeypatch, ratelimit.check, 3)
    with client:
        codes = [client.post("/api/molecule", json={"input": "ethanol"}).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and 429 in codes[3:]


def test_forwarded_for_ignored_without_trusted_proxy(monkeypatch):
    # A client can write anything into X-Forwarded-For; by default it is not
    # an address to key the limit on.
    _tight(monkeypatch, ratelimit.check, 1)
    monkeypatch.setattr(ratelimit, "TRUSTED_PROXY_HOPS", 0)
    with client:
        a = client.post("/api/molecule", json={"input": "ethanol"}, headers={"x-forwarded-for": "1.1.1.1"})
        b = client.post("/api/molecule", json={"input": "ethanol"}, headers={"x-forwarded-for": "2.2.2.2"})
    assert (a.status_code, b.status_code) == (200, 429)


def test_forwarded_for_behind_one_proxy(monkeypatch):
    # The proxy appends the real address; whatever the client sent sits to its left.
    _tight(monkeypatch, ratelimit.check, 1)
    monkeypatch.setattr(ratelimit, "TRUSTED_PROXY_HOPS", 1)
    with client:
        a = client.post("/api/molecule", json={"input": "ethanol"}, headers={"x-forwarded-for": "9.9.9.1, 1.1.1.1"})
        b = client.post("/api/molecule", json={"input": "ethanol"}, headers={"x-forwarded-for": "9.9.9.2, 1.1.1.1"})
        c = client.post("/api/molecule", json={"input": "ethanol"}, headers={"x-forwarded-for": "2.2.2.2"})
    assert (a.status_code, b.status_code, c.status_code) == (200, 429, 200)
    assert b.headers.get("retry-after")


def test_analysis_calls_charge_only_new_molecules(monkeypatch):
    _tight(monkeypatch, ratelimit.check, 2)
    with client:
        assert client.post("/api/molecule", json={"input": "propan-1-ol"}).status_code == 200
        smiles = client.post("/api/molecule", json={"input": "propan-1-ol"}).json()["smiles"]
        # Built already: the follow-up cards are free even with the bucket empty.
        assert client.post("/api/analysis/bonding", json={"smiles": smiles}).status_code == 200
        assert client.post("/api/molecule/projections", json={"smiles": smiles}).status_code == 200
        # A molecule nobody has built yet costs a token.
        assert client.post("/api/analysis/bonding", json={"smiles": "CCCCCCO"}).status_code == 429


def test_auth_limit(monkeypatch):
    _tight(monkeypatch, ratelimit.auth, 2)
    with client:
        codes = [client.post("/api/auth/login", json={"username": "nobody", "password": "password123"}).status_code for _ in range(3)]
    assert codes == [401, 401, 429]
