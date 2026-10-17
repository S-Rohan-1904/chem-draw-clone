import os
import shutil
from pathlib import Path

import pytest
from rdkit import Chem

from app import vibrations

G98 = """ Harmonic frequencies (cm**-1), IR intensities (km*mol-1)
                      1                      2                      3
                        a                      a                      a
 Frequencies --   -61.9612               114.8397               378.5725
 Red. masses --     1.1448                 2.4626                 8.1971
 IR Inten    --     0.0002                 0.4679                 0.9892
 Atom AN      X      Y      Z        X      Y      Z        X      Y      Z
   1   6    -0.03  -0.03  -0.07     0.04   0.05   0.10    -0.36  -0.14   0.22
   2   8    -0.00  -0.00  -0.00     0.02   0.02   0.05     0.02   0.28  -0.14
                      4
                        a
 Frequencies --  1784.1
 IR Inten    --   342.08
 Atom AN      X      Y      Z
   1   6     0.10   0.20   0.30
   2   8    -0.40   0.00   0.00
"""


def test_g98_modes_are_read_block_by_block():
    modes = vibrations.parse_g98(G98)
    assert [m["freq"] for m in modes] == [-61.9612, 114.8397, 378.5725, 1784.1]
    assert modes[1]["intensity"] == 0.4679 and modes[3]["intensity"] == 342.08
    assert modes[2]["disp"] == [[-0.36, -0.14, 0.22], [0.02, 0.28, -0.14]]
    assert modes[3]["disp"][1] == [-0.4, 0.0, 0.0]


def test_without_xtb_there_is_no_calculated_spectrum(monkeypatch, tmp_path):
    monkeypatch.setenv("CHEM_XTB", str(tmp_path / "missing"))
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert vibrations.calculate(Chem.MolFromSmiles("CC(C)=O")) == (None, True)


def _xtb() -> str | None:
    for p in (os.environ.get("CHEM_XTB_TEST"), str(Path.home() / ".local/share/xtb-env/bin/xtb"), shutil.which("xtb")):
        if p and Path(p).is_file():
            return p
    return None


@pytest.mark.skipif(_xtb() is None, reason="xtb is not installed")
def test_acetone_carbonyl_stretch_is_the_strongest_band(monkeypatch):
    monkeypatch.setenv("CHEM_XTB", _xtb())
    data, complete = vibrations.calculate(Chem.MolFromSmiles("CC(C)=O"))
    assert complete and data["method"] == "GFN2-xTB" and len(data["atoms"]) == 10
    co = max(data["modes"], key=lambda m: m["intensity"])
    assert 1700 < co["freq"] < 1800  # experiment: 1731 cm-1 (gas)
    assert co["atoms"] == [1, 3] and len(co["disp"]) == 10
    assert all(m["freq"] >= vibrations.MIN_FREQ * vibrations.SCALE for m in data["modes"])
