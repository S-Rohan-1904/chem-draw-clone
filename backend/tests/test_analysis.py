import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient  # noqa: E402
from rdkit import Chem  # noqa: E402

from app import analysis  # noqa: E402
from app.chem import embed_3d, mol_from_smiles  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def _ox(smi):
    return {a["idx"]: a["oxidation_state"] for a in analysis.oxidation_states(mol_from_smiles(smi))}


def test_oxidation_states():
    assert _ox("CC(=O)O") == {0: -3, 1: 3, 2: -2, 3: -2}
    assert _ox("C") == {0: -4}
    assert _ox("O=C=O") == {0: -2, 1: 4, 2: -2}
    assert _ox("CCl") == {0: -2, 1: -1}
    ox = _ox("[N+](=O)([O-])C")
    assert ox[0] == 3


def test_bond_polarity_classes():
    pol = {b["label"]: b["class"] for b in analysis.bond_polarity(mol_from_smiles("CCO"))}
    assert pol["C1-C2"] == "nonpolar"
    assert pol["C2-O3"] == "polar"
    ionic = analysis.bond_polarity(mol_from_smiles("[Li]F"))
    assert ionic[0]["class"] == "ionic"


def test_dipole_zero_for_symmetric():
    for smi in ("C", "O=C=O", "c1ccccc1"):
        mb = Chem.MolToMolBlock(embed_3d(mol_from_smiles(smi)))
        d = analysis.dipole(mb)
        assert d is not None and d["debye"] < 0.15, smi
    mb = Chem.MolToMolBlock(embed_3d(mol_from_smiles("O")))
    assert analysis.dipole(mb)["debye"] > 0.8


def test_vsepr_shapes():
    shapes = {v["symbol"] + str(v["idx"]): v["shape"] for v in analysis.vsepr(mol_from_smiles("CC(=O)N"))}
    assert shapes["C0"] == "tetrahedral"
    assert shapes["C1"] == "trigonal planar"
    assert shapes["N3"] == "trigonal planar"  # amide N is planar
    water = analysis.vsepr(mol_from_smiles("O"))
    assert water[0]["shape"] == "bent" and water[0]["ideal_angle"] == 104.5
    amine = analysis.vsepr(mol_from_smiles("CN"))
    assert [v["shape"] for v in amine if v["symbol"] == "N"] == ["trigonal pyramidal"]
    co2 = analysis.vsepr(mol_from_smiles("O=C=O"))
    assert co2[0]["shape"] == "linear"
    ether = [v for v in analysis.vsepr(mol_from_smiles("CC(=O)OC")) if v["symbol"] == "O"]
    assert ether[0]["shape"] == "bent"


def test_ring_aromaticity():
    r = analysis.ring_aromaticity(mol_from_smiles("c1ccccc1"))[0]
    assert r["aromatic"] and r["pi_electrons"] == 6
    r = analysis.ring_aromaticity(mol_from_smiles("c1cc[nH]c1"))[0]
    assert r["aromatic"] and r["pi_electrons"] == 6
    r = analysis.ring_aromaticity(mol_from_smiles("C1=CC=CC1"))[0]
    assert not r["aromatic"] and not r["conjugated"]
    r = analysis.ring_aromaticity(mol_from_smiles("C1=CC=C1"))[0]
    assert not r["aromatic"] and r["pi_electrons"] == 4 and "4n" in r["verdict"]
    r = analysis.ring_aromaticity(mol_from_smiles("C1CCCCC1"))[0]
    assert r["pi_electrons"] == 0 and not r["conjugated"]
    naph = analysis.ring_aromaticity(mol_from_smiles("c1ccc2ccccc2c1"))
    assert len(naph) == 2 and all(x["aromatic"] for x in naph)


def test_unsaturation():
    u = analysis.unsaturation(mol_from_smiles("c1ccccc1"))
    assert u["dbe"] == 4 and u["structural"] == 4 and u["consistent"]
    u = analysis.unsaturation(mol_from_smiles("C#CC"))
    assert u["dbe"] == 2 and u["triple_bonds"] == 1 and u["consistent"]
    u = analysis.unsaturation(mol_from_smiles("ClC1CC1"))
    assert u["dbe"] == 1 and u["rings"] == 1
    u = analysis.unsaturation(mol_from_smiles("CC#N"))
    assert u["dbe"] == 2 and u["consistent"]


def test_chirality_class():
    assert analysis.chirality_class(mol_from_smiles("CCO"))["kind"] == "achiral"
    assert analysis.chirality_class(mol_from_smiles("C[C@H](O)CC"))["kind"] == "chiral"
    meso = analysis.chirality_class(mol_from_smiles("O[C@H](C(=O)O)[C@@H](O)C(=O)O"))
    assert meso["kind"] == "meso" and meso["pairs"] == [[1, 5]]
    chiral_tart = analysis.chirality_class(mol_from_smiles("O[C@H](C(=O)O)[C@H](O)C(=O)O"))
    assert chiral_tart["kind"] == "chiral"
    unknown = analysis.chirality_class(mol_from_smiles("CC(O)CC"))
    assert unknown["kind"] == "unknown"
    # cis-1,2-dimethylcyclohexane is meso, trans is chiral
    assert analysis.chirality_class(mol_from_smiles("C[C@H]1CCCC[C@H]1C"))["kind"] == "meso"
    assert analysis.chirality_class(mol_from_smiles("C[C@H]1CCCC[C@@H]1C"))["kind"] == "chiral"


def test_hbond_and_solubility():
    hb = analysis.hbond_sites(mol_from_smiles("CCO"))
    assert hb["donors"] == [2] and hb["acceptors"] == [2] and hb["both"] == [2]
    assert "<svg" in hb["svg"]
    sol_eth = analysis.solubility(mol_from_smiles("CCO"))
    sol_hex = analysis.solubility(mol_from_smiles("CCCCCCCC"))
    assert sol_eth["logs"] > sol_hex["logs"]
    assert sol_hex["class"] in ("poorly soluble", "moderately soluble")


def test_bonding_endpoint():
    with client:
        r = client.post("/api/analysis/bonding", json={"smiles": "CC(=O)O"})
        assert r.status_code == 200
        body = r.json()
        assert body["oxidation"]["atoms"][1]["oxidation_state"] == 3
        assert "<svg" in body["oxidation"]["svg"] and "<svg" in body["polarity"]["svg"]
        assert body["polarity"]["dipole"]["debye"] > 0
        assert body["unsaturation"]["dbe"] == 1
        assert body["chirality"]["kind"] == "achiral"
        assert client.post("/api/analysis/bonding", json={"smiles": "not smiles"}).status_code == 400
