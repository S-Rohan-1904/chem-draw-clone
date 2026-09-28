import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient  # noqa: E402

from app import auth as authmod  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def _auth(u, **extra):
    r = client.post("/api/auth/register", json={"username": u, "password": "password123", **extra})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_admin_names_are_reserved(monkeypatch):
    monkeypatch.setattr(authmod, "ADMIN_USERS", {"chief"})
    body = {"username": "chief", "password": "password123"}
    with client:
        monkeypatch.setattr(authmod, "ADMIN_SIGNUP_CODE", "")
        assert client.post("/api/auth/register", json={**body, "admin_code": "anything"}).status_code == 403
        monkeypatch.setattr(authmod, "ADMIN_SIGNUP_CODE", "s3cret")
        assert client.post("/api/auth/register", json=body).status_code == 403
        assert client.post("/api/auth/register", json={**body, "admin_code": "wrong"}).status_code == 403
        assert client.post("/api/auth/register", json={**body, "admin_code": "s3cret"}).status_code == 201
        assert client.post("/api/auth/register", json={"username": "someone", "password": "password123"}).status_code == 201


def test_admin_stats(monkeypatch):
    monkeypatch.setattr(authmod, "ADMIN_USERS", {"boss"})
    monkeypatch.setattr(authmod, "ADMIN_SIGNUP_CODE", "s3cret")
    with client:
        boss, pleb = _auth("boss", admin_code="s3cret"), _auth("pleb")
        assert client.get("/api/auth/me", headers=boss).json()["is_admin"] is True
        assert client.get("/api/auth/me", headers=pleb).json()["is_admin"] is False
        client.post("/api/molecule", json={"input": "ethanol"})
        client.post("/api/molecule", json={"input": "ethanol"})
        client.post("/api/molecule", json={"input": "2-metylpropane"})
        client.post("/api/molecule", json={"input": "2-metylpropane"})
        assert client.get("/api/admin/stats", headers=pleb).status_code == 403
        assert client.get("/api/admin/stats").status_code == 401
        s = client.get("/api/admin/stats", headers=boss).json()
        assert s["totals"]["users"] >= 2 and s["totals"]["molecules_cached"] >= 1
        assert s["top_failures"][0]["text"] == "2-metylpropane" and s["top_failures"][0]["count"] == 2
        assert s["top_molecules"][0]["hits"] >= 1
        assert s["new_molecules_per_day"][-1]["count"] >= 1
