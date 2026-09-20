import pytest
from rdkit import Chem

from app.chem import ChemError, _cip_labels, build, resolve

STEREO_CASES = [
    ("(2R,3S)-2,3-dibromobutane", {"R", "S"}, set()),
    ("(2E)-but-2-ene", set(), {"E"}),
    ("(2Z)-but-2-ene", set(), {"Z"}),
    ("(1R,2S)-2-methylcyclohexan-1-ol", {"R", "S"}, set()),
    ("(2R)-2-[4-(2-methylpropyl)phenyl]propanoic acid", {"R"}, set()),
    ("(1R,4R)-1,7,7-trimethylbicyclo[2.2.1]heptan-2-one", {"R"}, set()),
    ("(2E,4Z)-hexa-2,4-dienoic acid", set(), {"E", "Z"}),
    ("C[C@H](N)C(=O)O", {"S"}, set()),
]


@pytest.mark.parametrize("name,centers,bonds", STEREO_CASES)
def test_build_reports_stereo(name, centers, bonds):
    r = build(name)
    assert {c.label for c in r.stereo.centers} == centers
    assert {b.label for b in r.stereo.double_bonds} == bonds
    assert not r.stereo.unspecified
    assert "<svg" in r.svg
    assert "M  END" in r.molblock


@pytest.mark.parametrize("name,_c,_b", STEREO_CASES)
def test_3d_geometry_matches_input_stereo(name, _c, _b):
    r = build(name)
    mol3d = Chem.MolFromMolBlock(r.molblock, removeHs=False)
    Chem.AssignStereochemistryFrom3D(mol3d, replaceExistingTags=True)
    got = _cip_labels(mol3d)
    expected = _cip_labels(Chem.MolFromSmiles(r.smiles))
    assert expected and all(got[k] == v for k, v in expected.items())


def test_smiles_fallback_source():
    assert resolve("CCO") == ("CCO", "smiles")
    assert resolve("ethanol")[1] == "iupac"


def test_unspecified_flagged():
    r = build("2-methylcyclohexan-1-ol")
    assert r.stereo.unspecified
    assert all(c.label == "?" for c in r.stereo.centers)


def test_garbage_rejected():
    with pytest.raises(ChemError):
        build("garbage name")


def test_impossible_stereo_rejected():
    with pytest.raises(ChemError, match="3D"):
        build("(1S,4R)-1,7,7-trimethylbicyclo[2.2.1]heptan-2-one")


# (R)/(S)-butan-2-ol drawn with a wedge (bond stereo 1) or hash (6) on the C2-O bond.
def _butanol_molfile(wedge: int) -> str:
    return f"""
  editor

  5  4  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.2990    0.7500    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    2.5981    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    3.8971    0.7500    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.2990    2.2500    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
  3  4  1  0
  2  5  1  {wedge}
M  END
"""


def test_molfile_wedge_sets_stereo():
    from app.chem import resolve_full

    up = resolve_full(_butanol_molfile(1))
    down = resolve_full(_butanol_molfile(6))
    flat = resolve_full(_butanol_molfile(0))
    assert up.source == "molfile" and "@" in up.smiles and "@" in down.smiles
    assert up.smiles != down.smiles
    assert "@" not in flat.smiles
    labels = {build(_butanol_molfile(1)).stereo.centers[0].label, build(_butanol_molfile(6)).stereo.centers[0].label}
    assert labels == {"R", "S"}
    assert build(_butanol_molfile(0)).stereo.unspecified


def test_molfile_3d_roundtrip():
    r = build(_butanol_molfile(1))
    mol3d = Chem.MolFromMolBlock(r.molblock, removeHs=False)
    Chem.AssignStereochemistryFrom3D(mol3d, replaceExistingTags=True)
    assert _cip_labels(mol3d) == _cip_labels(Chem.MolFromSmiles(r.smiles)) or set(_cip_labels(mol3d).values()) == set(
        _cip_labels(Chem.MolFromSmiles(r.smiles)).values()
    )


def test_bad_molfile_rejected():
    with pytest.raises(ChemError, match="drawn"):
        build("garbage\n\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n")
    with pytest.raises(ChemError):
        build("\n\n\n  1  0  0  0  0  0            999 V2000\n    0.0 0.0 0.0 Xx  0  0\nM  END\n")


def test_properties_panel_values():
    r = build("2-acetyloxybenzoic acid")  # aspirin
    p = r.properties
    assert p["hbd"] == 1 and p["hba"] == 3 and p["rings"] == 1 and p["aromatic_rings"] == 1
    assert 1.0 < p["logp"] < 1.5 and 60 < p["tpsa"] < 65
    assert p["lipinski_violations"] == 0 and p["charge"] == 0
    assert abs(p["exact_mass"] - 180.0423) < 0.001
    assert build("(2R)-butan-2-ol").properties["stereocentres"] == 1


def test_atom_table():
    from app.chem import atom_table

    rows = {r["symbol"] + str(r["idx"]): r for r in atom_table(Chem.MolFromSmiles("CC(=O)O"))}
    assert rows["C0"]["hybridization"] == "sp3" and rows["C1"]["hybridization"] == "sp2"
    assert rows["O2"]["lone_pairs"] == 2 and rows["O3"]["lone_pairs"] == 2
    amine = atom_table(Chem.MolFromSmiles("CN"))[1]
    assert amine["lone_pairs"] == 1 and amine["hs"] == 2
    nitrile = atom_table(Chem.MolFromSmiles("CC#N"))
    assert nitrile[1]["hybridization"] == "sp" and nitrile[2]["lone_pairs"] == 1
    assert all(r["hybridization"] == "sp2" for r in atom_table(Chem.MolFromSmiles("c1ccccc1")))
    ammonium = atom_table(Chem.MolFromSmiles("C[N+](C)(C)C"))[1]
    assert ammonium["lone_pairs"] == 0 and ammonium["charge"] == 1
