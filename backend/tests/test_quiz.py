import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def _seed():
    for n in ["ethanol", "propan-2-ol", "(2R)-butan-2-ol", "(2S)-butan-2-ol", "cyclohexanol", "2-methylpropane", "benzoic acid"]:
        assert client.post("/api/molecule", json={"input": n}).status_code == 200


def test_quiz_flow():
    with client:
        _seed()
        q = client.get("/api/quiz/question", params={"level": 1}).json()
        assert q["svg"].startswith("<?xml") and q["stereo_count"] == 0
        q3 = client.get("/api/quiz/question", params={"level": 3}).json()
        assert q3["stereo_count"] >= 1

        # find the target of q3 by trying both butanols
        r_ok = None
        for guess in ["(2R)-butan-2-ol", "(2S)-butan-2-ol"]:
            res = client.post("/api/quiz/answer", json={"id": q3["id"], "answer": guess}).json()
            if res["correct"]:
                r_ok = res
            else:
                assert res["verdict"] == "stereo"
        assert r_ok and r_ok["verdict"] == "exact" and r_ok["accepted"]

        wrong = client.post("/api/quiz/answer", json={"id": q["id"], "answer": "cholesterol"}).json()
        assert wrong["verdict"] == "wrong" and not wrong["correct"]
        bad = client.post("/api/quiz/answer", json={"id": q["id"], "answer": "asdfgh"}).json()
        assert bad["verdict"] == "unparsed"
        rev = client.post("/api/quiz/answer", json={"id": q["id"], "answer": "x", "reveal": True}).json()
        assert rev["verdict"] == "revealed" and rev["accepted"]

        ex = client.get("/api/quiz/question", params={"level": 1, "exclude": q["id"]}).json()
        assert ex["id"] != q["id"]


def test_quiz_stats_for_logged_in_user():
    with client:
        _seed()
        r = client.post("/api/auth/register", json={"username": "quizzer", "password": "password123"})
        headers = {"Authorization": f"Bearer {r.json()['token']}"}
        q = client.get("/api/quiz/question", params={"level": 1}).json()
        client.post("/api/quiz/answer", json={"id": q["id"], "answer": "x", "reveal": True}, headers=headers)
        s = client.get("/api/quiz/stats", headers=headers).json()
        assert s["total"] == 1 and s["correct"] == 0 and s["recent"][0]["inchikey"] == q["id"]


def test_draw_level_and_molfile_answer():
    from tests.test_chem import _butanol_molfile

    with client:
        _seed()
        q = client.get("/api/quiz/question", params={"level": 4}).json()
        assert q["name"] and not q["svg"]
        # answer the (R)/(S)-butanol question by drawing, if that is what came up; otherwise a wrong drawing
        res = client.post("/api/quiz/answer", json={"id": q["id"], "answer": _butanol_molfile(1)}).json()
        assert res["verdict"] in ("exact", "stereo", "wrong")
        bad = client.post("/api/quiz/answer", json={"id": q["id"], "answer": "garbage\n\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n"}).json()
        assert bad["verdict"] == "unparsed" and "structure" in bad["message"]


def test_stats_have_streak_and_names():
    with client:
        _seed()
        r = client.post("/api/auth/register", json={"username": "streaker", "password": "password123"})
        headers = {"Authorization": f"Bearer {r.json()['token']}"}
        q = client.get("/api/quiz/question", params={"level": 1}).json()
        client.post("/api/quiz/answer", json={"id": q["id"], "answer": "x", "reveal": True}, headers=headers)
        s = client.get("/api/quiz/stats", headers=headers).json()
        assert s["streak"] == 0 and s["recent"][0]["name"]
