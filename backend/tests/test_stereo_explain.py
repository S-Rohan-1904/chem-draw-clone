import pytest

from app.chem import ChemError, build
from app.stereo_explain import explain_centre, explain_double_bond


def test_r_butanol_priorities():
    r = build("(2R)-butan-2-ol")
    c = r.stereo.centers[0]
    ex = explain_centre(r.smiles, c.atom_idx)
    assert ex["label"] == "R"
    groups = [p["symbol"] for p in ex["priorities"]]
    assert groups == ["O", "C", "C", "H"]
    assert ex["priorities"][1]["group"].startswith("C (C") and ex["priorities"][2]["group"] == "C (H,H,H)"
    assert "clockwise" in ex["steps"][2] and "anticlockwise" not in ex["steps"][2]
    assert "<svg" in ex["svg"] and ex["has_h"]


def test_s_is_anticlockwise():
    r = build("(2S)-butan-2-ol")
    ex = explain_centre(r.smiles, r.stereo.centers[0].atom_idx)
    assert ex["label"] == "S" and "anticlockwise" in ex["steps"][2]


def test_bromochlorofluoromethane_no_h_when_quaternary():
    r = build("(R)-bromochlorofluoromethane")
    ex = explain_centre(r.smiles, r.stereo.centers[0].atom_idx)
    assert [p["symbol"] for p in ex["priorities"]] == ["Br", "Cl", "F", "H"]


def test_ez_explanation():
    r = build("(2E)-but-2-ene")
    b = r.stereo.double_bonds[0]
    ex = explain_double_bond(r.smiles, b.bond_idx)
    assert ex["label"] == "E" and "opposite sides" in ex["steps"][1]
    assert all(len(e["substituents"]) == 2 for e in ex["ends"])
    z = build("(2Z)-but-2-ene")
    assert "same side" in explain_double_bond(z.smiles, z.stereo.double_bonds[0].bond_idx)["steps"][1]


def test_non_stereo_atom_rejected():
    with pytest.raises(ChemError):
        explain_centre("CCO", 0)
