import importlib.util
import sqlite3
from pathlib import Path

import pytest
from rdkit import Chem

from app import reactiondb

HERE = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, HERE.parent / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wiki = _load("wiki_reactions")
build_reactions = _load("build_reactions")


def _same(a, b):
    return Chem.MolToSmiles(Chem.MolFromSmiles(a)) == Chem.MolToSmiles(Chem.MolFromSmiles(b))


@pytest.mark.parametrize("written, smiles", [
    ("CH3COOH", "CC(=O)O"), ("CH3CO2H", "CC(=O)O"), ("CH3CHO", "CC=O"), ("(CH3)2CO", "CC(C)=O"),
    ("C2H5OH", "CCO"), ("CH3OCH3", "COC"), ("CH3CO2CH2CH3", "CCOC(C)=O"), ("(CH3CO)2O", "CC(=O)OC(C)=O"),
    ("CH2\\dCHCH2Cl", "C=CCCl"), ("H3C\\sC\\tCH", "CC#C"), ("CHCl3", "ClC(Cl)Cl"), ("ClCH2CH2Cl", "ClCCCl"),
    ("C6H5CH(OH)CH3", "CC(O)c1ccccc1"), ("C6H5COCl", "O=C(Cl)c1ccccc1"), ("CH3NO2", "C[N+](=O)[O-]"),
    ("CO(NH2)2", "NC(N)=O"), ("(CH3)3CCl", "CC(C)(C)Cl"), ("CH3CN", "CC#N"),
])
def test_condensed_formulas(written, smiles):
    assert _same(wiki.parse_condensed(written), smiles)


@pytest.mark.parametrize("written", ["C4H10", "C6H12O6", "C2H4O2", "ClC2H4Cl", "RCH2OH"])
def test_ambiguous_formulas_are_refused(written):
    assert wiki.parse_condensed(written) is None


def test_equation_resolves_and_balances():
    st = wiki.Structures.__new__(wiki.Structures)
    st.by_title, st._formula, st._mol = {"Ethylene": "C=C"}, {}, {}
    left = [wiki.resolve(x, {}, st) for x in ("CH3COOH", "CH3CH2OH")]
    right = [wiki.resolve(x, {}, st) for x in ("CH3CO2CH2CH3", "H2O")]
    assert None not in left + right and wiki.balanced(left, right, st)
    assert not wiki.balanced(left, right[:1], st)
    assert wiki.resolve("[[Ethylene|C2H4]]", {}, st) == (1, "C=C")
    assert wiki.resolve("2 CH3OH", {}, st) == (2, "CO")


def test_wikipedia_equations_are_their_own_group(tmp_path, monkeypatch):
    row = "[CH2:1]=[CH2:2].[OH2:3]>>[CH3:1][CH2:2][OH:3]\tEthanol#12\t\t\t1234567|CCO\t0.95"
    out = tmp_path / "reactions.db"
    build_reactions.build([build_reactions.mapped_record(row, "wiki")], out, jobs=1)
    assert {r[0] for r in sqlite3.connect(out).execute("SELECT DISTINCT grp FROM top")} == {"textbook"}
    monkeypatch.setenv("CHEM_REACTIONS_DB", str(out))
    reactiondb._connect.cache_clear()
    reactiondb._schema.cache_clear()
    try:
        r = reactiondb.lookup("CCO")
        item = r["textbook_makes"][0]
        assert r["makes"] == [] and item["label"] == "Alkene → Alcohol"
        assert item["ref_label"] == "Wikipedia: Ethanol"
        assert item["ref_url"] == "https://en.wikipedia.org/w/index.php?title=Ethanol&oldid=1234567"
        assert any(s["licence"] == "CC BY-SA 4.0" for s in r["sources"])
    finally:
        reactiondb._connect.cache_clear()
        reactiondb._schema.cache_clear()


def test_text_route_makes_the_article_compound_only():
    """Hydrolysing ethyl formate (Ethyl formate article) makes formic acid and ethanol; the text
    is about ethyl formate, which is not made, and neither product is strictly the largest."""
    row = ("[CH:1](=[O:2])[O:3][CH2:4][CH3:5].[OH2:6]>>[CH:1](=[O:2])[OH:6].[OH:3][CH2:4][CH3:5]"
           "\tEthyl formate#3\t\t\t111|CCOC=O\t0.9")
    assert build_reactions.process(build_reactions.mapped_record(row, "wiki")) == []
    # On the Ethanol page the same equation is a route to ethanol.
    row2 = row.replace("Ethyl formate#3", "Ethanol#9").replace("111|CCOC=O", "222|CCO")
    views = build_reactions.process(build_reactions.mapped_record(row2, "wiki"))
    assert [o[2] for v in views for o in v["obs"] if o[4] == "makes"] == ["CCO"]


def test_reagents_named_in_words():
    st = wiki.Structures()
    side = wiki._side_combos(st)
    rxns = wiki.balance("CCC(C)Cl", ["Cl", "CC=CC"], "addition of hydrochloric acid to 2-butene", st, side)
    assert rxns == ["CC=CC.Cl>>CCC(C)Cl"]


def _forward(text, own=None, title="Topic", names=None, by_title=None):
    st = wiki.Structures()
    st.by_title.update(by_title or {})
    lower = {t.lower(): s for t, s in st.by_title.items()}
    return wiki.forward_candidates(title, own, text, st, wiki._side_combos(st), lower, names or {}, None)


def test_reaction_sentence_credits_the_product():
    """A sentence on another article (a reaction or the starting material) is a route to the
    compound it names after the verb, here a name looked up in PubChem."""
    text = "Treating [[trans-2-Butene|trans-2-butene]] with bromine gives meso-2,3-dibromobutane."
    found = _forward(text, by_title={"Trans-2-Butene": "C/C=C/C"},
                     names={"meso-2,3-dibromobutane": "C[C@@H](Br)[C@H](C)Br"})
    meso = Chem.MolToSmiles(Chem.MolFromSmiles("C[C@@H](Br)[C@H](C)Br"))
    assert [r for r, _, _ in found] == [f"BrBr.C/C=C/C>>{meso}"]


def test_reaction_sentence_on_the_compound_article():
    text = "==Reactions==\nIt reacts with [[hydrogen bromide]] to give [[Bromocyclohexane|bromocyclohexane]].\n"
    st_titles = {"Hydrogen bromide": "Br", "Bromocyclohexane": "BrC1CCCCC1"}
    st = wiki.Structures()
    st.by_title.update(st_titles)
    found = wiki.forward_candidates("Cyclohexene", "C1=CCCCC1", text, st, wiki._side_combos(st), {}, {}, wiki.REACT_SECTION)
    assert [r for r, _, _ in found] == ["Br.C1=CCCCC1>>BrC1CCCCC1"]


@pytest.mark.parametrize("text", [
    "Ethene does not react with bromine to give 1,2-dibromoethane.",  # denied
    "Analogues of ethene include propene, which forms 1,2-dibromoethane with bromine.",  # not a reaction
    "Diatomic carbon reacts with acetaldehyde to give ethyne.",  # the subject takes no part
])
def test_reaction_sentences_refused(text):
    by_title = {"Ethene": "C=C", "Propene": "CC=C", "1,2-dibromoethane": "BrCCBr", "Diatomic carbon": "[C]#[C]",
                "Acetaldehyde": "CC=O", "Ethyne": "C#C"}
    assert _forward(text, by_title=by_title) == []
