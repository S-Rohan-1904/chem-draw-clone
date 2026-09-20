import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def _auth(u):
    r = client.post("/api/auth/register", json={"username": u, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_assignment_flow():
    with client:
        teacher = _auth("teach")
        student = _auth("stud")
        r = client.post("/api/assignments", json={"title": "Week 1", "names": ["ethanol", "nonsense name", "(2R)-butan-2-ol"]}, headers=teacher)
        assert r.status_code == 201
        body = r.json()
        code = body["assignment"]["code"]
        assert len(code) == 6 and len(body["assignment"]["items"]) == 2 and body["rejected"][0]["name"] == "nonsense name"

        # anyone can read by code
        a = client.get(f"/api/assignments/{code.lower()}").json()
        assert a["title"] == "Week 1" and a["done_count"] == 0

        item = a["items"][0]["id"]
        d = client.post(f"/api/assignments/{code}/done/{item}", headers=student).json()
        assert d["done_count"] == 1 and d["items"][0]["done"] is True
        assert client.get(f"/api/assignments/{code}/me", headers=student).json()["done_count"] == 1
        assert client.get("/api/assignments/joined", headers=student).json()[0]["code"] == code

        p = client.get(f"/api/assignments/{code}/progress", headers=teacher).json()
        assert p["participants"][0]["username"] == "stud" and p["participants"][0]["count"] == 1
        assert client.get(f"/api/assignments/{code}/progress", headers=student).status_code == 403

        u = client.delete(f"/api/assignments/{code}/done/{item}", headers=student).json()
        assert u["done_count"] == 0
        assert client.get("/api/assignments/mine", headers=teacher).json()[0]["code"] == code
        assert client.delete(f"/api/assignments/{code}", headers=student).status_code == 404
        assert client.delete(f"/api/assignments/{code}", headers=teacher).status_code == 204
        assert client.get(f"/api/assignments/{code}").status_code == 404


def test_requires_login_to_create():
    with client:
        assert client.post("/api/assignments", json={"title": "x", "names": ["ethanol"]}).status_code == 401
