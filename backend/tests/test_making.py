"""How a molecule is made: PubChem manufacturing methods and the Wikipedia section."""

import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

import httpx  # noqa: E402

from app import literature, manufacture, wikipedia  # noqa: E402

RECORD = {"Record": {"Section": [{"TOCHeading": "Use and Manufacturing", "Section": [{
    "TOCHeading": "Methods of Manufacturing",
    "Information": [
        {"Reference": ["Ullmann's Encyclopedia"], "Value": {"StringWithMarkup": [{
            "String": "Cyclohexanol is made by hydrogenation of phenol.",
            "Markup": [
                {"Start": 0, "Length": 12, "Type": "PubChem Internal Link", "Extra": "CID-7966"},
                {"Start": 41, "Length": 6, "Type": "PubChem Internal Link", "Extra": "CID-996"},
            ]}]}},
        {"Reference": ["Merck Index"], "Value": {"StringWithMarkup": [{"String": "Liquid-phase oxidation of cyclohexane."}]}},
        {"Value": {"StringWithMarkup": [{"String": "For more Methods of Manufacturing (Complete) data for Cyclohexanol (7 total), please visit the HSDB record page."}]}},
    ]}]}]}}

SECTION_HTML = """<div class="mw-parser-output"><div class="mw-heading mw-heading2"><h2 id="Production">Production</h2></div>
<p>Crotonaldehyde is produced by the <a href="/wiki/Aldol_condensation" title="Aldol condensation">aldol condensation</a> of
<a href="/wiki/Acetaldehyde" title="Acetaldehyde">acetaldehyde</a>:<sup class="reference"><a href="#cite_note-1">[1]</a></sup></p>
<dl><dd>2 CH<sub>3</sub>CHO → CH<sub>3</sub>CH=CHCHO + H<sub>2</sub>O</dd></dl>
<figure typeof="mw:File"><a href="/wiki/File:Aldol_scheme.svg" class="mw-file-description"><img src="//upload.wikimedia.org/aldol.png" data-file-width="300" data-file-height="80"></a></figure>
<p>More text.</p>
<div class="mw-references-wrap"><ol class="references"><li>A reference</li></ol></div></div>"""


def _patch(monkeypatch, handler):
    real = httpx.Client

    def fake(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", fake)
    monkeypatch.setattr(literature, "enabled", lambda: True)
    monkeypatch.setattr(manufacture, "enabled", lambda: True)
    monkeypatch.setattr(wikipedia, "enabled", lambda: True)


def test_methods_skip_pointers_and_self_links():
    methods = manufacture.methods_from_record(RECORD["Record"], cid=7966)
    assert [m["text"] for m in methods] == ["Cyclohexanol is made by hydrogenation of phenol.", "Liquid-phase oxidation of cyclohexane."]
    assert methods[0]["compounds"] == [{"start": 41, "length": 6, "name": "phenol"}]
    assert methods[0]["reference"] == "Ullmann's Encyclopedia"


def test_methods_fall_back_to_the_compound_without_stereo(monkeypatch):
    def handler(request):
        if "/cids/" in request.url.path:
            assert "BTANRVKWQNVYAZ/" in request.url.path  # first InChIKey block
            return httpx.Response(200, json={"IdentifierList": {"CID": [6568, 84682]}})
        if "/compound/6568/" in request.url.path:
            return httpx.Response(200, json=RECORD)
        return httpx.Response(404, json={})

    _patch(monkeypatch, handler)
    data, complete = manufacture.search(84682, "BTANRVKWQNVYAZ-SCSAIBSYSA-N")
    assert complete and data["stereo_ignored"] and data["cid"] == 6568 and len(data["methods"]) == 2
    assert data["url"].endswith("/compound/6568#section=Methods-of-Manufacturing")


def test_methods_failure_is_not_cached(monkeypatch):
    _patch(monkeypatch, lambda request: httpx.Response(503, json={}))
    data, complete = manufacture.search(7966, "HPXRVTGHNJAIIH-UHFFFAOYSA-N")
    assert not complete and not data["available"]


def test_wikipedia_section_text_links_equations_and_pictures():
    parsed = wikipedia.parse_section(SECTION_HTML)
    texts = [p["text"] for p in parsed["paragraphs"]]
    assert texts[0] == "Crotonaldehyde is produced by the aldol condensation of acetaldehyde:"  # no [1]
    assert texts[1] == "2 CH₃CHO → CH₃CH=CHCHO + H₂O"
    assert texts[2] == "More text."
    link = next(link for link in parsed["paragraphs"][0]["links"] if link[2] == "Acetaldehyde")
    assert texts[0][link[0]:link[0] + link[1]] == "acetaldehyde"
    assert parsed["images"] == [{"file": "Aldol scheme.svg", "src": "https://upload.wikimedia.org/aldol.png", "width": 300, "height": 80, "after": 2}]


def test_wikipedia_search_by_inchikey(monkeypatch):
    def handler(request):
        p = dict(request.url.params)
        host = request.url.host
        if host == "www.wikidata.org" and p.get("list") == "search":
            assert p["srsearch"] == "haswbstatement:P235=MLUCVPSAIODCQM-UHFFFAOYSA-N"
            return httpx.Response(200, json={"query": {"search": [{"title": "Q411394"}]}})
        if host == "www.wikidata.org" and p.get("ids") == "Q411394":
            return httpx.Response(200, json={"entities": {"Q411394": {"sitelinks": {"enwiki": {"title": "Crotonaldehyde"}}}}})
        if host == "www.wikidata.org":  # the linked compounds
            return httpx.Response(200, json={"entities": {"Q12": {"claims": {"P233": [{"mainsnak": {"datavalue": {"value": "CC=O"}}}]}},
                                                          "Q13": {"claims": {}}}})
        if host == "en.wikipedia.org" and p.get("prop") == "tocdata":
            return httpx.Response(200, json={"parse": {"tocdata": {"sections": [
                {"line": "Properties", "index": "1", "anchor": "Properties"},
                {"line": "Production", "index": "2", "anchor": "Production"}]}}})
        if host == "en.wikipedia.org" and p.get("section") == "2":
            return httpx.Response(200, json={"parse": {"text": SECTION_HTML}})
        if host == "en.wikipedia.org":  # resolving the links
            return httpx.Response(200, json={"query": {"pages": [
                {"title": "Acetaldehyde", "pageprops": {"wikibase_item": "Q12"}},
                {"title": "Aldol condensation", "pageprops": {"wikibase_item": "Q13"}}]}})
        if host == "commons.wikimedia.org":
            return httpx.Response(200, json={"query": {"pages": [{"title": "File:Aldol scheme.svg", "imageinfo": [{
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Aldol_scheme.svg",
                "extmetadata": {"Artist": {"value": "<a href='x'>Someone</a>"}, "LicenseShortName": {"value": "CC BY-SA 4.0"}}}]}]}})
        raise AssertionError(request.url)

    _patch(monkeypatch, handler)
    data, complete = wikipedia.search("MLUCVPSAIODCQM-UHFFFAOYSA-N")
    assert complete and data["title"] == "Crotonaldehyde" and data["section"] == "Production"
    assert data["url"] == "https://en.wikipedia.org/wiki/Crotonaldehyde#Production"
    compounds = data["paragraphs"][0]["compounds"]
    assert [(c["name"], c["smiles"]) for c in compounds] == [("Acetaldehyde", "CC=O")], "aldol condensation is not a compound"
    assert data["images"][0]["author"] == "Someone" and data["images"][0]["licence"] == "CC BY-SA 4.0"


def test_wikipedia_nothing_for_unknown_structure(monkeypatch):
    _patch(monkeypatch, lambda request: httpx.Response(200, json={"query": {"search": []}}))
    data, complete = wikipedia.search("AAAAAAAAAAAAAA-UHFFFAOYSA-N")
    assert complete and data["paragraphs"] == [] and data["title"] == ""
