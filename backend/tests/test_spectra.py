import httpx
import pytest
from rdkit import Chem

from app import spectra
from tests.test_api import client

ETHANOL_1H = """<cml xmlns="http://www.xml-cml.org/schema"><spectrum type="NMR"><peakList>
<peak xValue="1.185" atomRefs="a4"/><peak xValue="1.185" atomRefs="a5"/><peak xValue="1.185" atomRefs="a6"/>
<peak xValue="3.67" atomRefs="a7"/><peak xValue="3.67" atomRefs="a8"/><peak xValue="4.21" atomRefs="a9"/>
</peakList></spectrum></cml>"""
ETHANOL_13C = """<cml xmlns="http://www.xml-cml.org/schema"><spectrum type="NMR"><peakList>
<peak xValue="18.16" atomRefs="a1"/><peak xValue="58.64" atomRefs="a2"/></peakList></spectrum></cml>"""

JCAMP_XY = """##TITLE=test
##JCAMP-DX=4.24
##XUNITS=1/CM
##YUNITS=ABSORBANCE
##XFACTOR=1.0
##YFACTOR=0.5
##FIRSTX=1000.0
##LASTX=1004.0
##NPOINTS=5
##XYDATA=(X++(Y..Y))
1000.0 0.0 2.0 0.0
1003.0 0.0 0.0
##END=
"""
JCAMP_PAIRS = """##TITLE=ms
##DATA TYPE=MASS SPECTRUM
##NPOINTS=3
##PEAK TABLE=(XY..XY)
31,999 45,500
46,200
##END=
"""


def peaks(smiles, kind):
    return spectra.nmr_local(Chem.MolFromSmiles(smiles))[kind]["peaks"]


def test_ethanol_1h_signals():
    h = peaks("CCO", "h")
    assert [(p["integration"], p["multiplicity"]) for p in sorted(h, key=lambda p: p["shift"])] == [(3, "t"), (1, "s"), (2, "q")]
    assert len(peaks("CCO", "c")) == 2


def test_symmetry_counts():
    assert len(peaks("c1ccccc1", "h")) == 1 and len(peaks("c1ccccc1", "c")) == 1
    h = peaks("CC(C)(C)O", "h")
    assert sorted(p["integration"] for p in h) == [1, 9]
    assert all(p["multiplicity"] == "s" for p in h)


def test_shift_regions():
    h = {p["label"]: p["shift"] for p in peaks("CC(=O)O", "h")}
    assert h["COOH"] > 10 and 1.8 < h["CH3-C=O"] < 2.6
    c = {p["label"]: p["shift"] for p in peaks("CC(=O)C", "c")}
    assert 190 < c["C=O (ketone)"] < 220
    ald = peaks("O=Cc1ccccc1", "h")
    assert any(p["label"] == "CHO" and 9 < p["shift"] < 10.5 for p in ald)


def test_ir_bands():
    names = lambda smi: {b["name"] for b in spectra.ir_bands(Chem.MolFromSmiles(smi))}
    eth = names("CCO")
    assert "O-H stretch (alcohol)" in eth and "C-O stretch (alcohol)" in eth
    ace = names("CC(=O)C")
    assert "C=O stretch (ketone)" in ace and not any(n.startswith("O-H") for n in ace)
    assert "C#N stretch (nitrile)" in names("N#Cc1ccccc1")
    band = next(b for b in spectra.ir_bands(Chem.MolFromSmiles("CC(=O)C")) if b["name"].startswith("C=O"))
    assert 1705 <= band["low"] and band["high"] <= 1725 and band["atoms"] == [0, 1, 2, 3]


def test_isotope_patterns():
    iso = {p["nominal"]: p["rel"] for p in spectra.ms_predict(Chem.MolFromSmiles("c1ccccc1Cl"))["isotopes"]}
    assert iso[112] == 100 and 30 < iso[114] < 34
    iso = {p["nominal"]: p["rel"] for p in spectra.ms_predict(Chem.MolFromSmiles("c1ccccc1Br"))["isotopes"]}
    assert 95 < iso[158] <= 100
    ms = spectra.ms_predict(Chem.MolFromSmiles("CCO"))
    assert ms["nominal_mass"] == 46 and abs(ms["exact_mass"] - 46.0419) < 0.001


def test_fragments():
    frags = {f["nominal"]: f for f in spectra.ms_predict(Chem.MolFromSmiles("Cc1ccccc1"))["fragments"]}
    assert 77 in frags
    acetone = {f["nominal"]: f for f in spectra.ms_predict(Chem.MolFromSmiles("CC(=O)C"))["fragments"]}
    assert acetone[43]["formula"] == "C2H3O+" and "acylium" in acetone[43]["why"]
    ethanol = {f["nominal"]: f for f in spectra.ms_predict(Chem.MolFromSmiles("CCO"))["fragments"]}
    assert ethanol[31]["formula"] == "CH3O+"


def test_parse_jcamp_xy_and_pairs():
    d = spectra.parse_jcamp(JCAMP_XY)
    assert d["x"] == [1000.0, 1001.0, 1002.0, 1003.0, 1004.0]
    assert d["y"] == [0.0, 1.0, 0.0, 0.0, 0.0]
    assert d["headers"]["YUNITS"] == "ABSORBANCE"
    d = spectra.parse_jcamp(JCAMP_PAIRS)
    assert list(zip(d["x"], d["y"])) == [(31.0, 999.0), (45.0, 500.0), (46.0, 200.0)]


def test_nmrshiftdb_atom_mapping():
    mol = Chem.MolFromSmiles("CCO")
    refs = spectra.map_atom_refs(mol)
    assert refs["a1"] == (0, 0) and refs["a3"] == (2, 2)
    assert refs["a4"] == (-1, 0) and refs["a6"] == (-1, 0) and refs["a7"] == (-1, 1) and refs["a9"] == (-1, 2)
    merged = spectra.merge_nmrshiftdb(spectra.nmr_local(mol), ETHANOL_1H, ETHANOL_13C, mol)
    assert merged["source"] == "nmrshiftdb2"
    h = {p["label"]: p["shift"] for p in merged["h"]["peaks"]}
    assert h["CH3"] == 1.19 and h["CH2-O"] == 3.67 and h["OH"] == 4.21
    c = sorted(p["shift"] for p in merged["c"]["peaks"])
    assert c == [18.2, 58.6]


def _mock(monkeypatch, handler):
    monkeypatch.setenv("CHEM_SPECTRA_LOOKUP", "1")
    transport = httpx.MockTransport(handler)
    real = httpx.Client
    monkeypatch.setattr(spectra.httpx, "Client", lambda **kw: real(transport=transport, **{k: v for k, v in kw.items() if k != "transport"}))


def test_nmr_falls_back_to_rules_when_service_down(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("down")

    _mock(monkeypatch, handler)
    data, complete = spectra.nmr("CCO")
    assert data["source"] == "rules" and complete is False


def test_nist_lookup_and_caching(monkeypatch):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        url = str(request.url)
        if "InChI=" in url:
            return httpx.Response(200, text='<a href="/cgi/cbook.cgi?ID=C999&amp;Units=SI">x</a> <a href="/cgi/cbook.cgi?ID=C64175&amp;Units=SI&amp;Mask=80#IR-Spec">IR</a>')
        if "Type=IR" in url and "Index=0" in url:
            return httpx.Response(200, text="##TITLE=img\n##NPOINTS=0\n##END=\n")
        if "Type=IR" in url:
            return httpx.Response(200, text=JCAMP_XY)
        if "Type=Mass" in url:
            return httpx.Response(200, text=JCAMP_PAIRS)
        return httpx.Response(404)

    _mock(monkeypatch, handler)
    ir, complete = spectra.build("CCO", "ir")
    assert complete and ir["experimental"]["x"][0] == 1000.0
    assert ir["experimental"]["y"][1] == pytest.approx(0.1, abs=1e-4)  # absorbance 1.0 -> transmittance 0.1
    assert "C64175" in ir["experimental"]["url"]
    ms, complete = spectra.build("CCO", "ms")
    assert complete and ms["experimental"]["peaks"][0] == {"mz": 31.0, "rel": 100.0}


    with client:
        r1 = client.post("/api/molecule/spectra", json={"smiles": "CCO", "kind": "ir"}).json()
        r2 = client.post("/api/molecule/spectra", json={"smiles": "CCO", "kind": "ir"}).json()
    assert r1["cached"] is False and r2["cached"] is True and r2["experimental"]["x"] == r1["experimental"]["x"]


def test_incomplete_not_cached(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("down")

    _mock(monkeypatch, handler)

    with client:
        r1 = client.post("/api/molecule/spectra", json={"smiles": "CC(=O)C", "kind": "ms"}).json()
        r2 = client.post("/api/molecule/spectra", json={"smiles": "CC(=O)C", "kind": "ms"}).json()
    assert r1["experimental"] is None and r1["cached"] is False and r2["cached"] is False
