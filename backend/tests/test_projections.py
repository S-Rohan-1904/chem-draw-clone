import pytest

from app.chem import ChemError, build
from app.projections import chair_analysis, chair_rings, chair_svg, newman_bonds, newman_svg


def test_newman_bonds_and_svg():
    r = build("butane")
    bonds = newman_bonds(r.molblock)
    assert len(bonds) == 1  # only C2-C3 has two non-terminal ends
    f, b = bonds[0]["atoms"]
    out = newman_svg(r.molblock, f, b)
    assert "<svg" in out["svg"] and "CH3" in out["svg"] and len(out["front_subs"]) == 3
    rot = newman_svg(r.molblock, f, b, rotate_deg=60)
    assert rot["dihedral"] != out["dihedral"]
    with pytest.raises(ChemError):
        newman_svg(r.molblock, 0, 3)


def test_chair_axial_equatorial():
    r = build("trans-1,4-dimethylcyclohexane")
    rings = chair_rings(r.molblock)
    assert len(rings) == 1
    a = chair_analysis(r.molblock, rings[0])
    kinds = sorted(s["axial"] for s in a["substituents"])
    # trans-1,4: diequatorial (stable) or diaxial; ETKDG+MMFF gives the diequatorial chair
    assert kinds in ([False, False], [True, True])
    svg = chair_svg(a)
    assert "CH3" in svg and ("eq" in svg or "ax" in svg)
    assert chair_svg(a, flipped=True) != svg


def test_cis_has_one_of_each():
    r = build("cis-1,4-dimethylcyclohexane")
    a = chair_analysis(r.molblock, chair_rings(r.molblock)[0])
    assert sorted(s["axial"] for s in a["substituents"]) == [False, True]


def test_no_chair_for_benzene():
    assert chair_rings(build("benzene").molblock) == []
