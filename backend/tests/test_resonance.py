from app.resonance import resonance_forms, resonance_svgs


def test_kekule_and_charge_delocalisation():
    assert len(resonance_forms("c1ccccc1")) == 2
    assert len(resonance_forms("CC(=O)[O-]")) == 2
    assert len(resonance_forms("c1ccc2ccccc2c1")) == 3
    assert len(resonance_forms("[O-][N+](=O)c1ccccc1")) >= 3


def test_no_forms_for_saturated():
    assert resonance_forms("CCO") and len(resonance_forms("CCO")) == 1
    assert resonance_svgs("CCO") == []


def test_svgs_share_layout():
    forms = resonance_svgs("c1ccccc1")
    assert len(forms) == 2 and all("<svg" in f["svg"] for f in forms)
    assert forms[0]["svg"] != forms[1]["svg"]
