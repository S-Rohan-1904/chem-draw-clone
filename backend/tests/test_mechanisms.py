import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient  # noqa: E402
from rdkit import Chem  # noqa: E402

from app import mechanisms  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def test_every_step_renders_and_arrows_resolve():
    for m in mechanisms.LIBRARY:
        r = mechanisms.get_mechanism(m.id)
        assert len(r["steps"]) == len(m.steps) >= 2
        for step in r["steps"]:
            assert "<svg" in step["svg"]
            assert step["svg"].count("<path d='M") >= step["arrows"]
        assert r["steps"][-1]["arrows"] == 0  # the last step shows products only


def test_atom_maps_are_consistent_between_steps():
    """Atoms that appear in consecutive steps keep the same element."""
    for m in mechanisms.LIBRARY:
        prev: dict[int, str] = {}
        for s in m.steps:
            mol = Chem.MolFromSmiles(s.smiles, mechanisms._PARSE)
            assert mol is not None, s.smiles
            cur = {a.GetAtomMapNum(): a.GetSymbol() for a in mol.GetAtoms() if a.GetAtomMapNum()}
            for k, sym in cur.items():
                if k in prev:
                    assert prev[k] == sym, (m.id, k, prev[k], sym)
            prev = cur


def test_endpoints():
    r = client.get("/api/analysis/mechanisms")
    assert r.status_code == 200 and len(r.json()["mechanisms"]) == len(mechanisms.LIBRARY)
    r = client.get("/api/analysis/mechanisms/sn2")
    assert r.status_code == 200 and r.json()["steps"][0]["arrows"] == 2
    assert client.get("/api/analysis/mechanisms/nope").status_code == 404
