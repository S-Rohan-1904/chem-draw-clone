from rdkit import Chem

from app import couplings, msfrag, spectra


def _h(smi):
    return spectra.nmr_local(Chem.MolFromSmiles(smi))["h"]["peaks"]


def _mult(smi, label):
    return next(p for p in _h(smi) if p["label"] == label)


def test_ethanol_triplet_quartet_with_7hz():
    peaks = {p["multiplicity"]: p for p in _h("CCO")}
    assert peaks["q"]["couplings"] == [{"J": 7.0, "n": 3, "atoms": [0]}]
    assert peaks["t"]["couplings"][0]["n"] == 2
    assert peaks["s"]["exchangeable"] and peaks["s"]["couplings"] == []


def test_trans_alkene_16hz_and_dq():
    peaks = _h("C/C=C/C(=O)O")
    by_shift = sorted(peaks, key=lambda p: -p["shift"])
    vinyl_a, vinyl_b = by_shift[1], by_shift[2]
    assert vinyl_a["multiplicity"] == "d" and vinyl_a["couplings"][0]["J"] == 16.0
    assert vinyl_b["multiplicity"] == "dq"
    assert [c["J"] for c in vinyl_b["couplings"]] == [16.0, 7.0]


def test_terminal_alkene_cis_trans_split():
    p = max(_h("C=CC(=O)OC"), key=lambda p: p["shift"])
    assert p["multiplicity"] == "dd"
    assert [c["J"] for c in p["couplings"]] == [16.0, 10.5]


def test_aromatic_ortho_meta_and_isopropyl_septet():
    ar = _h("c1ccccc1C(=O)C")
    assert any(p["multiplicity"] == "dd" and [c["J"] for c in p["couplings"]] == [8.0, 2.0] for p in ar)
    ipr = _h("CC(C)Br")
    assert any(p["multiplicity"] == "sept" and p["couplings"][0]["n"] == 6 for p in ipr)


def test_aldehyde_small_coupling_and_ring_tt():
    ald = _h("CC=O")
    assert max(ald, key=lambda p: p["shift"])["couplings"][0]["J"] == 2.5
    ring = max(_h("C1CCCCC1O"), key=lambda p: p["shift"] if not p["exchangeable"] else 0)
    assert ring["multiplicity"] == "tt"
    assert ring["couplings"][0]["J"] > 10 and ring["couplings"][1]["J"] < 6


def test_pattern_merges_and_collapses_to_m():
    sym, merged = couplings.pattern([{"J": 7.2, "n": 2, "atoms": [1]}, {"J": 6.8, "n": 3, "atoms": [2]}])
    assert sym == "sext" and merged[0]["n"] == 5
    sym, _ = couplings.pattern([{"J": 9, "n": 1, "atoms": []}, {"J": 6, "n": 1, "atoms": []}, {"J": 4, "n": 1, "atoms": []}, {"J": 2, "n": 1, "atoms": []}])
    assert sym == "m"


def _tree(smi):
    return msfrag.tree(Chem.MolFromSmiles(smi))["nodes"]


def test_tree_root_and_ids():
    nodes = _tree("CCCCO")
    assert nodes[0]["parent"] == -1 and nodes[0]["formula"] == "C4H10O+•" and nodes[0]["nominal"] == 74
    assert [n["id"] for n in nodes] == list(range(len(nodes)))
    assert all(n["parent"] < n["id"] for n in nodes[1:])


def test_mclafferty_and_water_loss():
    hexanone = _tree("CCCCC(=O)C")
    mcl = next(n for n in hexanone if "McLafferty" in n["why"])
    assert mcl["nominal"] == 58 and mcl["formula"] == "C3H6O+•" and mcl["loss"] == "C3H6"
    butanol = _tree("CCCCO")
    dehydr = next(n for n in butanol if n["loss"] == "H2O")
    assert dehydr["nominal"] == 56 and len(dehydr["atoms"]) == 4


def test_secondary_steps():
    acetophenone = _tree("CC(=O)c1ccccc1")
    benzoyl = next(n for n in acetophenone if n["nominal"] == 105)
    phenyl = next(n for n in acetophenone if n["parent"] == benzoyl["id"])
    assert phenyl["nominal"] == 77 and phenyl["loss"] == "CO"
    ethylbenzene = _tree("CCc1ccccc1")
    trop = next(n for n in ethylbenzene if n["nominal"] == 91)
    assert "tropylium" in trop["why"]
    assert any(n["parent"] == trop["id"] and n["nominal"] == 65 for n in ethylbenzene)
    # No CH3+ from acylium - CO
    assert not any(n["loss"] == "CO" and n["nominal"] == 15 for n in _tree("CCCCC(=O)C"))


def test_chlorine_isotopes_and_svgs():
    nodes = _tree("CCCl")
    m = nodes[0]
    assert [p["nominal"] for p in m["isotopes"]] == [64, 66] and abs(m["isotopes"][1]["rel"] - 32) < 1
    frag = next(n for n in nodes if n["formula"] == "CH2Cl+")
    assert frag["isotopes"][1]["nominal"] == 51
    assert frag["svg"].startswith("<?xml") or "<svg" in frag["svg"]
    assert nodes[0]["svg"] == ""


def test_ms_payload_includes_tree():
    data = spectra.ms_predict(Chem.MolFromSmiles("CC(=O)C"))
    assert data["tree"][0]["formula"] == "C3H6O+•"
    assert any(n["nominal"] == 43 for n in data["tree"])
