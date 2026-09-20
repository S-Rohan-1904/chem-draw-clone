import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.worksheet import build_pdf  # noqa: E402

client = TestClient(app)


def test_pdf_pages():
    items = [{"name": f"mol {i}", "smiles": "CCO"} for i in range(9)]
    pdf = build_pdf("Test", items, show_names=False, answer_key=True)
    assert pdf.startswith(b"%PDF") and pdf.count(b"/Type /Page\n") >= 3  # 2 grid pages + key
    with_names = build_pdf("Test", items[:2], show_names=True, answer_key=True)
    assert with_names.count(b"/Type /Page\n") == 1  # no key page when names are shown


def test_endpoint():
    with client:
        r = client.post("/api/worksheet", json={"title": "W", "items": [{"name": "ethanol", "smiles": "CCO"}]})
        assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
        assert client.post("/api/worksheet", json={"title": "W", "items": [{"name": "x", "smiles": "xx"}]}).status_code == 400
