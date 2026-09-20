import pytest

from app.chem import ChemError
from app.isomers import carbon_trees, enumerate_isomers


@pytest.mark.parametrize("formula,count", [("C4H10", 2), ("C5H12", 3), ("C6H14", 5), ("C7H16", 9), ("C8H18", 18),
                                           ("C4H10O", 7), ("C3H8O", 3), ("C4H9Cl", 4), ("C3H9N", 4), ("C4H8", 3), ("C2H6O", 2)])
def test_known_counts(formula, count):
    assert enumerate_isomers(formula)["count"] == count


def test_enols_omitted():
    r = enumerate_isomers("C3H6O")
    smiles = {i["smiles"] for i in r["isomers"]}
    assert "CC(C)=O" in smiles and "CCC=O" in smiles and "C=CCO" in smiles
    assert not any("=C" in s and "O" in s and s.count("O") == 1 and "C(O)" in s for s in smiles)  # no enols
    assert r["skipped_unstable"] >= 1


def test_tree_counts():
    assert [len(carbon_trees(n)) for n in range(1, 9)] == [1, 1, 1, 2, 3, 5, 9, 18]


def test_limits():
    for bad in ["C9H20", "C6H6", "C2H6S", "C4H10O3", "xyz"]:
        with pytest.raises(ChemError):
            enumerate_isomers(bad)
