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


def test_rate_limit(monkeypatch):
    monkeypatch.setattr(ratelimit, "BURST", 3)
    monkeypatch.setattr(ratelimit, "RATE", 60.0)
    ratelimit._buckets.clear()
    with client:
        codes = [client.post("/api/molecule", json={"input": "ethanol"}).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and 429 in codes[3:]


def test_rate_limit_uses_forwarded_ip(monkeypatch):
    monkeypatch.setattr(ratelimit, "BURST", 1)
    monkeypatch.setattr(ratelimit, "RATE", 60.0)
    ratelimit._buckets.clear()
    with client:
        a = client.post("/api/molecule", json={"input": "ethanol"}, headers={"x-forwarded-for": "1.1.1.1"})
        b = client.post("/api/molecule", json={"input": "ethanol"}, headers={"x-forwarded-for": "2.2.2.2"})
        c = client.post("/api/molecule", json={"input": "ethanol"}, headers={"x-forwarded-for": "1.1.1.1"})
    assert (a.status_code, b.status_code, c.status_code) == (200, 200, 429)
    assert c.headers.get("retry-after")
