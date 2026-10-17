"""Reviewed textbook routes: the curated file, the review sheet, the builder's curated group and the lookup."""

import csv
import importlib.util
import os
import sqlite3
from pathlib import Path

import pytest

from app import curated, reactiondb

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
REVIEW_SHEET = BACKEND.parent / "docs" / "curated" / "made_by_review.csv"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, BACKEND / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build_reactions = _load("build_reactions")
curated_reactions = _load("curated_reactions")

MESO = "C[C@H](Br)[C@@H](C)Br"
RR = "C[C@@H](Br)[C@@H](C)Br"
PLAIN = "CC(Br)C(C)Br"


def _route(**kw) -> dict:
    row = {"id": "T1", "kind": "route", "name": "meso-2,3-dibromobutane", "product_smiles": MESO,
           "reaction_smiles": f"C/C=C/C.BrBr>ClCCl>{MESO}", "reference": "Clayden, Organic Chemistry, 2nd ed.",
           "note": "Anti addition to trans-but-2-ene gives the meso dibromide.", "reviewed_by": "A Reviewer",
           "reviewed_on": "2026-10-17"}
    return row | kw


def test_a_correct_route_passes():
    assert curated.problems(_route()) == []


def test_the_product_must_be_the_exact_stereoisomer():
    # cis-but-2-ene gives the racemic (2R,3R)/(2S,3S) pair, not the meso compound
    found = curated.problems(_route(reaction_smiles=f"C/C=C\\C.BrBr>>{RR}"))
    assert any("not among the products" in p for p in found)


def test_rows_are_checked_for_signature_text_and_atoms():
    assert any("reviewed_by" in p for p in curated.problems(_route(reviewed_by="")))
    assert any("semicolon" in p for p in curated.problems(_route(note="Anti addition; meso")))
    assert any("long dash" in p for p in curated.problems(_route(note="Anti addition – meso")))
    assert any("supplies Br" in p for p in curated.problems(_route(reaction_smiles=f"C/C=C/C>>{MESO}")))
    assert any("does not parse" in p for p in curated.problems(_route(reaction_smiles="C/C=C/C.BrBr>>C(Br")))
    assert curated.problems(_route(kind="maybe"))


def test_no_preparation_rows_need_a_note_and_no_reaction():
    row = _route(kind="no_preparation", reaction_smiles="", product_smiles="CCC[C@H](C)CC", reference="",
                 note="A branched alkane used as a naming example.")
    assert curated.problems(row) == []
    assert curated.problems(row | {"note": ""})
    assert curated.problems(row | {"reaction_smiles": f"C/C=C/C.BrBr>>{MESO}"})


def test_the_curated_file_in_the_repo_is_valid():
    rows = curated.read(curated.DEFAULT_PATH)
    with open(curated.DEFAULT_PATH, encoding="utf-8") as f:
        assert f.readline().rstrip("\n").split("\t") == curated.FIELDS
    for row in rows:
        assert curated.problems(row) == [], row["id"]
    assert len({r["id"] for r in rows}) == len(rows)


@pytest.mark.skipif(not REVIEW_SHEET.exists(), reason="review sheet is in docs/, outside the backend image")
def test_the_review_sheet_drafts_are_well_formed(capsys):
    rows = curated_reactions.read_review(REVIEW_SHEET)
    assert rows and curated_reactions.check(rows) == 0, capsys.readouterr().out
    assert {r["kind"] for r in rows} == {"route", "no_preparation"}


def _sheet(tmp_path: Path, verdicts: list[tuple[str, str]]) -> Path:
    """A review sheet with the meso route and a no_preparation row, verdicts as given."""
    rows = [
        {"id": "R1", "target_name": "meso-2,3-dibromobutane", "target_smiles": MESO, "kind": "route",
         "reaction_smiles": f"C/C=C/C.BrBr>ClCCl>{MESO}", "stereo_note": "Anti addition gives the meso isomer.",
         "reference": "Clayden, Organic Chemistry, 2nd ed.", "card_note": ""},
        {"id": "R2", "target_name": "(3R)-3-methylhexane", "target_smiles": "CCC[C@H](C)CC", "kind": "no_preparation",
         "reaction_smiles": "", "stereo_note": "", "reference": "", "card_note": "A branched alkane used as a naming example."},
        {"id": "R3", "target_name": "wrong stereo", "target_smiles": MESO, "kind": "route",
         "reaction_smiles": f"C/C=C\\C.BrBr>>{RR}", "stereo_note": "", "reference": "x", "card_note": ""},
    ]
    file = tmp_path / "review.csv"
    with open(file, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) + ["verdict", "reviewer"])
        w.writeheader()
        for row, (verdict, reviewer) in zip(rows, verdicts):
            w.writerow(row | {"verdict": verdict, "reviewer": reviewer})
    return file


def test_accept_copies_only_rows_marked_right(tmp_path):
    out = tmp_path / "curated.tsv"
    sheet = _sheet(tmp_path, [("right", "A Reviewer"), ("wrong", "A Reviewer"), ("", "")])
    added, kept, issues = curated_reactions.accept(curated_reactions.read_review(sheet), out)
    assert (added, kept, issues) == (1, 0, [])
    rows = curated.read(out)
    assert [r["id"] for r in rows] == ["R1"]
    assert rows[0]["note"] == "Anti addition gives the meso isomer." and rows[0]["reviewed_by"] == "A Reviewer"
    # a second run adds nothing
    assert curated_reactions.accept(curated_reactions.read_review(sheet), out)[:2] == (0, 1)


def test_accept_refuses_unsigned_and_wrong_rows(tmp_path):
    out = tmp_path / "curated.tsv"
    sheet = _sheet(tmp_path, [("right", ""), ("yes", "A Reviewer"), ("right", "A Reviewer")])
    added, _, issues = curated_reactions.accept(curated_reactions.read_review(sheet), out)
    assert added == 1 and [r["id"] for r in curated.read(out)] == ["R2"]
    assert len(issues) == 2 and issues[0].startswith("R1") and "reviewed_by" in issues[0]
    assert "not among the products" in issues[1]


# --- the curated group in the index --------------------------------------------------------------

@pytest.fixture(scope="module")
def index(tmp_path_factory):
    """An index built by the real builder from RXNMapper output for three reviewed routes
    (tests/fixtures_reactions_curated.tsv, mapped from tests/fixtures_curated.tsv) and two
    Wikipedia equations for 2,3-dibromobutane, one the same reaction as a reviewed route."""
    out = tmp_path_factory.mktemp("rx") / "reactions.db"
    records = [*build_reactions.read(HERE / "fixtures_reactions_wiki_dibromide.tsv", "wiki"),
               *build_reactions.read(HERE / "fixtures_reactions_curated.tsv", "curated")]
    built = build_reactions.build(iter(records), out, jobs=1)
    saved = {k: os.environ.get(k) for k in ("CHEM_REACTIONS_DB", "CHEM_CURATED_REACTIONS")}
    os.environ["CHEM_REACTIONS_DB"] = str(out)
    os.environ["CHEM_CURATED_REACTIONS"] = str(HERE / "fixtures_curated.tsv")
    reactiondb._connect.cache_clear()
    reactiondb._schema.cache_clear()
    yield out, built
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    reactiondb._connect.cache_clear()
    reactiondb._schema.cache_clear()


def test_a_reviewed_route_is_kept_when_wikipedia_has_the_same_reaction(index):
    out, built = index
    assert built.stats["reactions_curated"] == 3 and built.stats["reactions_wiki"] == 2
    assert built.stats["duplicates"] == 0
    con = sqlite3.connect(out)
    groups = {g for (g,) in con.execute("SELECT DISTINCT grp FROM top")}
    assert groups == {"textbook", "curated"}
    assert "curated" in dict(con.execute("SELECT key, value FROM meta"))["sources"].split(",")


def test_the_exact_reviewed_route_replaces_the_textbook_routes(index):
    r = reactiondb.lookup(MESO)
    assert r["textbook_makes"] == []
    (item,) = r["curated_makes"]
    assert item["source"] == "curated" and item["ref"] == "R004" and not item["other_stereo"]
    assert item["ref_label"].startswith("Clayden") and item["note"].startswith("Anti addition")
    assert item["svg"].startswith("<svg") and item["products"] == [MESO]
    assert r["no_preparation"] == ""
    assert any(s["name"] == "Reviewed textbook routes" for s in r["sources"])


def test_another_stereoisomers_reviewed_route_does_not_hide_the_textbook_routes(index):
    for smiles in (RR, PLAIN):
        r = reactiondb.lookup(smiles)
        assert [x["other_stereo"] for x in r["curated_makes"]] == [True]
        assert r["textbook_makes"], smiles


def test_the_reviewed_route_is_listed_under_uses_of_the_alkene(index):
    r = reactiondb.lookup("C/C=C/C")
    assert [x["ref"] for x in r["curated_uses"]] == ["R004"]
    assert r["curated_uses"][0]["products"] == [MESO]


def test_routes_without_a_named_group_change_still_get_a_label(index):
    assert reactiondb.lookup("C1CCCCC1")["curated_makes"][0]["label"] == "Aromatic ring hydrogenated"
    (item,) = reactiondb.lookup("C1=C/CCCCCC/1")["curated_makes"]
    assert item["label"] == "Double bond geometry changed" and not item["other_stereo"]
    # the Z isomer only sees it as another stereoisomer's route
    assert [x["other_stereo"] for x in reactiondb.lookup("C1=C\\CCCCCC/1")["curated_makes"]] == [True]


def test_no_common_preparation_note_for_every_stereoisomer(index):
    for smiles in ("CCC[C@H](C)CC", "CCC[C@@H](C)CC", "CCCC(C)CC"):
        r = reactiondb.lookup(smiles)
        assert r["no_preparation"].startswith("A branched alkane"), smiles
    assert reactiondb.lookup("CCCCCC")["no_preparation"] == ""


def test_no_common_preparation_note_without_an_index(monkeypatch, tmp_path):
    monkeypatch.setenv("CHEM_REACTIONS_DB", str(tmp_path / "missing.db"))
    monkeypatch.setenv("CHEM_CURATED_REACTIONS", str(HERE / "fixtures_curated.tsv"))
    r = reactiondb.lookup("CCC[C@H](C)CC")
    assert not r["available"] and r["no_preparation"].startswith("A branched alkane")
    assert r["curated_makes"] == []
