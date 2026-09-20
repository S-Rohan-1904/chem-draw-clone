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

        # students see structures, not names, until they answer correctly
        seen = client.get(f"/api/assignments/{code}/me", headers=student).json()
        assert seen["items"][0]["name"] == "" and seen["items"][0]["svg"].startswith("<?xml")
        assert "(R)" not in seen["items"][1]["svg"]  # stereo labels hidden until solved
        item = seen["items"][0]["id"]
        wrong = client.post(f"/api/assignments/{code}/answer/{item}", json={"answer": "cholesterol", "attempt": 1}, headers=student).json()
        assert not wrong["correct"] and wrong["assignment"]["done_count"] == 0
        right = client.post(f"/api/assignments/{code}/answer/{item}", json={"answer": "ethanol", "attempt": 2}, headers=student).json()
        assert right["correct"] and right["assignment"]["done_count"] == 1
        assert right["assignment"]["items"][0]["name"] == "ethanol" and right["assignment"]["items"][0]["attempts"] == 2
        assert client.get("/api/assignments/joined", headers=student).json()[0]["code"] == code

        p = client.get(f"/api/assignments/{code}/progress", headers=teacher).json()
        assert p["participants"][0]["username"] == "stud" and p["participants"][0]["count"] == 1
        assert p["participants"][0]["attempts"][str(item)] == 2
        assert client.get(f"/api/assignments/{code}/progress", headers=student).status_code == 403
        # owner sees names
        assert client.get(f"/api/assignments/{code}/me", headers=teacher).json()["items"][1]["name"] == "(2R)-butan-2-ol"
        assert client.get("/api/assignments/mine", headers=teacher).json()[0]["code"] == code
        assert client.delete(f"/api/assignments/{code}", headers=student).status_code == 404
        assert client.delete(f"/api/assignments/{code}", headers=teacher).status_code == 204
        assert client.get(f"/api/assignments/{code}").status_code == 404


def test_requires_login_to_create():
    with client:
        assert client.post("/api/assignments", json={"title": "x", "names": ["ethanol"]}).status_code == 401
