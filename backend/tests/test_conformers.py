import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient  # noqa: E402
from rdkit import Chem  # noqa: E402

from app import conformers, projections  # noqa: E402
from app.chem import embed_3d, mol_from_smiles  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def _mb(smi):
    return Chem.MolToMolBlock(embed_3d(mol_from_smiles(smi)))


def test_butane_scan():
    mb = _mb("CCCC")
    f, b = projections.newman_bonds(mb)[0]["atoms"]
    r = conformers.torsion_scan(mb, f, b)
    e = {p["angle"]: p["energy"] for p in r["points"]}
    assert r["labels"] == ["CH3", "CH3"]
    assert e[180] == 0.0  # anti is the global minimum
    assert 0.5 < e[60] < 1.5  # gauche
    assert 3.5 < e[0] < 7.0  # eclipsed methyl/methyl is the top
    assert e[0] > e[120] > e[60]
    assert 180 in r["minima"] and 0 in r["maxima"]


def test_scan_rejects_ring_bond():
    mb = _mb("C1CCCCC1")
    try:
        conformers.torsion_scan(mb, 0, 1)
        raise AssertionError("ring bond accepted")
    except Exception as e:  # noqa: BLE001
        assert "Ring bonds" in str(e)


def test_chair_energies():
    mb = _mb("CC1CCCCC1")
    ring = projections.chair_rings(mb)[0]
    r = conformers.chair_energies(mb, ring)
    assert len(r["chairs"]) == 2 and r["delta"] is not None
    eq = next(c for c in r["chairs"] if not c["axial"])
    ax = next(c for c in r["chairs"] if c["axial"])
    assert eq["energy"] == 0.0 and 0.8 < ax["energy"] < 3.0
    mb = _mb("CC(C)(C)C1CCCCC1")
    r = conformers.chair_energies(mb, projections.chair_rings(mb)[0])
    assert abs(r["delta"]) > 3.5  # tert-butyl locks the ring


def test_endpoints():
    with client:
        r = client.post("/api/analysis/scan", json={"smiles": "CCCC", "front": 1, "back": 2})
        assert r.status_code == 200 and len(r.json()["points"]) == 36
        r = client.post("/api/analysis/chair-energy", json={"smiles": "CC1CCCCC1", "ring": [1, 2, 3, 4, 5, 6]})
        assert r.status_code == 200 and len(r.json()["chairs"]) == 2
        assert client.post("/api/analysis/chair-energy", json={"smiles": "C1CCCCC1", "ring": [0, 1, 2, 3, 4, 5]}).status_code == 400
