import pytest

from app.chem import build, mol_from_smiles, render_svg_highlight
from app.groups import find_groups


def names(smiles):
    return {g["name"] for g in find_groups(mol_from_smiles(smiles))}


@pytest.mark.parametrize(
    "smiles,expected,absent",
    [
        ("CC(=O)Oc1ccccc1C(=O)O", {"Carboxylic acid", "Ester", "Aromatic ring"}, {"Ketone", "Ether", "Alcohol"}),
        ("CCO", {"Alcohol"}, {"Ether", "Phenol"}),
        ("COC", {"Ether"}, {"Alcohol"}),
        ("CC(=O)C", {"Ketone"}, {"Aldehyde"}),
        ("CC=O", {"Aldehyde"}, {"Ketone"}),
        ("CC(=O)N", {"Amide"}, {"Amine", "Ketone"}),
        ("CCN", {"Amine"}, {"Amide"}),
        ("Nc1ccccc1", {"Aniline N", "Aromatic ring"}, {"Amine"}),
        ("CC#N", {"Nitrile"}, set()),
        ("C[N+](=O)[O-]", {"Nitro"}, set()),
        ("CCCl", {"Alkyl halide"}, {"Aryl halide"}),
        ("Clc1ccccc1", {"Aryl halide"}, {"Alkyl halide"}),
        ("C=CC#C", {"Alkene", "Alkyne"}, set()),
        ("CS(=O)C", {"Sulfoxide"}, {"Sulfone"}),
        ("Oc1ccccc1", {"Phenol"}, {"Alcohol"}),
    ],
)
def test_group_detection(smiles, expected, absent):
    found = names(smiles)
    assert expected <= found, found
    assert not (absent & found), found


def test_groups_in_result_and_highlight_svg():
    r = build("2-acetyloxybenzoic acid")
    group = next(g for g in r.groups if g["name"] == "Carboxylic acid")
    assert len(group["atoms"][0]) == 3
    svg = render_svg_highlight(mol_from_smiles(r.smiles), group["atoms"][0], group["colour"])
    assert "<svg" in svg and "fill:#" in svg.lower()
    assert len(find_groups(mol_from_smiles("c1ccccc1"))[0]["atoms"]) == 1  # one ring, not 12 orderings
