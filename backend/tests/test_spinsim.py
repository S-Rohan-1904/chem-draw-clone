import pytest

from app import spectra, spinsim


def _at(lines, field):
    return [(round(p * field, 1), w) for p, w in lines]


def test_ethyl_group_is_a_triplet_and_quartet_at_high_field():
    hs = {0: 3.6, 1: 3.6, 2: 1.2, 3: 1.2, 4: 1.2}
    j = {(a, b): 7.0 for a in (0, 1) for b in (2, 3, 4)}
    sim = spinsim.simulate(hs, j, [], {})
    lines = sim["lines"]["600"]
    assert sum(w for _, w in lines) == pytest.approx(5.0, abs=0.01)  # each proton counts once
    ch3 = {}
    for f, w in _at(lines, 600):
        if f < 1000:
            ch3[round(f)] = ch3.get(round(f), 0) + w
    assert list(ch3) == [713, 720, 727] and ch3[720] / ch3[713] == pytest.approx(2.0, rel=0.05)
    assert sim["exact"] and sim["largest"] == 5


def test_close_pair_roofs_at_low_field():
    sim = spinsim.simulate({0: 4.0, 1: 4.1}, {(0, 1): 10.0}, [], {})
    low = [w for _, w in sim["lines"]["60"]]   # 6 Hz apart, J = 10 Hz: strongly second order
    high = [w for _, w in sim["lines"]["600"]]  # 60 Hz apart: nearly first order
    assert len(low) == 4 and low[1] / low[0] > 10
    assert high[1] / high[0] < 1.5


def test_big_coupled_groups_fall_back_to_first_order():
    n = spinsim.MAX_SPINS + 2
    hs = {i: 1.0 + 0.1 * i for i in range(n)}
    j = {(i, i + 1): 7.0 for i in range(n - 1)}
    sim = spinsim.simulate(hs, j, [(11.0, 1)], {i: [{"J": 7.0, "n": 1}] for i in range(n)})
    assert not sim["exact"] and sim["largest"] == n and sim["broad"] == [[11.0, 1]]
    assert sum(w for _, w in sim["lines"]["400"]) == pytest.approx(n, abs=0.05)


def test_nmr_payload_has_dept_counts_2d_and_simulation():
    data, _ = spectra.nmr("CCOC(C)=O")  # ethyl acetate
    hs = sorted(p["hs"] for p in data["c"]["peaks"])
    assert hs == [0, 2, 3, 3]
    hp, cp = data["h"]["peaks"], data["c"]["peaks"]
    corr = data["correlations"]
    label = {i: p["label"] for i, p in enumerate(hp)}
    assert [(label[a], label[b]) for a, b in corr["cosy"]] in ([("CH2-O", "CH3")], [("CH3", "CH2-O")])
    assert len(corr["hsqc"]) == 3  # three protonated carbons, each with its own protons
    carbonyl = next(i for i, p in enumerate(cp) if p["hs"] == 0)
    assert {label[h] for c, h in corr["hmbc"] if c == carbonyl} == {"CH3-C=O", "CH2-O"}  # 2 and 3 bonds away
    sim = data["simulation"]
    assert sim["exact"] and set(sim["lines"]) == {"60", "100", "300", "400", "600"}
    assert all("_hs" not in p for p in hp)
