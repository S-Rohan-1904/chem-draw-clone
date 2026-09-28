import importlib.util
import os
import tempfile
from collections import Counter
from pathlib import Path

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from rdkit import Chem  # noqa: E402

from app import reactiondb  # noqa: E402
from app.main import app  # noqa: E402

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("build_reactions", HERE.parent / "scripts" / "build_reactions.py")
build_reactions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_reactions)

BENZALDEHYDE = "O=Cc1ccccc1"
CYCLOHEXANONE = "O=C1CCCCC1"


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    """A small index built by the real builder from 88 real USPTO rows (tests/fixtures_reactions.rsmi)."""
    out = tmp_path_factory.mktemp("rx") / "reactions.db"
    with open(HERE / "fixtures_reactions.rsmi", encoding="utf-8") as f:
        build_reactions.build(f, out, jobs=1)
    old = os.environ.get("CHEM_REACTIONS_DB")
    os.environ["CHEM_REACTIONS_DB"] = str(out)
    reactiondb._connect.cache_clear()
    yield out
    if old is None:
        os.environ.pop("CHEM_REACTIONS_DB", None)
    else:
        os.environ["CHEM_REACTIONS_DB"] = old
    reactiondb._connect.cache_clear()


def _heavy(smiles: str) -> Counter:
    m = Chem.MolFromSmiles(smiles)
    return Counter(a.GetSymbol() for a in m.GetAtoms())


def test_benzaldehyde_uses_keep_the_ring(index):
    r = reactiondb.lookup(BENZALDEHYDE)
    assert r["available"] and 0 < len(r["uses"]) <= 5
    labels = [x["label"] for x in r["uses"]]
    assert all(lab.startswith("Aldehyde") for lab in labels)
    assert any(lab in ("Aldehyde → Amine", "Aldehyde → Alkene", "Aldehyde → Imine") for lab in labels)
    ring = Chem.MolFromSmarts("c1ccccc1")
    # The source is text-mined: one fixture record draws the product with the ring broken
    # (US03950565), so allow a single bad example rather than all-or-nothing.
    kept = sum(Chem.MolFromSmiles(item["products"][0]).HasSubstructMatch(ring) for item in r["uses"])
    assert kept >= len(r["uses"]) - 1
    for item in r["uses"]:
        assert item["svg"].startswith("<svg") and item["patent_url"].startswith("https://patents.google.com/patent/US")
        assert item["atoms"], "reacting atoms map onto the user's molecule"


def test_ranked_by_count(index):
    r = reactiondb.lookup(CYCLOHEXANONE)
    counts = [x["count"] for x in r["uses"]]
    assert counts == sorted(counts, reverse=True)


def test_cyclohexanone_makes_never_isopropanol(index):
    r = reactiondb.lookup(CYCLOHEXANONE)
    assert r["makes"]
    for item in r["makes"]:
        assert "CC(C)O" not in item["reactants"]
        assert item["products"][0] == Chem.MolToSmiles(Chem.MolFromSmiles(CYCLOHEXANONE))


def test_product_atoms_come_from_the_reaction(index):
    """Every heavy atom in the example product is accounted for by reactants and agents (no invented atoms)."""
    for smi in (BENZALDEHYDE, CYCLOHEXANONE):
        r = reactiondb.lookup(smi)
        for item in r["uses"] + r["makes"]:
            supply = Counter()
            for s in item["reactants"] + item["agents"]:
                supply += _heavy(s)
            need = _heavy(item["products"][0])
            assert all(supply[el] >= n or el in ("H",) for el, n in need.items()), item["smiles"]


def test_unknown_molecule_is_empty(index):
    r = reactiondb.lookup("CC(C)(C)C(C)(C)C(C)(C)C1CC1")
    assert r["available"] and r["uses"] == [] and r["makes"] == []


def test_missing_index(monkeypatch, tmp_path):
    monkeypatch.setenv("CHEM_REACTIONS_DB", str(tmp_path / "absent.db"))
    reactiondb._connect.cache_clear()
    try:
        assert reactiondb.lookup(BENZALDEHYDE)["available"] is False
    finally:
        reactiondb._connect.cache_clear()


def test_patent_urls():
    assert reactiondb.patent_url("US03930836") == "https://patents.google.com/patent/US3930836/en"
    assert reactiondb.patent_url("US09450188B2") == "https://patents.google.com/patent/US9450188B2/en"
    assert reactiondb.patent_url("USRE038551E1") == "https://patents.google.com/patent/USRE38551E1/en"


def test_endpoint(index):
    with TestClient(app) as client:
        r = client.post("/api/analysis/reactions", json={"smiles": BENZALDEHYDE})
        assert r.status_code == 200 and r.json()["uses"]
        assert client.post("/api/analysis/reactions", json={"smiles": "not a molecule"}).status_code == 400


def test_classify_describes_group_change():
    with TestClient(app) as client:
        r = client.post("/api/analysis/classify", json={"reactants": ["CC(=O)O", "CCO"], "products": ["CC(=O)OCC"]}).json()
        assert "esterification" in r["guess"] and "Ester (1)" in r["groups_gained"]


def test_builder_rejects_inconsistent_atom_maps():
    """Rows whose map numbers repeat or change element are text-mining errors (seen in the real set)."""
    good = "[CH3:1][OH:2].[CH3:3][C:4](Cl)=[O:5]>>[CH3:3][C:4](=[O:5])[O:2][CH3:1]\tUS01\t\t2000\t\t"
    repeated = "[CH3:1][OH:2].[CH3:3][C:4](Cl)=[O:5]>>[CH3:3][C:4](=[O:5])[O:2][CH3:1].[CH3:1][OH:2]\tUS02\t\t2000\t\t"
    element = "[CH3:1][OH:2].[CH3:3][C:4](Cl)=[O:5]>>[CH3:3][C:4](=[O:5])[N:2][CH3:1]\tUS03\t\t2000\t\t"
    assert build_reactions.process_line(good) is not None
    assert build_reactions.process_line(repeated) is None
    assert build_reactions.process_line(element) is None


def test_stereo_fallback_only_for_stereo_molecules(index):
    # (R)- and (S)-benzaldehyde cyanohydrin do not exist in the fixture; an achiral molecule never falls back.
    r = reactiondb.lookup(BENZALDEHYDE)
    assert r["stereo_ignored"] is False
