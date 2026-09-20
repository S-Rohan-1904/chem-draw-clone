import pytest

from app.align import align
from app.chem import ChemError, build


def test_enantiomers_overlay():
    a, b = build("(2R)-butan-2-ol"), build("(2S)-butan-2-ol")
    r = align(a.molblock, b.molblock)
    assert r["common_atoms"] == 5 and r["identical_connectivity"] and 0 < r["rmsd"] < 2
    assert "M  END" in r["molblock_b"]


def test_related_molecules():
    a, b = build("ethanol"), build("propan-1-ol")
    r = align(a.molblock, b.molblock)
    assert r["common_atoms"] == 3 and not r["identical_connectivity"]


def test_unrelated_rejected():
    with pytest.raises(ChemError):
        align(build("methane").molblock, build("ammonia").molblock)
