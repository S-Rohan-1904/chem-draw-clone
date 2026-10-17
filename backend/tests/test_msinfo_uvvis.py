import pytest
from rdkit import Chem

from app import msinfo, spectra, uvvis


def _m(smiles):
    return Chem.MolFromSmiles(smiles)


def test_esi_ions_and_which_are_likely():
    ions = {i["label"]: i for i in msinfo.esi_ions(_m("CCN(CC)CC"))}  # triethylamine, C6H15N, 101.1204
    assert ions["[M+H]+"]["mz"] == pytest.approx(102.1277, abs=1e-4) and ions["[M+H]+"]["likely"]
    assert not ions["[M-H]-"]["likely"]
    acid = {i["label"]: i for i in msinfo.esi_ions(_m("CC(=O)O"))}
    assert acid["[M-H]-"]["likely"] and acid["[M-H]-"]["mz"] == pytest.approx(59.0139, abs=1e-4)
    sugar = {i["label"]: i["likely"] for i in msinfo.esi_ions(_m("OCC1OC(O)C(O)C(O)C1O"))}
    assert sugar["[M+Na]+"] and not sugar["[M+H]+"]
    assert not any(i["likely"] for i in msinfo.esi_ions(_m("ClC(Cl)Cl")))
    assert [i["label"] for i in msinfo.esi_ions(_m("C[N+](C)(C)C"))] == ["[M]+"]


def test_nitrogen_rule_and_rings_plus_double_bonds():
    assert msinfo.rules(_m("c1ccncc1")) == {"dbe": 4.0, "nitrogen": 1, "nominal": 79, "nitrogen_rule": True}
    assert msinfo.rules(_m("CC(C)Cc1ccc(cc1)C(C)C(=O)O"))["dbe"] == 5.0
    assert msinfo.rules(_m("C[N+](C)(C)C")) is None


def test_formulas_that_fit_an_exact_mass():
    fit = msinfo.formulas_for(_m("OCC1OC(O)C(O)C(O)C1O"))  # glucose C6H12O6
    assert fit["candidates"][0]["formula"] == "C6H12O6" and fit["candidates"][0]["actual"]
    assert all(abs(c["ppm"]) <= 5 for c in fit["candidates"]) and fit["total"] >= 1


@pytest.mark.parametrize("smiles,expected,rule", [
    ("C=CC=C", 217, "diene"),               # butadiene, measured 217
    ("CC(=C)C(C)=C", 227, "diene"),         # 2,3-dimethylbutadiene, measured 226
    ("C1CC=CC=C1", 263, "diene"),           # homoannular 253 + 2 ring residues (measured 256)
    ("CC(C)=CC(C)=O", 239, "enone"),        # mesityl oxide, measured 237
    ("O=C1CCCC=C1", 227, "enone"),          # cyclohex-2-enone, measured 225
    ("O=C1CCC=C1", 214, "enone"),           # cyclopent-2-enone: 202 + beta ring residue 12
])
def test_woodward_fieser(smiles, expected, rule):
    r = uvvis.estimate(_m(smiles))
    assert r["rule"] == rule and r["lambda_max"] == expected
    assert sum(p["nm"] for p in r["parts"]) == pytest.approx(expected, abs=0.5)


def test_fieser_kuhn_for_beta_carotene():
    r = uvvis.estimate(_m("CC1=C(/C=C/C(C)=C/C=C/C(C)=C/C=C/C=C(C)/C=C/C=C(C)/C=C/C2=C(C)CCCC2(C)C)C(C)(C)CCC1"))
    assert r["rule"] == "polyene" and abs(r["lambda_max"] - 452) <= 3 and "coloured" in r["note"]


def test_no_rule_for_isolated_or_aromatic_chromophores():
    for smi in ("CC(C)=O", "c1ccccc1", "C1=CCC=CC1"):
        r = uvvis.estimate(_m(smi))
        assert r["rule"] is None and r["lambda_max"] is None and "do not apply" in r["note"]


def test_uv_kind_through_build():
    data, complete = spectra.build("CC(C)=CC(C)=O", "uv")
    assert complete and data["lambda_max"] == 239
