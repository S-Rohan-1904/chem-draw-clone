import os
import tempfile

os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import literature, resolver  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

OPENALEX_HIT = {
    "results": [
        {
            "doi": f"https://doi.org/10.26434/chemrxiv-2024-{i:05d}",
            "title": f"Benzaldehyde study {i}",
            "publication_date": "2024-01-0" + str(i % 9 + 1),
            "cited_by_count": i,
            "authorships": [{"author": {"display_name": n}} for n in ("A One", "B Two", "C Three", "D Four")],
        }
        for i in range(7)
    ]
    + [{"doi": "https://doi.org/10.26434/chemrxiv-2024-00001.v2", "title": "Benzaldehyde study 1", "authorships": []}],
}

CROSSREF_HIT = {
    "message": {
        "items": [
            {"DOI": "10.26434/chemrxiv.123.v1", "title": ["Oxidation of benzaldehyde"], "author": [{"given": "Ada", "family": "Lovelace"}], "posted": {"date-parts": [[2021, 3, 4]]}},
            {"DOI": "10.26434/chemrxiv.456.v1", "title": ["Something unrelated"], "author": [], "posted": {"date-parts": [[2021, 3, 4]]}},
        ]
    }
}


def _transport(openalex_status=200, crossref_status=200, calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.host)
        if request.url.host == "api.openalex.org":
            return httpx.Response(openalex_status, json=OPENALEX_HIT if openalex_status == 200 else {"error": "Rate limit exceeded"})
        return httpx.Response(crossref_status, json=CROSSREF_HIT)

    return httpx.MockTransport(handler)


def _patch_client(monkeypatch, transport):
    real = httpx.Client

    def fake(*args, **kwargs):
        kwargs["transport"] = transport
        return real(*args, **kwargs)

    monkeypatch.setattr(literature.httpx, "Client", fake)
    monkeypatch.setattr(literature, "enabled", lambda: True)


def test_openalex_results_link_to_chemrxiv(monkeypatch):
    _patch_client(monkeypatch, _transport())
    data, complete = literature.search(["Benzaldehyde"])
    assert complete and data["source"] == "OpenAlex"
    assert len(data["items"]) == 5
    first = data["items"][0]
    assert first["url"] == "https://chemrxiv.org/doi/full/10.26434/chemrxiv-2024-00000"
    assert first["authors"] == "A One, B Two, C Three et al."
    # The .v2 copy of preprint 1 is dropped as a duplicate.
    assert len({i["title"] for i in data["items"]}) == 5


def test_falls_back_to_crossref_and_keeps_only_matching_titles(monkeypatch):
    _patch_client(monkeypatch, _transport(openalex_status=429))
    data, complete = literature.search(["benzaldehyde"])
    assert complete and data["source"] == "Crossref"
    assert [i["title"] for i in data["items"]] == ["Oxidation of benzaldehyde"]
    assert data["items"][0]["url"] == "https://chemrxiv.org/doi/full/10.26434/chemrxiv.123.v1"
    assert data["items"][0]["date"] == "2021-03-04"


def test_both_down_is_not_cached(monkeypatch):
    _patch_client(monkeypatch, _transport(openalex_status=500, crossref_status=500))
    data, complete = literature.search(["benzaldehyde"])
    assert not complete and not data["available"]


def test_stereo_prefixes_dropped_from_search():
    assert literature.search_name("(-)-2-Butanol") == "2-Butanol"
    assert literature.search_name("(2R,3S)-2,3-dibromobutane") == "2,3-dibromobutane"
    assert literature.search_name("L-Alanine") == "Alanine"
    assert literature.search_name("Benzaldehyde") == "Benzaldehyde"
    # Catalogue style, descriptor after the name (PubChem titles look like this).
    assert literature.search_name("1,2-Dimethylcyclohexane, cis-") == "1,2-Dimethylcyclohexane"
    assert literature.search_name("1,2-Dimethylcyclohexane, (1S,2S)-") == "1,2-Dimethylcyclohexane"
    assert literature.search_name("Camphor, (+/-)-") == "Camphor"
    assert literature.search_name("protoporphyrin IX") == "protoporphyrin IX"


def test_tries_next_name_when_first_finds_nothing(monkeypatch):
    asked = []

    def handler(request: httpx.Request) -> httpx.Response:
        f = request.url.params.get("filter", "")
        asked.append(f)
        if request.url.host == "api.openalex.org" and "protoporphyrin" in f:
            return httpx.Response(200, json=OPENALEX_HIT)
        if request.url.host == "api.openalex.org":
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, json={"message": {"items": []}})

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    extra = []
    data, complete = literature.search(["3-[18-(2-Carboxyethyl)-7,12-bis(ethenyl)porphyrin-2-yl]propanoic acid", "protoporphyrin ix"],
                                       more=lambda: extra.append(1) or ["never needed"])
    assert complete and data["query"] == "protoporphyrin ix" and len(data["items"]) == 5
    assert extra == [], "the stereo-free lookup only runs when every name came back empty"


def test_falls_back_to_stereo_free_record(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.openalex.org":
            return httpx.Response(200, json=OPENALEX_HIT if "Dimethylcyclohexane" in request.url.params.get("filter", "") and "(1S" not in request.url.params.get("filter", "") else {"results": []})
        return httpx.Response(200, json={"message": {"items": []}})

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    data, complete = literature.search([], more=lambda: ["1,2-Dimethylcyclohexane"])
    assert complete and data["query"] == "1,2-Dimethylcyclohexane" and data["items"]


def test_endpoint_uses_pubchem_name_and_caches(monkeypatch):
    calls: list[str] = []
    _patch_client(monkeypatch, _transport(calls=calls))
    monkeypatch.setattr(resolver, "name_for_inchikey", lambda key: {"iupac": "benzaldehyde", "title": "Benzaldehyde", "cid": 240})
    with client:
        r = client.post("/api/analysis/literature", json={"smiles": "O=Cc1ccccc1"}).json()
        assert r["query"] == "Benzaldehyde" and len(r["items"]) == 5 and r["cached"] is False
        again = client.post("/api/analysis/literature", json={"smiles": "O=Cc1ccccc1"}).json()
        assert again["cached"] is True and calls.count("api.openalex.org") == 1


def test_endpoint_without_any_name(monkeypatch):
    monkeypatch.setattr(resolver, "name_for_inchikey", lambda key: None)
    with client:
        r = client.post("/api/analysis/literature", json={"smiles": "CC(C)(C)C(C)(C)C(C)(C)C1CC1"}).json()
        assert r["available"] is False and "no name to search" in r["reason"]


def test_crossref_fallback_is_retried_next_day(monkeypatch):
    from datetime import datetime, timedelta, timezone

    from app import cache
    from app.db import LiteratureCache, SessionLocal

    calls = []

    def search():
        calls.append(1)
        return {"available": True, "query": "x", "items": [{"title": "x"}], "source": "Crossref", "_v": literature.VERSION}, True

    with client:
        db = SessionLocal()
        try:
            cache.get_literature(db, "TESTKEY-CROSSREF", search)
            row = db.get(LiteratureCache, "TESTKEY-CROSSREF")
            row.created_at = datetime.now(timezone.utc) - timedelta(days=2)
            db.commit()
            cache.get_literature(db, "TESTKEY-CROSSREF", search)
        finally:
            db.close()
    assert len(calls) == 2


def test_full_text_is_the_last_resort(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.openalex.org":
            return httpx.Response(200, json=OPENALEX_HIT if request.url.params.get("search") else {"results": []})
        return httpx.Response(200, json={"message": {"items": []}})

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    data, complete = literature.search(["2-Methylcyclohexanol"])
    assert complete and data["match"] == "fulltext" and len(data["items"]) == 5
