"""Exhaustive corpus run: every name must parse, report the expected stereo
elements, embed in 3D, and the 3D geometry must reproduce every label."""

import pytest
from rdkit import Chem

from app.chem import ChemError, _cip_labels, build, resolve

from tests.corpus import CORPUS, IMPOSSIBLE_STEREO, INVALID, STEREO_IGNORED, UNSPECIFIED, UNSUPPORTED_NAMES

VALID = [c for c in CORPUS if not c[3].endswith("skip") and "skip" not in c[3]]


IDS = [f"{c[3]}:{c[0][:50]}" for c in VALID]


@pytest.mark.parametrize("name,n_centers,n_bonds,category", VALID, ids=IDS)
def test_corpus_entry(name, n_centers, n_bonds, category):
    r = build(name)

    assert not r.stereo.unspecified, f"unspecified stereo in {name}: {r.stereo}"
    if n_centers is not None:
        assert len(r.stereo.centers) == n_centers, (
            f"{name}: expected {n_centers} centres, got {[(c.atom_idx, c.label) for c in r.stereo.centers]} smiles={r.smiles}"
        )
    if n_bonds is not None:
        assert len(r.stereo.double_bonds) == n_bonds, (
            f"{name}: expected {n_bonds} E/Z bonds, got {[(b.atoms, b.label) for b in r.stereo.double_bonds]} smiles={r.smiles}"
        )

    assert "<svg" in r.svg and "M  END" in r.molblock
    assert r.formula and r.mw > 0 and r.inchikey

    # 3D round trip: re-perceive stereo from coordinates, must match every label.
    mol3d = Chem.MolFromMolBlock(r.molblock, removeHs=False)
    assert mol3d is not None
    Chem.AssignStereochemistryFrom3D(mol3d, replaceExistingTags=True)
    got = _cip_labels(mol3d)
    expected = _cip_labels(Chem.MolFromSmiles(r.smiles))
    assert all(got.get(k) == v for k, v in expected.items()), f"{name}: 3D {got} != {expected}"

    # Heavy-atom count preserved through AddHs/embedding.
    assert Chem.RemoveHs(mol3d).GetNumAtoms() == Chem.MolFromSmiles(r.smiles).GetNumAtoms()


@pytest.mark.parametrize("name", INVALID)
def test_invalid_rejected(name):
    with pytest.raises(ChemError):
        build(name)


@pytest.mark.parametrize("name", UNSUPPORTED_NAMES)
def test_unsupported_name_rejected_cleanly(name):
    with pytest.raises(ChemError, match="Could not interpret"):
        build(name)


@pytest.mark.parametrize("name", STEREO_IGNORED)
def test_unplaceable_stereo_builds_with_warning(name):
    r = build(name)
    assert r.warnings and "ignored" in r.warnings[0]


@pytest.mark.parametrize("name", IMPOSSIBLE_STEREO)
def test_impossible_stereo_rejected(name):
    with pytest.raises(ChemError, match="3D"):
        build(name)


@pytest.mark.parametrize("name,n_unspecified", UNSPECIFIED)
def test_unspecified_flagged(name, n_unspecified):
    r = build(name)
    assert r.stereo.unspecified
    unspecified = [c for c in r.stereo.centers if c.label == "?"] + [
        b for b in r.stereo.double_bonds if b.label == "?"
    ]
    if n_unspecified:
        assert len(unspecified) >= 1


def test_enantiomers_are_mirror_images():
    pairs = [
        ("(2R)-butan-2-ol", "(2S)-butan-2-ol"),
        ("(4R)-1-methyl-4-(prop-1-en-2-yl)cyclohex-1-ene", "(4S)-1-methyl-4-(prop-1-en-2-yl)cyclohex-1-ene"),
        ("L-alanine", "D-alanine"),
        ("(1R,4R)-1,7,7-trimethylbicyclo[2.2.1]heptan-2-one", "(1S,4S)-1,7,7-trimethylbicyclo[2.2.1]heptan-2-one"),
    ]
    for a, b in pairs:
        ra, rb = build(a), build(b)
        assert ra.smiles != rb.smiles
        assert ra.inchikey.split("-")[0] == rb.inchikey.split("-")[0]  # same skeleton
        assert ra.inchikey != rb.inchikey
        assert {c.label for c in ra.stereo.centers} != {c.label for c in rb.stereo.centers} or len(ra.stereo.centers) > 1
        assert sorted(c.label for c in ra.stereo.centers) == sorted(
            {"R": "S", "S": "R"}[c.label] for c in rb.stereo.centers
        )


def test_ez_pairs_differ():
    for e, z in [("(2E)-but-2-ene", "(2Z)-but-2-ene"), ("(E)-but-2-enedioic acid", "(Z)-but-2-enedioic acid")]:
        re_, rz = build(e), build(z)
        assert re_.inchikey != rz.inchikey
        assert re_.stereo.double_bonds[0].label == "E" and rz.stereo.double_bonds[0].label == "Z"


def test_meso_is_achiral():
    r = build("(2R,3S)-2,3-dibromobutane")
    mol = Chem.MolFromSmiles(r.smiles)
    mirror = Chem.MolFromSmiles(r.smiles.replace("@@", "X").replace("@", "@@").replace("X", "@"))
    assert Chem.MolToSmiles(mol) == Chem.MolToSmiles(mirror)


def test_name_variants_same_molecule():
    groups = [
        ["L-alanine", "(2S)-2-aminopropanoic acid", "(S)-alanine", "(S)-2-aminopropanoic acid"],
        ["2-acetoxybenzoic acid", "2-acetyloxybenzoic acid", "acetylsalicylic acid"],
        ["(1R,4R)-camphor", "(1R,4R)-1,7,7-trimethylbicyclo[2.2.1]heptan-2-one"],
        ["ethanoic acid", "acetic acid", "CC(=O)O"],
        ["(E)-but-2-enedioic acid", "fumaric acid", "trans-butenedioic acid"],
        ["(Z)-but-2-enedioic acid", "maleic acid", "cis-butenedioic acid"],
    ]
    for group in groups:
        keys = {build(n).inchikey for n in group}
        assert len(keys) == 1, f"{group} -> {keys}"


def test_whitespace_and_case_tolerated():
    a = build("(2R)-Butan-2-OL")
    b = build("  (2r)-butan-2-ol  ")
    assert a.inchikey == b.inchikey
