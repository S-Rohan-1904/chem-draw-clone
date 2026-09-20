import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.chem import ChemError, build, variant_smiles  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def test_mirror_gives_enantiomer():
    r = build("(2R)-butan-2-ol")
    m = build(variant_smiles(r.smiles, "mirror"))
    assert m.stereo.centers[0].label == "S"
    assert m.inchikey.split("-")[0] == r.inchikey.split("-")[0] and m.inchikey != r.inchikey


def test_invert_one_centre_gives_diastereomer():
    r = build("(2R,3R)-2,3-dihydroxybutanedioic acid")
    c = r.stereo.centers[0]
    d = build(variant_smiles(r.smiles, "invert", c.atom_idx))
    labels = sorted(x.label for x in d.stereo.centers)
    assert labels == ["R", "S"]  # meso-tartaric acid
    assert build(variant_smiles(r.smiles, "mirror")).stereo.centers[0].label == "S"


def test_mirror_keeps_ez():
    r = build("(2E,4R)-4-methylhex-2-ene")
    m = build(variant_smiles(r.smiles, "mirror"))
    assert m.stereo.double_bonds[0].label == "E" and m.stereo.centers[0].label == "S"


def test_variant_errors():
    with pytest.raises(ChemError):
        variant_smiles("CCO", "mirror")
    with pytest.raises(ChemError):
        variant_smiles("C[C@H](O)CC", "invert", 0)


def test_variant_endpoint():
    with client:
        base = client.post("/api/molecule", json={"input": "(2S)-butan-2-ol"}).json()
        r = client.post("/api/molecule/variant", json={"smiles": base["smiles"], "op": "mirror"})
        assert r.status_code == 200 and r.json()["stereo"]["centers"][0]["label"] == "R"
        assert client.post("/api/molecule/variant", json={"smiles": "CCO", "op": "mirror"}).status_code == 400
