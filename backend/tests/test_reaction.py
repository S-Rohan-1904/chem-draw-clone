import pytest

from app.chem import ChemError
from app.reaction import is_reaction, parse_reaction


def test_esterification_balanced():
    r = parse_reaction("CC(=O)O.CCO>>CC(=O)OCC.O")
    assert r["balanced"] and len(r["reactants"]) == 2 and len(r["products"]) == 2
    assert "<svg" in r["svg"]


def test_unbalanced_reports_diff():
    r = parse_reaction("CC(=O)O.CCO>>CC(=O)OCC")
    assert not r["balanced"] and r["imbalance"] == {"H": -2, "O": -1}


def test_agents_and_mapping():
    r = parse_reaction("[CH3:1][OH:2].[Cl:3]C(=O)C>[Na+]>[CH3:1][O:2]C(=O)C.[Cl:3]")
    assert r["agents"] and r["mapped"]


def test_is_reaction_and_errors():
    assert is_reaction("CCO>>CC=O") and not is_reaction("but-2-ene") and not is_reaction("(E)-but-2-ene > name")
    with pytest.raises(ChemError):
        parse_reaction("CCO>>")
    with pytest.raises(ChemError):
        parse_reaction("notasmiles>>CC")


def test_single_atom_agents_draw_cleanly():
    r = parse_reaction("CC(=O)O.OCC>[H+].[Cl-].OCC>CC(=O)OCC")
    assert "nan" not in r["svg"]
    assert "H⁺" in r["svg"] and "Cl⁻" in r["svg"] and "C₂H₆O" in r["svg"]
    assert r["svg"].count("<g transform") == 3  # two reactants, one product
