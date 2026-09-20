import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient  # noqa: E402

from app import transforms  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def _products(smi, name):
    r = transforms.predict_products(smi)
    rx = next((x for x in r["reactions"] if x["name"] == name), None)
    assert rx is not None, f"{name} not offered for {smi}"
    return [p["smiles"] for p in rx["products"]]


def test_markovnikov_and_anti():
    assert _products("CC=C", "Hydrohalogenation (Markovnikov)") == [["CC(C)Br"]]
    assert _products("CC=C", "Hydrobromination with peroxides (anti-Markovnikov)") == [["CCCBr"]]
    assert _products("CC(C)=C", "Acid-catalysed hydration (Markovnikov)") == [["CC(C)(C)O"]]
    assert _products("CC(C)=C", "Hydroboration-oxidation (anti-Markovnikov)") == [["CC(C)CO"]]


def test_zaitsev_and_hofmann():
    assert _products("CCC(C)Br", "Dehydrohalogenation (Zaitsev)") == [["CC=CC"]]
    assert _products("CCC(C)Br", "Dehydrohalogenation (Hofmann)") == [["C=CCC"]]


def test_aromatic_directing():
    phenol = _products("Oc1ccccc1", "Nitration")
    assert sorted(p[0] for p in phenol) == sorted(["O=[N+]([O-])c1ccccc1O", "O=[N+]([O-])c1ccc(O)cc1"])
    nitro = _products("O=[N+]([O-])c1ccccc1", "Bromination of the ring")
    assert nitro == [["O=[N+]([O-])c1cccc(Br)c1"]]


def test_oxidations_and_carbonyls():
    assert _products("CCO", "Oxidation of a primary alcohol to an aldehyde") == [["CC=O"]]
    assert _products("CC(O)C", "Oxidation of a secondary alcohol to a ketone") == [["CC(C)=O"]]
    assert _products("CC(C)=O", "Reduction of an aldehyde or ketone") == [["CC(C)O"]]
    assert _products("CC(C)=O", "Wolff-Kishner reduction") == [["CCC"]]
    assert _products("CC(=O)OC", "Ester hydrolysis") == [["CC(=O)O", "CO"]]
    assert _products("C=CC=C", "Ozonolysis") == [["C=O", "C=CC=O"]]
    names = {x["name"] for x in transforms.predict_products("CC(=O)O")["reactions"]}
    assert "Reduction of an aldehyde or ketone" not in names  # acids are excluded


def test_retrosynthesis():
    r = transforms.retrosynthesis("CC(O)CC")
    by = {x["name"]: [p["smiles"] for p in x["precursors"]] for x in r["routes"]}
    assert [["CCC(C)=O"]] == by["Reduction of a carbonyl"]
    assert sorted(p[0] for p in by["Hydration of an alkene"]) == ["C=CCC", "CC=CC"]
    from rdkit import Chem

    enol = Chem.MolFromSmarts("C=C[OH]")
    for p in by.get("Hydrogenation of an alkene", []):
        assert not Chem.MolFromSmiles(p[0]).HasSubstructMatch(enol)
    r = transforms.retrosynthesis("C1CC=CCC1")
    da = next(x for x in r["routes"] if x["name"] == "Diels-Alder")
    assert [p["smiles"] for p in da["precursors"]] == [["C=CC=C", "C=C"]]
    ester = transforms.retrosynthesis("CCOC(C)=O")
    assert "Williamson ether synthesis" not in {x["name"] for x in ester["routes"]}


def test_classify():
    c = transforms.classify(["CC(C)(C)Br"], ["CC(C)(C)O"])
    assert c["matches"][0]["name"] == "Substitution by hydroxide" and "SN1" in c["matches"][0]["mechanism_note"]
    c = transforms.classify(["CC=C"], ["CC(C)Br"])
    assert c["matches"][0]["name"].startswith("Hydrohalogenation")
    c = transforms.classify(["CC(=O)O", "CCO"], ["CC(=O)OCC"])
    assert not c["matches"] and "esterification" in c["guess"]
    c = transforms.classify(["C=CC=C", "C=C"], ["C1CC=CCC1"])
    assert c["matches"][0]["name"].startswith("Diels-Alder")


def test_endpoints():
    with client:
        assert client.post("/api/analysis/products", json={"smiles": "CC=C"}).json()["count"] > 5
        assert client.post("/api/analysis/retro", json={"smiles": "CCO"}).json()["count"] > 1
        r = client.post("/api/analysis/classify", json={"reactants": ["CCO"], "products": ["CC=O"]})
        assert r.status_code == 200 and r.json()["matches"][0]["category"] == "oxidation"
