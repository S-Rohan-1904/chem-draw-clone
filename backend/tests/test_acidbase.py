import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient  # noqa: E402

from app import acidbase, isotopes  # noqa: E402
from app.chem import mol_from_smiles  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def _groups(smi):
    return [(s["group"], s["kind"]) for s in acidbase.sites(mol_from_smiles(smi))]


def test_sites():
    assert _groups("CC(=O)O") == [("Carboxylic acid", "acid")]
    assert _groups("CCN") == [("Primary amine", "base")]
    assert _groups("CC(=O)N") == []  # amide N is not basic, N-H not acidic in water
    assert ("Aniline", "base") in _groups("Nc1ccccc1")
    assert ("Pyridine", "base") in _groups("c1ccncc1")
    assert ("Phenol", "acid") in _groups("Oc1ccccc1")
    assert ("Alcohol", "acid") in _groups("CCO")
    ala = _groups("N[C@@H](C)C(=O)O")
    assert ("Alpha-amino acid, carboxyl", "acid") in ala and ("Alpha-amino acid, amino", "base") in ala


def test_ionisation_and_pi():
    r = acidbase.analyse("N[C@@H](C)C(=O)O", 7.4)
    assert r["species_smiles"] == "C[C@H]([NH3+])C(=O)[O-]"
    assert abs(r["net_charge"]) < 0.05
    assert 5.5 < r["pi"] < 6.5
    low = acidbase.analyse("N[C@@H](C)C(=O)O", 1.0)
    assert low["species_charge"] == 1
    high = acidbase.analyse("N[C@@H](C)C(=O)O", 12.0)
    assert high["species_charge"] == -1
    acid = acidbase.analyse("CC(=O)O", 2.0)
    assert acid["species_charge"] == 0 and acid["sites"][0]["fraction_ionised"] < 0.01
    assert acidbase.analyse("CCO", 7.4)["pi"] is None


def test_isotopes():
    r = isotopes.apply_labels("CCO", [{"atom_idx": 0, "isotope": "2H", "count": 3}, {"atom_idx": 1, "isotope": "13C"}])
    assert r["nominal_shift"] == 4 and abs(r["shift"] - 4.0222) < 0.001
    assert r["formula"] == "C[13C]H3D3O"
    assert "[13CH2]" in r["smiles"] and r["smiles"].count("[2H]") == 3
    try:
        isotopes.apply_labels("CCO", [{"atom_idx": 2, "isotope": "13C"}])
        raise AssertionError("13C on oxygen should fail")
    except Exception as e:  # noqa: BLE001
        assert "cannot label" in str(e)


def test_endpoints():
    with client:
        r = client.post("/api/analysis/acidbase", json={"smiles": "CC(=O)O", "ph": 7.4})
        assert r.status_code == 200 and r.json()["species_charge"] == -1
        r = client.post("/api/analysis/isotopes", json={"smiles": "CCO", "labels": [{"atom_idx": 2, "isotope": "18O"}]})
        assert r.status_code == 200
        body = r.json()
        assert body["nominal_shift"] == 2 and body["options"][0]["codes"][0] == "2H"
        assert client.post("/api/analysis/isotopes", json={"smiles": "CCO", "labels": [{"atom_idx": 9, "isotope": "18O"}]}).status_code == 400
