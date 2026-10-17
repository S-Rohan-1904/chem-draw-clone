import sys
from pathlib import Path

import pytest
from rdkit import Chem

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import nmr_env as builder  # noqa: E402  (scripts/nmr_env.py)

from app import nmr_env, spectra  # noqa: E402


def _record(smiles, c, h, solvent="0:Chloroform-D1 (CDCl3)", record="1"):
    mol = Chem.MolFromSmiles(smiles)
    mol.SetProp("nmrshiftdb2 ID", record)
    mol.SetProp("INChI key", Chem.MolToInchiKey(mol))
    mol.SetProp("Solvent", solvent)
    if c:
        mol.SetProp("Spectrum 13C 0", "".join(f"{v};0.0Q;{i}|" for i, v in c.items()))
    if h:
        mol.SetProp("Spectrum 1H 0", "".join(f"{v};0.0;{i}|" for i, vs in h.items() for v in vs))
    return mol


@pytest.fixture
def index(tmp_path, monkeypatch):
    sd = tmp_path / "toy.sd"
    w = Chem.SDWriter(str(sd))
    # Ethanol twice (two records: the one with more assignments is kept as measured), and propan-1-ol.
    w.write(_record("CCO", {0: 18.3, 1: 58.2}, {0: [1.22, 1.22, 1.22], 1: [3.69, 3.69]}, record="11"))
    w.write(_record("CCO", {0: 18.1}, {}, solvent="0:Dimethylsulphoxide-D6 (DMSO-D6)", record="12"))
    w.write(_record("CCCO", {0: 10.3, 1: 25.9, 2: 64.2}, {0: [0.93] * 3, 1: [1.57] * 2, 2: [3.58] * 2}, record="13"))
    w.close()
    out = tmp_path / "nmr_env.db"
    builder.build(str(sd), str(out), holdout=0, test_path=None)
    monkeypatch.setenv("CHEM_NMR_ENV_DB", str(out))
    return out


def test_measured_shifts_map_onto_the_built_molecule(index):
    mol = Chem.MolFromSmiles("OCC")  # atoms in another order than the stored record
    seen = nmr_env.measured(mol)
    assert seen["record"] == "11" and seen["solvent"] == "CDCl3"
    assert seen["C"] == [None, 58.2, 18.3] and seen["H"] == [None, 3.69, 1.22]
    assert nmr_env.measured(Chem.MolFromSmiles("CCCCO")) is None


def test_prediction_uses_the_widest_matching_environment(index):
    pred = nmr_env.predict(Chem.MolFromSmiles("CCCCO"))  # butan-1-ol: not in the toy index
    ch2o = pred["C"][3]
    assert ch2o["radius"] >= 1 and abs(ch2o["shift"] - 64.2) < 7
    assert ch2o["spread"] >= nmr_env.TYPICAL_ERROR["C"][ch2o["radius"]]
    assert pred["C"][4] is None and pred["H"][4] is None  # no 13C on oxygen, and the toy records assign no OH proton


def test_card_shows_measured_then_index_then_rules(index):
    data, complete = spectra.nmr("CCO")
    assert complete and data["source"] == "measured" and data["record"] == {"id": "11", "solvent": "CDCl3"}
    c = {p["label"]: p for p in data["c"]["peaks"]}
    assert c["CH2-O"]["shift"] == 58.2 and c["CH2-O"]["estimate"] == "measured" and "spread" not in c["CH2-O"]
    oh = next(p for p in data["h"]["peaks"] if p["exchangeable"])
    assert oh["estimate"] in ("index", "rules")  # the record assigns no OH proton

    data, _ = spectra.nmr("CCCCO")
    est = {p["estimate"] for p in data["c"]["peaks"]}
    assert data["source"] == "index" and "index" in est and "record" not in data

    data, _ = spectra.nmr("FC(F)(F)S(=O)(=O)c1ccccc1")  # nothing like it in the toy index
    assert {p["estimate"] for p in data["c"]["peaks"]} <= {"rules", "index"}
    assert any(p["estimate"] == "rules" for p in data["c"]["peaks"]) and "additive rules" in data["note"]


def test_without_the_index_the_rules_answer(monkeypatch, tmp_path):
    monkeypatch.setenv("CHEM_NMR_ENV_DB", str(tmp_path / "missing.db"))
    data, complete = spectra.nmr("CCO")
    assert complete and data["source"] == "rules" and all("estimate" not in p for p in data["c"]["peaks"])


def test_spectra_made_by_prediction_programs_are_left_out(tmp_path, monkeypatch):
    assert builder._predicted("6:ACD/Labs C+H NMR Predictors and DB, 2020.1.0 7:HOSE code using nmrshiftdb2 data ") == {"6", "7"}
    assert builder._predicted("0:MestReNova 14.1 3:CSEARCH") == {"3"} and builder._predicted("") == set()
    mol = _record("CCO", {0: 18.3, 1: 58.2}, {})
    mol.SetProp("Spectrum 13C 1", "99.9;0.0Q;0|99.9;0.0Q;1|")
    mol.SetProp("Program", "1:HOSE code using nmrshiftdb2 data")
    sd = tmp_path / "one.sd"
    w = Chem.SDWriter(str(sd))
    w.write(mol)
    w.close()
    out = tmp_path / "one.db"
    builder.build(str(sd), str(out), holdout=0, test_path=None)
    monkeypatch.setenv("CHEM_NMR_ENV_DB", str(out))
    assert nmr_env.measured(Chem.MolFromSmiles("CCO"))["C"][:2] == [18.3, 58.2]
