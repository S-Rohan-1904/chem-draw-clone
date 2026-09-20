import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from rdkit import Chem  # noqa: E402

from app import chem, reaction, tools  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def test_elemental_percentages_sum_to_100():
    out = tools.elemental("CCO")
    assert out["formula"] == "C2H6O"
    assert [e["symbol"] for e in out["elements"]] == ["C", "H", "O"]
    assert abs(sum(e["percent"] for e in out["elements"]) - 100) < 0.05
    assert abs(out["elements"][0]["percent"] - 52.14) < 0.05


def test_elemental_hill_order_and_endpoint():
    r = client.post("/api/tools/elemental", json={"smiles": "ClCCBr"})
    assert r.status_code == 200
    assert [e["symbol"] for e in r.json()["elements"]] == ["C", "H", "Br", "Cl"]


def test_peptide_from_letters_and_three_letter_codes():
    a = tools.from_sequence("peptide", "AGS")
    b = tools.from_sequence("peptide", "Ala-Gly-Ser")
    c = tools.from_sequence("peptide", "ALA GLY SER")
    assert a["smiles"] == b["smiles"] == c["smiles"]
    assert a["residues"] == 3
    assert a["formula"] == "C8H15N3O5"


def test_dna_rna_helm():
    dna = tools.from_sequence("dna", "acgt")
    assert dna["sequence"] == "ACGT" and dna["heavy_atoms"] > 60
    rna = tools.from_sequence("rna", "ACGU")
    assert rna["smiles"] != dna["smiles"]
    helm = tools.from_sequence("helm", "PEPTIDE1{A.G.S}$$$$")
    assert helm["smiles"] == tools.from_sequence("peptide", "AGS")["smiles"]


def test_sequence_rejects_bad_letters_and_length():
    with pytest.raises(chem.ChemError):
        tools.from_sequence("dna", "ACGU")
    with pytest.raises(chem.ChemError, match="heavy atoms"):
        tools.from_sequence("peptide", "W" * 30)
    r = client.post("/api/tools/sequence", json={"kind": "peptide", "sequence": "AXZ"})
    assert r.status_code == 400 and "X" in r.json()["detail"]


def test_conformers_sorted_with_populations():
    out = tools.conformers("CCCCO", 6)
    confs = out["conformers"]
    assert 2 <= len(confs) <= 6
    assert confs[0]["relative"] == 0 and confs[0]["rmsd"] == 0
    assert all(confs[i]["relative"] <= confs[i + 1]["relative"] for i in range(len(confs) - 1))
    assert abs(sum(c["population"] for c in confs) - 100) < 0.5
    assert Chem.MolFromMolBlock(confs[1]["molblock"]) is not None


def test_conformers_keeps_stereo():
    out = tools.conformers("C[C@H](O)CC", 4)
    for c in out["conformers"]:
        m = Chem.MolFromMolBlock(c["molblock"])
        Chem.AssignStereochemistryFrom3D(m)
        assert Chem.MolToSmiles(m) == "CC[C@H](C)O"


def test_minimise_lowers_energy():
    with client:
        r = client.post("/api/tools/minimise", json={"smiles": "CC(=O)OC"})
    assert r.status_code == 200
    out = r.json()
    assert out["after"] <= out["before"] + 1e-6
    assert out["force_field"] == "MMFF94"


def test_search_substructure_then_similarity():
    items = [(1, "c1ccccc1O"), (2, "CCO"), (3, "CCCO")]
    sub = tools.search("c1ccccc1", items)
    assert sub["mode"] == "substructure" and [h["id"] for h in sub["hits"]] == [1]
    assert len(sub["hits"][0]["atoms"]) == 6
    sim = tools.search("CCO", items, "similarity")
    assert sim["mode"] == "similarity" and sim["hits"][0]["id"] == 2 and sim["hits"][0]["score"] == 1.0
    auto = tools.search("[OH]C", items)  # SMARTS with no exact hit is fine
    assert auto["mode"] == "substructure"
    with pytest.raises(chem.ChemError):
        tools.search("not smiles", items)


def test_search_endpoint_scoped_to_user():
    with client:
        tok = client.post("/api/auth/register", json={"username": "searcher", "password": "pw123456"}).json()["token"]
        h = {"Authorization": f"Bearer {tok}"}
        client.post("/api/saved", json={"label": "phenol", "input_text": "phenol", "smiles": "Oc1ccccc1"}, headers=h)
        client.post("/api/saved", json={"label": "ethanol", "input_text": "ethanol", "smiles": "CCO"}, headers=h)
        r = client.post("/api/tools/search", json={"query": "c1ccccc1"}, headers=h)
        assert r.status_code == 200 and len(r.json()["hits"]) == 1
        assert client.post("/api/tools/search", json={"query": "CCO"}).status_code == 401


def test_structure_check_messages():
    with pytest.raises(chem.ChemError) as e:
        chem.resolve_full("CC(C)(C)(C)C")
    assert "C2 has 5 bonds" in str(e.value)
    with pytest.raises(chem.ChemError) as e:
        chem.resolve_full("c1cccc1")
    assert "alternating double bonds" in str(e.value)
    bad = Chem.MolToMolBlock(Chem.MolFromSmiles("CC(C)(C)(C)C", sanitize=False))
    with pytest.raises(chem.ChemError) as e:
        chem.resolve_molfile(bad)
    assert "C2 has 5 bonds" in str(e.value)


def test_enhanced_stereo_notes():
    mb = Chem.MolToMolBlock(Chem.MolFromSmiles("C[C@H](O)CC"), forceV3000=True)
    plain = chem.resolve_molfile(mb)
    assert plain.warnings == []
    rac = mb.replace("M  V30 END BOND", "M  V30 END BOND\nM  V30 BEGIN COLLECTION\nM  V30 MDLV30/STERAC1 ATOMS=(1 2)\nM  V30 END COLLECTION")
    r = chem.resolve_molfile(rac)
    assert r.smiles == plain.smiles
    assert len(r.warnings) == 1 and "racemic" in r.warnings[0] and "C2" in r.warnings[0]
    rel = rac.replace("STERAC1", "STEREL1")
    assert "relative" in chem.resolve_molfile(rel).warnings[0]


def test_reaction_components_have_mw_and_map_colours():
    out = reaction.parse_reaction("[CH3:1][OH:2].[C:3](=O)O>>[CH3:1][O:2][C:3](=O)")
    assert out["mapped"] and out["reactants"][0]["mw"] == 32.04
    assert out["svg"].count("fill:#") >= 3  # highlight circles for mapped atoms
    plain = reaction.parse_reaction("CO.C(=O)O>>COC(=O)")
    assert not plain["mapped"] and plain["products"][0]["mw"] > 0


def test_structure_check_reaches_api():
    with client:
        r = client.post("/api/molecule", json={"input": "CC(C)(C)(C)C"})
        assert r.status_code == 400 and "C2 has 5 bonds" in r.json()["detail"]
        r = client.post("/api/molecule/check", json={"input": "c1cccc1"})
        assert r.json()["ok"] is False and "alternating double bonds" in r.json()["reason"]
