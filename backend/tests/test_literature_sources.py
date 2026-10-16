import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

import httpx  # noqa: E402

from app import (cache, literature, literature_card, literature_chembl, literature_journals, literature_mentions,  # noqa: E402
                 literature_openalex, literature_patents, literature_surechembl, ord_papers)


def _patch(monkeypatch, handler):
    real = httpx.Client

    def fake(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", fake)
    for module in (literature, literature_journals, literature_patents, literature_openalex, literature_chembl,
                   literature_mentions, literature_surechembl):
        monkeypatch.setattr(module, "enabled", lambda: True)


def _work(pmid, title, year, cites, pub_type="journal article"):
    return {
        "pmid": str(pmid), "doi": f"10.1000/{pmid}", "title": title + ".", "pubYear": str(year), "firstPublicationDate": f"{year}-01-01",
        "citedByCount": cites, "pubType": pub_type, "authorString": "Author A, Other B, Third C, Fourth D.", "journalTitle": "J Chem",
    }


def _europepmc(works):
    return httpx.Response(200, json={"hitCount": len(works), "resultList": {"result": works}})


def _query(request):
    return dict(httpx.QueryParams(request.content.decode()))


def test_journals_come_from_pubchem_links_and_favour_titles_naming_the_molecule(monkeypatch):
    asked = []

    def handler(request):
        if request.url.host == "pubchem.ncbi.nlm.nih.gov":
            return httpx.Response(200, json={"InformationList": {"Information": [{"CID": 7966, "PubMedID": [3, 1, 2, 4]}]}})
        asked.append(_query(request)["query"])
        return _europepmc([
            _work(1, "Heavy metal adsorption on nanotubes", 2010, 900, pub_type="review; journal article"),
            _work(2, "Oxidation of cyclohexanol to cyclohexanone", 2011, 50),
            _work(3, "A retracted cyclohexanol paper", 2012, 10, pub_type="retracted publication; journal article"),
            _work(4, "Polymorphism in cyclohexanol", 2008, 35),
        ])

    _patch(monkeypatch, handler)
    data, complete = literature_journals.search(7966, ["Cyclohexanol"])
    assert complete and data["match"] == "pubchem" and data["total"] == 4
    assert asked == ["SRC:MED AND (EXT_ID:1 OR EXT_ID:2 OR EXT_ID:3 OR EXT_ID:4)"]
    titles = [i["title"] for i in data["items"]]
    assert titles[:2] == ["Oxidation of cyclohexanol to cyclohexanone", "Polymorphism in cyclohexanol"]
    assert "A retracted cyclohexanol paper" not in titles
    first = data["items"][0]
    assert first["url"] == "https://doi.org/10.1000/2" and first["journal"] == "J Chem" and first["year"] == 2011
    assert first["authors"] == "Author A, Other B, Third C et al." and data["items"][-1]["type"] == "review"


def test_journals_title_search_when_pubchem_has_no_links(monkeypatch):
    def handler(request):
        if request.url.host == "pubchem.ncbi.nlm.nih.gov":
            return httpx.Response(404, json={})
        q = _query(request)
        assert q["query"].lower() == 'title:"2-butanol" and src:med' and q["sort"] == "CITED desc"
        return _europepmc([_work(1, "Dehydration of 2-butanol", 2015, 5), _work(2, "Butanal chemistry", 2016, 99)])

    _patch(monkeypatch, handler)
    data, complete = literature_journals.search(1234, ["(R)-2-Butanol"])
    assert complete and data["match"] == "title"
    assert [i["title"] for i in data["items"]] == ["Dehydration of 2-butanol"]


def test_journals_retry_a_busy_service(monkeypatch):
    monkeypatch.setattr(literature_journals.time, "sleep", lambda s: None)
    tries = []

    def handler(request):
        if request.url.host == "pubchem.ncbi.nlm.nih.gov":
            tries.append(1)
            if len(tries) < 3:
                return httpx.Response(503, json={"Fault": {"Code": "PUGREST.ServerBusy"}})
            return httpx.Response(200, json={"InformationList": {"Information": [{"CID": 7966, "PubMedID": [2]}]}})
        return _europepmc([_work(2, "Oxidation of cyclohexanol", 2011, 50)])

    _patch(monkeypatch, handler)
    data, complete = literature_journals.search(7966, ["Cyclohexanol"])
    assert complete and len(tries) == 3 and len(data["items"]) == 1


def test_journals_failure_is_not_cached(monkeypatch):
    monkeypatch.setattr(literature_journals.time, "sleep", lambda s: None)
    _patch(monkeypatch, lambda request: httpx.Response(503, json={}))
    data, complete = literature_journals.search(7966, ["Cyclohexanol"])
    assert not complete and not data["available"]


def test_spread_keeps_newest_and_samples_the_rest():
    ids = list(range(1, 10_001))
    picked = literature_journals._spread(ids)
    assert len(picked) == literature_journals.LOOKUP == len(set(picked))
    assert picked[-1] == 10_000 and picked[0] == 1


def test_pubchem_patent_ids():
    assert literature_patents.pubchem_ids("US03930836") == ["US-3930836-A"]
    assert literature_patents.pubchem_ids("US09450188B2") == ["US-9450188-B2", "US-9450188-B"]
    assert literature_patents.pubchem_ids("USRE038551E1") == ["US-RE38551-E1", "US-RE38551-E"]
    assert literature_patents.pubchem_ids("EP123") == []


def test_patents_from_reaction_examples_with_pubchem_titles(monkeypatch):
    record = {"Record": {"RecordTitle": "Method of hydrogenating phenol", "Section": [
        {"TOCHeading": "Important Dates", "Section": [{"TOCHeading": "Publication Date", "Information": [{"Value": {"DateISO8601": ["2007/07/31"]}}]}]},
        {"TOCHeading": "Assignee", "Information": [{"Value": {"StringWithMarkup": [{"String": "NAT INST (JP)"}]}}]},
    ]}}

    def handler(request):
        if "US-7250537-B2" in request.url.path:
            return httpx.Response(200, json=record)
        return httpx.Response(404, json={})

    _patch(monkeypatch, handler)
    reactions = {
        "uses": [{"source": "uspto", "ref": "US04868310", "year": 1989, "label": "Alcohol → new C-N bond"},
                 {"source": "crd", "ref": "12", "year": None, "label": "Alcohol → Ester"}],
        "makes": [{"source": "uspto", "ref": "US07250537B2", "year": 2007, "label": "Phenol → Alcohol"},
                  {"source": "uspto", "ref": "US07250537B2", "year": 2007, "label": "Ketone → Alcohol"}],
    }
    data, complete = literature_patents.search(reactions, 7966)
    assert complete and [i["number"] for i in data["items"]] == ["US07250537B2", "US04868310"]
    first = data["items"][0]
    assert first["title"] == "Method of hydrogenating phenol" and first["date"] == "2007-07-31" and first["assignee"] == "NAT INST (JP)"
    assert [r["label"] for r in first["reactions"]] == ["Phenol → Alcohol", "Ketone → Alcohol"]
    assert data["items"][1]["title"] == "" and data["pubchem_url"].endswith("/compound/7966#section=Patents")


def test_chemrxiv_snippet_around_the_name():
    text = "We report a catalyst. " * 10 + "It oxidises cyclohexanol to cyclohexanone in water. " + "More text here. " * 10
    snip = literature.snippet(text, "Cyclohexanol")
    assert "cyclohexanol" in snip and snip.startswith("…") and snip.endswith("…") and len(snip) <= literature.SNIPPET + 20
    assert literature.snippet(text, "benzene") == ""
    assert literature._abstract({"b": [1], "a": [0], "c": [2]}) == "a b c"


def test_synonyms_skip_codes_and_cas_numbers(monkeypatch):
    syns = ["CYCLOHEXANOL", "108-93-0", "Cyclohexyl alcohol", "NSC 403656", "Hexahydrophenol", "UNII-8E7S519M3P", "Adronal"]

    def handler(request):
        return httpx.Response(200, json={"InformationList": {"Information": [{"CID": 7966, "Synonym": syns}]}})

    _patch(monkeypatch, handler)
    assert literature.synonyms(7966) == ["Cyclohexyl alcohol", "Hexahydrophenol", "Adronal"]
    assert literature.synonyms(None) == []


# --- shared helpers --------------------------------------------------------------

def test_names_it_rejects_bigger_molecules_built_on_the_name():
    name = ["1-(4-bromophenyl)ethanone"]
    assert literature.names_it("Reduction of 1-(4-bromophenyl)ethanone with NaBH4", name)
    assert not literature.names_it("2-Bromo-1-(4-bromophenyl)ethanone", name)
    assert not literature.names_it("2-(Benzothiazol-2-ylsulfonyl)-1-(4-bromophenyl)ethanone", name)
    assert literature.names_it("4′-Bromoacetophenone in water", ["4'-Bromoacetophenone"])
    assert literature.names_it("Aspirin-loaded micelles", ["aspirin"])
    assert not literature.names_it("Polyaspirin films", ["aspirin"]) and not literature.names_it("Butanal", ["butanol"])


def test_europe_pmc_titles_are_unescaped():
    assert literature_journals.clean_title("Mn&lt;sup&gt;V&lt;/sup&gt; oxo &amp;amp; water.") == "MnV oxo & water"


def test_europe_pmc_open_access_articles_link_to_the_full_text():
    w = _work(5, "Cyclohexanol", 2020, 3)
    assert literature_journals._item({**w, "pmcid": "PMC123", "isOpenAccess": "Y"})["oa_url"] == "https://europepmc.org/article/PMC/PMC123"
    assert literature_journals._item({**w, "pmcid": "PMC123", "isOpenAccess": "N"})["oa_url"] == ""


# --- OpenAlex chemistry journals -------------------------------------------------

def _oa_work(doi, title, year=2020, cites=1, is_oa=False, kind="article"):
    return {"doi": f"https://doi.org/{doi}", "title": title, "publication_year": year, "publication_date": f"{year}-01-01",
            "cited_by_count": cites, "type": kind, "authorships": [{"author": {"display_name": "A B"}}],
            "primary_location": {"source": {"display_name": "J. Org. Chem."}},
            "open_access": {"is_oa": is_oa, "oa_url": "https://x.org/pdf" if is_oa else None},
            "abstract_inverted_index": {"We": [0], "reduce": [1], "4'-bromoacetophenone": [2]}}


def test_openalex_journals_are_chemistry_and_not_chemrxiv(monkeypatch):
    seen = {}

    def handler(request):
        seen.update(request.url.params)
        return httpx.Response(200, json={"meta": {"count": 2}, "results": [
            _oa_work("10.1/a", "Reduction of 4'-bromoacetophenone", is_oa=True),
            _oa_work("10.1/b", "Ketone reductions", kind="review"),
        ]})

    _patch(monkeypatch, handler)
    data, complete = literature_openalex.search(["4'-Bromoacetophenone"])
    assert complete and data["total"] == 2
    f = seen["filter"]
    assert "primary_topic.field.id:16|15|25" in f and f"primary_location.source.id:!{literature.CHEMRXIV_SOURCE}" in f
    a, b = data["items"]
    assert a["match"] == "title" and a["oa_url"] == "https://x.org/pdf" and a["journal"] == "J. Org. Chem."
    assert b["match"] == "abstract" and b["type"] == "review" and b["oa_url"] == "" and "bromoacetophenone" in b["snippet"]


def test_openalex_journals_failure_is_not_cached(monkeypatch):
    _patch(monkeypatch, lambda request: httpx.Response(429, json={}))
    data, complete = literature_openalex.search(["Cyclohexanol"])
    assert not complete and not data["available"]


# --- ChEMBL --------------------------------------------------------------------

def test_chembl_papers_by_structure_with_europe_pmc_details(monkeypatch):
    def handler(request):
        path = request.url.path
        if "unichem" in path:
            return httpx.Response(500, json={})  # UniChem down: ChEMBL's own structure filter answers instead
        if path.endswith("/molecule.json"):
            assert request.url.params["molecule_structures__standard_inchi_key"] == "KEY"
            return httpx.Response(200, json={"molecules": [{"molecule_chembl_id": "CHEMBL25"}]})
        if path.endswith("/compound_record.json"):
            return httpx.Response(200, json={"compound_records": [{"document_chembl_id": d} for d in ("CHEMBL9", "CHEMBL10", "CHEMBL9")]})
        if path.endswith("/document.json"):
            return httpx.Response(200, json={"documents": [
                {"document_chembl_id": "CHEMBL9", "title": "Aspirin analogues.", "journal": "J Med Chem", "year": 1990,
                 "doi": "10.1021/X", "pubmed_id": 2, "doc_type": "PUBLICATION", "authors": "A, B, C, D"},
                {"document_chembl_id": "CHEMBL10", "title": "Unpublished", "doc_type": "DATASET"},
                {"document_chembl_id": "CHEMBL11", "title": "No PubMed id", "journal": "Bioorg Med Chem Lett", "year": 1999,
                 "doi": "10.1016/Y", "pubmed_id": None, "doc_type": "PUBLICATION", "authors": "E"},
            ]})
        assert "europepmc" in path
        return _europepmc([_work(2, "Aspirin analogues", 1990, 40)])

    _patch(monkeypatch, handler)
    data, complete = literature_chembl.search("KEY")
    assert complete and data["chembl_id"] == "CHEMBL25" and data["total"] == 2
    by_title = {i["title"]: i for i in data["items"]}
    assert by_title["Aspirin analogues"]["cited_by"] == 40
    assert by_title["No PubMed id"]["url"] == "https://doi.org/10.1016/y" and by_title["No PubMed id"]["cited_by"] == 0


def test_chembl_id_comes_from_unichem(monkeypatch):
    asked = []

    def handler(request):
        asked.append(request.url.path)
        if "unichem" in request.url.path:
            return httpx.Response(200, json={"compounds": [{"sources": [{"shortName": "chebi", "compoundId": "CHEBI:1"},
                                                                         {"shortName": "chembl", "compoundId": "CHEMBL32010"}]}]})
        assert request.url.params["molecule_chembl_id"] == "CHEMBL32010"
        return httpx.Response(200, json={"compound_records": []})

    _patch(monkeypatch, handler)
    data, complete = literature_chembl.search("KEY")
    assert complete and data["chembl_id"] == "CHEMBL32010" and data["items"] == []
    assert not any(p.endswith("/molecule.json") for p in asked)


def test_chembl_unknown_structure_is_an_empty_answer(monkeypatch):
    _patch(monkeypatch, lambda request: httpx.Response(404, json={}))
    data, complete = literature_chembl.search("KEY")
    assert complete and data["available"] and data["items"] == []


# --- Europe PMC chemical tagging -------------------------------------------------

def test_mentions_by_chebi_name(monkeypatch):
    asked = []

    def handler(request):
        if "unichem" in request.url.path:
            return httpx.Response(200, json={"compounds": [{"sources": [{"shortName": "chembl", "compoundId": "CHEMBL1"},
                                                                         {"shortName": "chebi", "compoundId": "CHEBI:18099"}]}]})
        if "ols4" in request.url.path:
            assert request.url.params["obo_id"] == "CHEBI:18099"
            return httpx.Response(200, json={"_embedded": {"terms": [{"label": "cyclohexanol"}]}})
        asked.append(_query(request)["query"])
        return _europepmc([_work(7, "Solvent effects", 2024, 0)])

    _patch(monkeypatch, handler)
    data, complete = literature_mentions.search("KEY")
    assert complete and asked == ['CHEBITERM:"cyclohexanol"'] and data["chebi"] == "CHEBI:18099"
    assert data["items"][0]["match"] == "text"


def test_mentions_without_chebi_entry(monkeypatch):
    _patch(monkeypatch, lambda request: httpx.Response(200, json={"compounds": [{"sources": []}]}))
    data, complete = literature_mentions.search("KEY")
    assert complete and data["items"] == []


# --- SureChEMBL ------------------------------------------------------------------

def _sc(data):
    return httpx.Response(200, json={"status": "OK", "error_message": "", "data": data})


def test_surechembl_ranks_titles_naming_or_making_the_compound(monkeypatch):
    queries, pages = [], []

    def handler(request):
        path = request.url.path
        if path.endswith("/chemical/smiles/"):
            smi = request.url.params["smiles"]
            return _sc({smi: {"chemical_id": "20102"}} if smi == "CC(=O)c1ccc(Br)cc1" else {})
        if path.endswith("/documents_for_structures"):
            pages.append(request.url.params["page"])
            docs = [("CN-1-A", "Organic light emitting device"), ("US-2-B2", "Process for preparing biaryls"),
                    ("JP-3-A", "Use of 4-bromoacetophenone as a photoinitiator"), ("WO-4-A1", "Display panel")]
            return _sc({"results": {"total_hits": 7114, "documents": [
                {"docId": d, "metadata": {"pd": "null", "titles": [{"lang": "en", "titles": [t]}]}} for d, t in docs]}})
        queries.append(request.url.params["query"])
        return _sc({"results": {"documents": [{"docId": "US-2-B2", "metadata": {"pd": "20190305"}, "pa": "ACME CORP"}]}})

    _patch(monkeypatch, handler)
    data, complete = literature_surechembl.search("C[C@H](O)Br", "CC(=O)c1ccc(Br)cc1", ["4-bromoacetophenone"])
    assert complete and data["total"] == 7114 and data["chemical_id"] == "20102"
    assert pages == ["1", "71", "72"]  # the total from page 1, then the newest two pages
    assert [d["number"] for d in data["items"]] == ["JP-3-A", "US-2-B2", "WO-4-A1", "CN-1-A"]
    us = data["items"][1]
    assert us["date"] == "2019-03-05" and us["year"] == 2019 and us["assignee"] == "Acme Corp" and us["making"]
    assert us["url"] == "https://patents.google.com/patent/US2B2/en" and queries and '"US-2-B2"' in queries[0]


def test_surechembl_down_is_not_cached(monkeypatch):
    _patch(monkeypatch, lambda request: httpx.Response(500, json={}))
    data, complete = literature_surechembl.search("CCO")
    assert not complete and not data["available"]


# --- merging ---------------------------------------------------------------------

def _j(title, doi="", pmid="", cites=0, year=2000, match=None, oa=""):
    it = {"title": title, "doi": doi, "pmid": pmid, "cited_by": cites, "year": year, "type": "article", "oa_url": oa,
          "url": f"https://doi.org/{doi}", "journal": "", "authors": ""}
    if match:
        it["match"] = match
    return it


def test_merge_journals_lists_each_article_once_with_every_source():
    found = {
        "journals": {"items": [_j("Solvent toxicity in rats", doi="10.1/a", pmid="1", cites=500)]},
        "chembl": {"items": [_j("Solvent toxicity in rats", doi="10.1/a", pmid="1", cites=510, oa="https://pmc/1")]},
        "openalex": {"items": [_j("Synthesis of cyclohexanol by hydrogenation", doi="10.1/b", cites=20, match="title"),
                               _j("2-Methyl-cyclohexanol oxidation", doi="10.1/c", cites=900, match="abstract")]},
        "mentions": {"available": False, "reason": "down", "items": []},
    }
    out = literature_card.merge_journals(found, ["Cyclohexanol"])
    assert out["available"] and out["total"] == 3
    by_doi = {i["doi"]: i for i in out["items"]}
    a = by_doi["10.1/a"]
    assert a["sources"] == ["PubMed", "ChEMBL"] and a["cited_by"] == 510 and a["oa_url"] == "https://pmc/1" and a["match"] == "structure"
    assert by_doi["10.1/b"]["about"] and by_doi["10.1/b"]["making"]
    assert not by_doi["10.1/c"]["about"]  # a methyl derivative, not cyclohexanol
    assert out["items"][0]["doi"] == "10.1/b"  # about the molecule and how to make it beats citations
    assert out["sources"]["Europe PMC"] == {"available": False, "count": 0, "total": 0, "reason": "down", "stale": False, "pending": False}


def test_merge_patents_joins_the_reaction_index_and_surechembl():
    index = {"items": [{"number": "US09450188B2", "url": "u", "year": 2016, "title": "", "date": "", "assignee": "",
                        "reactions": [{"direction": "makes", "label": "Ketone → Alcohol"}]}], "cid": 1, "pubchem_url": "p"}
    sure = {"items": [{"number": "US-9450188-B2", "title": "Carbazole derivative", "date": "2016-09-20", "year": 2016, "assignee": "Lab",
                       "url": "g", "making": False},
                      {"number": "WO-2020123-A1", "title": "Method for producing cyclohexanol", "date": "2020-01-01", "year": 2020,
                       "assignee": "", "url": "g2", "making": True}], "total": 5000}
    out = literature_card.merge_patents(index, sure, ["cyclohexanol"])
    # A patent about making the molecule first, then one whose worked examples use it.
    assert [i["number"] for i in out["items"]] == ["WO-2020123-A1", "US09450188B2"]
    first = out["items"][1]
    assert first["sources"] == ["Reaction records", "SureChEMBL"] and first["title"] == "Carbazole derivative" and first["assignee"] == "Lab"
    assert out["items"][0]["about"] and out["surechembl"]["total"] == 5000


# --- reliability ---------------------------------------------------------------------

def test_an_expired_result_is_served_when_the_service_is_down():
    from datetime import datetime, timedelta, timezone

    from app.db import LiteratureCache, SessionLocal, init_db

    init_db()
    with SessionLocal() as db:
        old = {"available": True, "items": [{"title": "x"}], "_v": literature_openalex.VERSION}
        cache.store_literature(db, "STALEKEY", "openalex", old, True)
        row = db.get(LiteratureCache, "STALEKEY/o")
        row.created_at = datetime.now(timezone.utc) - timedelta(days=90)
        db.commit()
        assert cache.cached_literature(db, "STALEKEY", "openalex") is None
        down = {"available": False, "items": [], "reason": "OpenAlex is not reachable right now.", "_v": literature_openalex.VERSION}
        served = cache.store_literature(db, "STALEKEY", "openalex", down, False)
        assert served["items"] == [{"title": "x"}] and served["stale"] is True


# --- Open Reaction Database ------------------------------------------------------------

def test_ord_papers_from_the_local_index(monkeypatch, tmp_path):
    import sqlite3

    path = tmp_path / "ord.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE papers (doi TEXT PRIMARY KEY, title TEXT, authors TEXT, journal TEXT, year INTEGER,
                             cited_by INTEGER, oa_url TEXT, type TEXT, datasets TEXT);
        CREATE TABLE links (inchikey TEXT, doi TEXT, roles TEXT, reactions INTEGER, PRIMARY KEY (inchikey, doi));
        INSERT INTO papers VALUES ('10.1126/science.aap9112', 'Suzuki screening', 'A et al.', 'Science', 2018, 300, '', 'article', 'HTE');
        INSERT INTO links VALUES ('KEY', '10.1126/science.aap9112', 'reactant', 120);
    """)
    con.commit()
    con.close()
    monkeypatch.setenv("CHEM_ORD_DB", str(path))
    data = ord_papers.search("KEY")
    assert data["installed"] and data["total"] == 1
    item = data["items"][0]
    assert item["url"] == "https://doi.org/10.1126/science.aap9112" and item["ord"] == {"roles": ["reactant"], "reactions": 120}
    assert ord_papers.search("OTHER")["items"] == []
    monkeypatch.setenv("CHEM_ORD_DB", str(tmp_path / "missing.db"))
    assert ord_papers.search("KEY")["installed"] is False


def test_slow_sources_are_pending_then_cached(monkeypatch):
    import threading

    from app.db import SessionLocal, init_db

    init_db()
    release = threading.Event()

    def slow(key):
        release.wait(5)
        return {"available": True, "items": [_j("A neopentyl alcohol in medicinal chemistry", doi="10.9/slow")], "total": 1,
                "chembl_id": "CHEMBL1", "_v": literature_chembl.VERSION}, True

    from rdkit import Chem

    monkeypatch.setattr(literature_chembl, "search", slow)
    smiles = "CC(C)(C)CC(C)(C)CCO"  # a molecule no other test uses: collect() caches its (missing) PubChem name
    key = Chem.MolToInchiKey(Chem.MolFromSmiles(smiles))
    with SessionLocal() as db:
        first = literature_card.collect(db, smiles, budget=0.2)
        assert first["journals"]["sources"]["ChEMBL"]["pending"] is True
        release.set()
        for _ in range(50):  # the background search finishes and is stored
            if cache.cached_literature(db, key, "chembl"):
                break
            threading.Event().wait(0.05)
        again = literature_card.collect(db, smiles, budget=0.2)
    chembl = again["journals"]["sources"]["ChEMBL"]
    assert chembl["pending"] is False and chembl["count"] == 1
    assert [i["doi"] for i in again["journals"]["items"]] == ["10.9/slow"]
