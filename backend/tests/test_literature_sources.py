import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

import httpx  # noqa: E402

from app import literature, literature_journals, literature_patents  # noqa: E402


def _patch(monkeypatch, handler):
    real = httpx.Client

    def fake(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", fake)
    monkeypatch.setattr(literature, "enabled", lambda: True)
    monkeypatch.setattr(literature_journals, "enabled", lambda: True)
    monkeypatch.setattr(literature_patents, "enabled", lambda: True)


def _work(pmid, title, year, cites, **extra):
    return {
        "doi": f"https://doi.org/10.1000/{pmid}", "title": title, "publication_year": year, "publication_date": f"{year}-01-01",
        "cited_by_count": cites, "type": "article", "authorships": [{"author": {"display_name": "A Author"}}],
        "primary_location": {"source": {"display_name": "J. Chem."}}, "ids": {"pmid": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}"},
        **extra,
    }


def test_journals_come_from_pubchem_links_and_favour_titles_naming_the_molecule(monkeypatch):
    asked = []

    def handler(request):
        if request.url.host == "pubchem.ncbi.nlm.nih.gov":
            return httpx.Response(200, json={"InformationList": {"Information": [{"CID": 7966, "PubMedID": [3, 1, 2, 4]}]}})
        asked.append(request.url.params["filter"])
        return httpx.Response(200, json={"results": [
            _work(1, "Heavy metal adsorption on nanotubes", 2010, 900),
            _work(2, "Oxidation of cyclohexanol to cyclohexanone", 2011, 50),
            _work(3, "A retracted cyclohexanol paper", 2012, 10, is_retracted=True),
            _work(4, "Polymorphism in cyclohexanol", 2008, 35),
        ]})

    _patch(monkeypatch, handler)
    data, complete = literature_journals.search(7966, ["Cyclohexanol"])
    assert complete and data["match"] == "pubchem" and data["total"] == 4
    assert asked == ["ids.pmid:1|2|3|4"]
    titles = [i["title"] for i in data["items"]]
    assert titles[:2] == ["Oxidation of cyclohexanol to cyclohexanone", "Polymorphism in cyclohexanol"]
    assert "A retracted cyclohexanol paper" not in titles
    assert data["items"][0]["url"] == "https://doi.org/10.1000/2" and data["items"][0]["journal"] == "J. Chem."


def test_journals_title_search_when_pubchem_has_no_links(monkeypatch):
    def handler(request):
        if request.url.host == "pubchem.ncbi.nlm.nih.gov":
            return httpx.Response(404, json={})
        assert request.url.params["filter"].lower().startswith("title.search:2-butanol")
        return httpx.Response(200, json={"results": [_work(1, "Dehydration of 2-butanol", 2015, 5), _work(2, "Butanal chemistry", 2016, 99)]})

    _patch(monkeypatch, handler)
    data, complete = literature_journals.search(1234, ["(R)-2-Butanol"])
    assert complete and data["match"] == "title"
    assert [i["title"] for i in data["items"]] == ["Dehydration of 2-butanol"]


def test_journals_failure_is_not_cached(monkeypatch):
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
