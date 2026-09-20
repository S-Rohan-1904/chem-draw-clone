import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient  # noqa: E402
from rdkit import Chem  # noqa: E402

from app import sugars  # noqa: E402
from app.chem import embed_3d, mol_from_smiles  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def _mb(smi):
    return Chem.MolToMolBlock(embed_3d(mol_from_smiles(smi)))


def _sides(f):
    return [(r["label"] or ((r["left"] or {}).get("text"), (r["right"] or {}).get("text"))) for r in f["rows"]]


def test_fischer_amino_acids():
    f = sugars.fischer(_mb("N[C@@H](C)C(=O)O"))
    assert f["dl"] == "L" and _sides(f) == ["COOH", ("NH2", "H"), "CH3"]
    f = sugars.fischer(_mb("N[C@H](C)C(=O)O"))
    assert f["dl"] == "D" and _sides(f) == ["COOH", ("H", "NH2"), "CH3"]
    f = sugars.fischer(_mb("C[C@@H](O)[C@H](N)C(=O)O"))  # L-threonine (2S,3R)
    assert f["dl"] == "L" and _sides(f) == ["COOH", ("NH2", "H"), ("H", "OH"), "CH3"]


def test_fischer_sugars():
    f = sugars.fischer(_mb("O=C[C@H](O)CO"))
    assert f["dl"] == "D" and _sides(f) == ["CHO", ("H", "OH"), "CH2OH"]
    f = sugars.fischer(_mb("O=C[C@H](O)[C@@H](O)[C@H](O)[C@H](O)CO"))  # D-glucose
    assert f["dl"] == "D" and _sides(f) == ["CHO", ("H", "OH"), ("OH", "H"), ("H", "OH"), ("H", "OH"), "CH2OH"]
    f = sugars.fischer(_mb("O=C[C@H](O)[C@@H](O)[C@@H](O)[C@H](O)CO"))  # D-galactose
    assert _sides(f)[3] == ("OH", "H")
    assert "<svg" in f["svg"]


def test_fischer_not_applicable():
    assert sugars.fischer(_mb("CCO")) is None
    assert sugars.fischer(_mb("C[C@H]1CCCC[C@@H]1C")) is None  # ring: no chain


def test_haworth_glucose_anomers():
    h = sugars.haworth(_mb("OC[C@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O"))  # beta-D-glucopyranose
    assert h["kind"] == "pyranose" and h["anomer"] == "beta" and h["dl"] == "D"
    ups = [next(s["up"] for s in a["subs"] if not s["h"]) for a in h["atoms"]]
    assert ups == [True, False, True, False, True]
    h = sugars.haworth(_mb("OC[C@H]1O[C@H](O)[C@H](O)[C@@H](O)[C@@H]1O"))  # alpha
    assert h["anomer"] == "alpha" and h["dl"] == "D"
    h = sugars.haworth(_mb("OC[C@@H]1O[C@@H](O)[C@@H](O)[C@H](O)[C@H]1O"))  # alpha-L
    assert h["anomer"] == "alpha" and h["dl"] == "L"


def test_haworth_furanose_and_pentose():
    h = sugars.haworth(_mb("C([C@@H]1[C@H]([C@@H]([C@](O1)(CO)O)O)O)O"))  # beta-D-fructofuranose
    assert h["kind"] == "furanose" and h["anomer"] == "beta" and h["dl"] == "D"
    assert h["atoms"][0]["label"] == 2  # ketose numbering
    h = sugars.haworth(_mb("C1[C@H]([C@@H]([C@H]([C@H](O1)O)O)O)O"))  # alpha-D-xylopyranose
    assert h["anomer"] == "alpha" and h["dl"] == "D"
    assert sugars.haworth(_mb("C1CCOC1")) is None  # no anomeric carbon
    assert sugars.haworth(_mb("c1ccccc1")) is None


def test_group_label():
    m = Chem.AddHs(Chem.MolFromSmiles("CC(C)(C)C(=O)O"))
    c = next(a for a in m.GetAtoms() if a.GetSymbol() == "C" and a.GetDegree() == 4 and all(n.GetSymbol() == "C" for n in a.GetNeighbors()))
    acid = next(n for n in c.GetNeighbors() if any(x.GetSymbol() == "O" for x in n.GetNeighbors()))
    assert sugars.group_label(acid, c.GetIdx()) == "COOH"
    assert sugars.group_label(c, acid.GetIdx()) == "C(CH3)3"


def test_endpoint():
    with client:
        r = client.post("/api/analysis/sugars", json={"smiles": "N[C@@H](C)C(=O)O"})
        assert r.status_code == 200
        body = r.json()
        assert body["fischer"]["dl"] == "L" and body["haworth"] is None
