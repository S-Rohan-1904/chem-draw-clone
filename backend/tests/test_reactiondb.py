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
    build_reactions.build(build_reactions.read(HERE / "fixtures_reactions.rsmi", "uspto"), out, jobs=1)
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
        assert item["svg"].startswith("<svg") and item["ref_url"].startswith("https://patents.google.com/patent/US")
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


def test_reports_size_for_molecules_beyond_the_index(index):
    big = "CC(C)C[C@H](NC(=O)[C@H](CC(C)C)NC(=O)[C@H](CC(C)C)NC(=O)[C@H](CC(C)C)NC(=O)[C@H](CC(C)C)NC(=O)[C@H](CC(C)C)NC(=O)[C@H](CC(C)C)NC(=O)[C@H](CC(C)C)N)C(=O)O"
    r = reactiondb.lookup(big)
    assert r["uses"] == [] and r["heavy_atoms"] > r["max_atoms"] == 60


@pytest.fixture(scope="module")
def multi(tmp_path_factory):
    """USPTO fixture plus two CRD rows (one repeating a USPTO reaction) and two Rhea enzyme reactions."""
    out = tmp_path_factory.mktemp("rx") / "reactions.db"
    records = [
        *build_reactions.read(HERE / "fixtures_reactions.rsmi", "uspto"),
        *build_reactions.read(HERE / "fixtures_reactions_crd.tsv", "crd"),
        *build_reactions.read(HERE / "fixtures_reactions_rhea.tsv", "rhea"),
    ]
    index = build_reactions.build(records, out, jobs=1)
    old = os.environ.get("CHEM_REACTIONS_DB")
    os.environ["CHEM_REACTIONS_DB"] = str(out)
    reactiondb._connect.cache_clear()
    reactiondb._schema.cache_clear()
    yield index
    if old is None:
        os.environ.pop("CHEM_REACTIONS_DB", None)
    else:
        os.environ["CHEM_REACTIONS_DB"] = old
    reactiondb._connect.cache_clear()
    reactiondb._schema.cache_clear()


def test_sources_are_counted_once(multi):
    assert multi.stats["reactions_crd"] == 1, "the CRD row repeating a USPTO reaction is a duplicate"
    assert multi.stats["duplicates"] >= 1 and multi.stats["reactions_rhea"] >= 2


def test_crd_example_cites_the_dataset(multi):
    r = reactiondb.lookup("COc1ccc(Oc2ccc(OC)cc2)cc1")
    item = r["makes"][0]
    assert item["source"] == "crd" and item["ref_url"] == "https://doi.org/10.5281/zenodo.18109268"
    assert [s["licence"] for s in r["sources"]] == ["CC0", "CC BY 4.0", "CC BY 4.0"]


def test_enzyme_reactions_have_their_own_group(multi):
    ethanol = reactiondb.lookup("CCO")
    assert [x["label"] for x in ethanol["enzyme_uses"]] == ["Alcohol → Aldehyde"]
    item = ethanol["enzyme_uses"][0]
    assert item["ref_url"] == "https://www.rhea-db.org/rhea/25291" and item["ec"] == ["1.1.1.1"]
    assert item["products"] == ["CC=O"]
    # Rhea draws ions; the index stores neutral molecules, so glucose 6-phosphate is found as the acid.
    g6p = reactiondb.lookup("O=P(O)(O)OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O")
    assert g6p["enzyme_makes"] and not g6p["makes"]
    # ADP is a product of the hexokinase reaction too.
    adp = reactiondb.lookup("Nc1ncnc2c1ncn2[C@@H]1O[C@H](COP(=O)(O)OP(=O)(O)O)[C@@H](O)[C@H]1O")
    assert adp["enzyme_makes"]


def test_old_index_without_sources(monkeypatch, tmp_path):
    """The live index predates the extra sources (no source column, no groups) and must keep working."""
    import sqlite3

    path = tmp_path / "v1.db"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE mol (id INTEGER PRIMARY KEY, inchikey TEXT, skeleton TEXT, smiles TEXT);
        CREATE TABLE rxn (id INTEGER PRIMARY KEY, smiles TEXT, patent TEXT, year INTEGER, yield REAL);
        CREATE TABLE top (mol_id INTEGER, direction TEXT, rank INTEGER, label TEXT, count INTEGER, rxn_id INTEGER, centre TEXT);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        """
    )
    key = Chem.MolToInchiKey(Chem.MolFromSmiles("CCO"))
    con.execute("INSERT INTO mol VALUES (1, ?, ?, 'CCO')", (key, key[:14]))
    con.execute("INSERT INTO rxn VALUES (1, 'CCO.CC(=O)Cl>>CC(=O)OCC', 'US03930836', 1976, 80)")
    con.execute("INSERT INTO top VALUES (1, 'uses', 1, 'Alcohol → Ester', 3, 1, '1,2')")
    con.commit()
    con.close()
    monkeypatch.setenv("CHEM_REACTIONS_DB", str(path))
    reactiondb._connect.cache_clear()
    reactiondb._schema.cache_clear()
    try:
        r = reactiondb.lookup("CCO")
        assert [x["label"] for x in r["uses"]] == ["Alcohol → Ester"] and r["enzyme_uses"] == []
        assert r["uses"][0]["ref_url"] == "https://patents.google.com/patent/US3930836/en"
        assert [s["author"] for s in r["sources"]] == ["Daniel Lowe"]
    finally:
        reactiondb._connect.cache_clear()
        reactiondb._schema.cache_clear()


def test_builder_rejects_a_product_that_is_also_the_solvent():
    """CRD 504201 lists xylene as its product and as its solvent; the map from maleic anhydride is forced."""
    row = ("[O:9]=[C:10]1[CH:11]=[CH:1][C:13](=[O:14])[O:15]1>Cc1ccc(C)cc1.Cc1cccc(C)c1.Cc1ccccc1C>"
           "[CH3:1][c:2]1[cH:3][cH:4][cH:5][cH:6][c:7]1[CH3:8].[O:9]=[C:10]1[CH:11]=[CH:12][C:13](=[O:14])[O:15]1"
           "\t504201\t\t\t\t0.880")
    assert build_reactions.process(build_reactions.mapped_record(row, "crd")) == []


def test_named_change_ranks_before_others_seen_as_often(tmp_path):
    """Cyclohexanol: three types seen once each. Hydrogenating phenol comes first, then the
    formate (loses 2 atoms), then the benzyl ether (loses 7), not alphabetical order."""
    rows = [
        "c1ccc(C[O:1][CH:2]2[CH2:3][CH2:4][CH2:5][CH2:6][CH2:7]2)cc1>ClCCl.[Br-].[Li+].CC(=O)Br>"
        "[OH:1][CH:2]1[CH2:3][CH2:4][CH2:5][CH2:6][CH2:7]1\t1131409\t\t\t\t0.887",
        "O=C[O:1][CH:2]1[CH2:3][CH2:4][CH2:5][CH2:6][CH2:7]1>O.CC(C)=O>[OH:1][CH:2]1[CH2:3][CH2:4][CH2:5][CH2:6][CH2:7]1"
        "\t1311530\t\t\t\t0.867",
        "[OH:1][c:2]1[cH:3][cH:4][cH:5][cH:6][cH:7]1>[Pd]>[OH:1][CH:2]1[CH2:3][CH2:4][CH2:5][CH2:6][CH2:7]1\t1\t\t\t\t0.9",
    ]
    out = tmp_path / "reactions.db"
    build_reactions.build([build_reactions.mapped_record(r, "crd") for r in rows], out, jobs=1)
    import sqlite3

    labels = [r[0] for r in sqlite3.connect(out).execute(
        "SELECT label FROM top WHERE direction = 'makes' ORDER BY rank")]
    assert labels == ["Phenol → Alcohol", "Ester → Alcohol", "Ether → Alcohol"]


def test_every_stereoisomer_is_pooled(tmp_path, monkeypatch):
    """The professor's rule: show reactions of any stereochemistry, and say which rows are another's."""
    rows = [  # (R)-butan-2-ol by ketone reduction, butan-2-ol without stereo by ester hydrolysis
        "[CH3:1][C:2](=[O:3])[CH2:4][CH3:5]>[H][H]>[CH3:1][C@@H:2]([OH:3])[CH2:4][CH3:5]\t1\t\t\t\t0.9",
        "[CH3:1][CH:2]([O:3]C(C)=O)[CH2:4][CH3:5]>O>[CH3:1][CH:2]([OH:3])[CH2:4][CH3:5]\t2\t\t\t\t0.9",
    ]
    out = tmp_path / "reactions.db"
    build_reactions.build([build_reactions.mapped_record(r, "crd") for r in rows], out, jobs=1)
    monkeypatch.setenv("CHEM_REACTIONS_DB", str(out))
    reactiondb._connect.cache_clear()
    reactiondb._schema.cache_clear()
    try:
        r = reactiondb.lookup("C[C@@H](O)CC")  # (R)
        stereo = {x["label"]: x["other_stereo"] for x in r["makes"]}
        assert stereo == {"Ketone → Alcohol": False, "Ester → Alcohol": True} and r["stereo_ignored"]
        s = reactiondb.lookup("C[C@H](O)CC")  # (S): nothing of its own, both shown
        assert len(s["makes"]) == 2 and all(x["other_stereo"] for x in s["makes"])
        plain = reactiondb.lookup("CC(O)CC")  # no stereo given: the (R) record is found too
        assert {x["label"] for x in plain["makes"]} == {"Ketone → Alcohol", "Ester → Alcohol"}
    finally:
        reactiondb._connect.cache_clear()
        reactiondb._schema.cache_clear()


def test_hsdb_route_cites_pubchem_and_its_reference():
    ref = reactiondb.reference("hsdb", "702#15", "Kirk-Othmer Encyclopedia of Chemical Technology. 4th ed.; p. 820")
    assert ref["ref_label"] == "PubChem CID 702, citing Kirk-Othmer Encyclopedia of Chemical Technology. 4th ed."
    assert ref["ref_url"] == "https://pubchem.ncbi.nlm.nih.gov/compound/702#section=Methods-of-Manufacturing"
