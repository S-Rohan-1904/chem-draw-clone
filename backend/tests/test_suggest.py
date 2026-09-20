import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import opsin, suggest  # noqa: E402
from app.chem import normalise_name, resolve_full  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.mark.parametrize(
    "typo,expected",
    [
        ("2-metylpropane", "2-methylpropane"),
        ("ethly acetate", "ethyl acetate"),
        ("benzoic acd", "benzoic acid"),
        ("1-brmo-2-chlorobenzene", "1-bromo-2-chlorobenzene"),
        ("tolune", "toluene"),
        ("ibuprofn", "ibuprofen"),
        ("cyclohexanole", "cyclohexanol"),
        ("ethanoic acide", "ethanoic acid"),
        ("2-methly-butan-1-ol", "2-methyl-butan-1-ol"),
    ],
)
def test_typo_suggestions(typo, expected):
    smi, err = opsin.strict.convert(typo)
    assert not smi
    d = suggest.diagnose(typo, err)
    assert expected in d.suggestions, d
    assert d.reason.startswith("Could not understand")


def test_highlight_span_points_at_bad_fragment():
    _, err = opsin.strict.convert("2-metylpropane")
    d = suggest.diagnose("2-metylpropane", err)
    assert d.highlight == (2, 14)


def test_normalisation():
    assert normalise_name("butan‐2‐ol.") == "butan-2-ol"
    assert normalise_name("“(E)-but-2-ene”") == "(E)-but-2-ene"
    assert normalise_name("  ethanoic   acid , ") == "ethanoic   acid".replace("   ", " ")


def test_bad_stereo_builds_with_warning():
    r = resolve_full("(2R)-propan-2-ol")
    assert r.smiles and r.warnings and "not a stereocentre" in r.warnings[0]
    assert not resolve_full("(2R)-butan-2-ol").warnings


def test_impossible_locant_message():
    _, err = opsin.strict.convert("hexane-7-ol")
    d = suggest.diagnose("hexane-7-ol", err)
    assert "locant 7" in d.reason.lower() or "7" in d.reason


def test_api_error_body_has_suggestions():
    with client:
        r = client.post("/api/molecule", json={"input": "2-metylpropane"})
        assert r.status_code == 400
        body = r.json()
        assert body["highlight"] == [2, 14]
        assert "2-methylpropane" in body["suggestions"]
        assert body["detail"].startswith("Could not understand")


def test_check_and_autocomplete():
    with client:
        assert client.post("/api/molecule/check", json={"input": "ethanol"}).json()["ok"] is True
        bad = client.post("/api/molecule/check", json={"input": "ethanl"}).json()
        assert bad["ok"] is False and bad["reason"]
        warn = client.post("/api/molecule/check", json={"input": "(2R)-propan-2-ol"}).json()
        assert warn["ok"] is True and warn["warnings"]
        names = client.get("/api/molecule/suggest", params={"q": "cyclohex"}).json()["names"]
        assert names and all("cyclohex" in n.lower() for n in names)
        # previously built names show up in autocomplete
        client.post("/api/molecule", json={"input": "(3R)-3-methylhexane"})
        assert "(3R)-3-methylhexane" in client.get("/api/molecule/suggest", params={"q": "(3R)-3-m"}).json()["names"]


def test_opsin_process_concurrency():
    from concurrent.futures import ThreadPoolExecutor

    names = ["ethanol", "propane", "benzene", "(2R)-butan-2-ol", "toluene", "phenol"] * 8
    ref = {n: opsin.strict.convert(n)[0] for n in set(names)}
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda n: (n, opsin.strict.convert(n)[0]), names))
    assert all(ref[n] == s for n, s in results)


def test_opsin_process_restarts_after_crash():
    assert opsin.strict.convert("ethanol")[0]
    opsin.strict._proc.kill()
    assert opsin.strict.convert("propane")[0] == "CCC"
