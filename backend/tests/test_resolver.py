import json

import httpx
import pytest

from app import chem, resolver

PPIX = "CC1=C(C2=CC3=NC(=CC4=NC(=CC5=C(C(=C(N5)C=C1N2)C=C)C)C(=C4CCC(=O)O)C)C(=C3C)CCC(=O)O)C=C"


def _mock(monkeypatch, handler):
    monkeypatch.setenv("CHEM_NAME_LOOKUP", "1")
    transport = httpx.MockTransport(handler)
    real = httpx.Client

    def client(**kw):
        kw["transport"] = transport
        return real(**kw)

    monkeypatch.setattr(resolver.httpx, "Client", client)


def _pubchem_ok(request: httpx.Request) -> httpx.Response:
    assert "pubchem" in request.url.host
    body = {"PropertyTable": {"Properties": [{"CID": 4971, "SMILES": PPIX}]}}
    return httpx.Response(200, text=json.dumps(body))


def test_pubchem_hit(monkeypatch):
    _mock(monkeypatch, _pubchem_ok)
    smiles, source, note = resolver.lookup("Protoporphyrin IX")
    assert smiles == PPIX and source == "pubchem" and "CID 4971" in note


def test_falls_back_to_cactus(monkeypatch):
    def handler(request):
        if "pubchem" in request.url.host:
            return httpx.Response(404, text=json.dumps({"Fault": {"Code": "PUGREST.NotFound"}}))
        return httpx.Response(200, text="OC(=O)C\n")

    _mock(monkeypatch, handler)
    assert resolver.lookup("something")[1:] == ("cactus", "'something' is not a systematic IUPAC name; structure taken from NCI CACTUS.")
    assert resolver.lookup("something")[0] == "OC(=O)C"


def test_none_when_both_miss(monkeypatch):
    _mock(monkeypatch, lambda r: httpx.Response(404, text="<h1>Page not found (404)</h1>"))
    assert resolver.lookup("Turcasarin") is None


def test_none_on_network_error(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("down")

    _mock(monkeypatch, handler)
    assert resolver.lookup("aspirin") is None


def test_invalid_smiles_rejected(monkeypatch):
    _mock(monkeypatch, lambda r: httpx.Response(200, text='{"PropertyTable":{"Properties":[{"CID":1,"SMILES":"not smiles("}]}}'))
    assert resolver.lookup("aspirin") is None


def test_disabled_by_env(monkeypatch):
    monkeypatch.setenv("CHEM_NAME_LOOKUP", "0")
    monkeypatch.setattr(resolver.httpx, "Client", lambda **kw: pytest.fail("network used"))
    assert resolver.lookup("aspirin") is None


def test_resolve_full_order(monkeypatch):
    _mock(monkeypatch, _pubchem_ok)
    assert chem.resolve("ethanol")[1] == "iupac"
    assert chem.resolve("CCO") == ("CCO", "smiles")
    r = chem.resolve_full("Protoporphyrin IX")
    assert r.source == "pubchem" and r.smiles == PPIX and r.warnings and "PubChem" in r.warnings[0]
    with pytest.raises(chem.ChemError):
        chem.resolve_full("Protoporphyrin IX", lookup=False)


def test_error_mentions_lookup(monkeypatch):
    _mock(monkeypatch, lambda r: httpx.Response(404))
    with pytest.raises(chem.ChemError, match="Not found in PubChem"):
        chem.resolve_full("Turcasarin")
    monkeypatch.setenv("CHEM_NAME_LOOKUP", "0")
    with pytest.raises(chem.ChemError) as e:
        chem.resolve_full("Turcasarin")
    assert "PubChem" not in str(e.value)
