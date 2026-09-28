"""How a molecule is made, from its English Wikipedia article.

The article is found by structure, not name: Wikidata items carry the
InChIKey (property P235) and link to their Wikipedia article. The first
section headed Production, Synthesis, Preparation or similar is shown as
text (up to a few paragraphs, with text equations such as
2 CH₃CHO → CH₃CH=CHCHO + H₂O kept) together with the reaction scheme
pictures in it, each credited to its author and licence on Wikimedia
Commons. Linked names that are chemical compounds on Wikidata become buttons
that open them. Article text is CC BY-SA 4.0, credited with a link.
When the exact stereoisomer has no article, the compound without
stereochemistry is used. Never raises.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import unquote

import httpx

from .literature import MAILTO, _timeout, enabled

WIKIDATA = "https://www.wikidata.org/w/api.php"
WIKIPEDIA = "https://en.wikipedia.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = f"ChemIllustrator/1.0 (mailto:{MAILTO})"
# Section headings that describe making the compound, most useful first.
HEADINGS = [r"^(industrial )?production", r"synthes", r"^preparation", r"manufactur", r"^laboratory", r"^biosynthesis"]
MAX_CHARS = 900
MAX_IMAGES = 3
LICENCE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
VERSION = 1

_SUBSCRIPT = str.maketrans("0123456789+-", "₀₁₂₃₄₅₆₇₈₉₊₋")
_SUPERSCRIPT = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")


class _Section(HTMLParser):
    """Paragraphs (with the wiki links in them) and scheme pictures of one section's HTML."""

    SKIP = {"style", "script", "table", "math"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict] = []  # {"text", "links": [(start, length, title)]} or {"image": file, "src"}
        self._text: list[str] | None = None
        self._links: list[tuple[int, int, str]] = []
        self._link: tuple[int, str] | None = None
        self._skip = 0  # inside references, edit links, tables, maths
        self._script = ""  # "sub" or "sup"
        self._depth_skip: list[str] = []
        self._file = ""  # the File: page the next picture belongs to

    def _length(self) -> int:
        return sum(len(t) for t in self._text or [])

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        cls = a.get("class") or ""
        if self._skip:
            if tag in ("sup", "span", "div", "style", "table", "math", "ol", "ul"):
                self._depth_skip.append(tag)
                self._skip += 1
            return
        if tag in self.SKIP or "reference" in cls.split() or "mw-editsection" in cls or "mwe-math-element" in cls \
                or tag in ("h2", "h3", "h4") or (tag == "div" and "references" in cls) or (tag == "ol" and "references" in cls):
            self._depth_skip.append(tag)
            self._skip = 1
            return
        if tag in ("p", "dd", "li") and self._text is None:
            self._text, self._links = [], []
        elif tag == "a" and (a.get("href") or "").startswith("/wiki/File:"):
            self._file = unquote(a["href"][len("/wiki/File:"):]).replace("_", " ")
        elif tag == "img":
            # Scheme pictures sit between paragraphs or alone in an indented line.
            src = a.get("src") or ""
            file, self._file = self._file, ""
            if src and file:
                self.blocks.append({"image": file, "src": ("https:" + src) if src.startswith("//") else src,
                                    "width": int(a.get("data-file-width") or 0), "height": int(a.get("data-file-height") or 0)})
        elif tag == "a" and self._text is not None:
            href = a.get("href") or ""
            if href.startswith("/wiki/") and ":" not in href[6:]:
                self._link = (self._length(), unquote(href[6:]).replace("_", " ").split("#")[0])
        elif tag in ("sub", "sup"):
            self._script = tag
        elif tag == "br" and self._text is not None:
            self._text.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self._skip:
            if self._depth_skip and self._depth_skip[-1] == tag:
                self._depth_skip.pop()
                self._skip -= 1
            return
        if tag == "a" and self._link is not None and self._text is not None:
            start, title = self._link
            if self._length() > start:
                self._links.append((start, self._length() - start, title))
            self._link = None
        elif tag in ("sub", "sup"):
            self._script = ""
        elif tag in ("p", "dd", "li") and self._text is not None:
            raw = "".join(self._text)
            lead = len(raw) - len(raw.lstrip())
            if raw.strip():
                links = [(s - lead, n, t) for s, n, t in self._links if s >= lead]
                self.blocks.append({"text": raw.strip(), "links": links})
            self._text = None

    def handle_data(self, data: str) -> None:
        if self._skip or self._text is None:
            return
        if self._script and re.fullmatch(r"[0-9+\-]+", data.strip()):
            data = data.strip().translate(_SUBSCRIPT if self._script == "sub" else _SUPERSCRIPT)
        # Collapse whitespace as it arrives, so link offsets stay right.
        data = re.sub(r"\s+", " ", data)
        if data.startswith(" ") and self._text and self._text[-1].endswith(" "):
            data = data[1:]
        self._text.append(data)


def parse_section(section_html: str) -> dict:
    """{"paragraphs": [{"text", "links"}], "images": [{"file", "src", "width", "height"}]}, capped in length."""
    p = _Section()
    p.feed(section_html)
    paragraphs, images, used = [], [], 0
    for b in p.blocks:
        if "image" in b:
            if b["image"] and len(images) < MAX_IMAGES and used < MAX_CHARS:
                images.append({"file": b["image"], "src": b["src"], "width": b["width"], "height": b["height"], "after": len(paragraphs)})
            continue
        if used >= MAX_CHARS:
            break
        text = b["text"]
        if used + len(text) > MAX_CHARS:
            cut = text.rfind(" ", 0, MAX_CHARS - used)
            text = text[:max(cut, 40)].rstrip(" ,.;") + "…"
        paragraphs.append({"text": text, "links": [(s, n, t) for s, n, t in b["links"] if s + n <= len(text)]})
        used += len(text)
    return {"paragraphs": paragraphs, "images": images}


def _get(client: httpx.Client, url: str, params: dict) -> dict:
    r = client.get(url, params={**params, "format": "json", "formatversion": "2"})
    r.raise_for_status()
    return r.json()


def _article(client: httpx.Client, inchikey: str) -> str:
    """English Wikipedia title of the Wikidata item with this InChIKey, or ''."""
    hits = _get(client, WIKIDATA, {"action": "query", "list": "search", "srsearch": f"haswbstatement:P235={inchikey}", "srlimit": "3"})
    qids = [h["title"] for h in hits.get("query", {}).get("search", [])]
    if not qids:
        return ""
    ent = _get(client, WIKIDATA, {"action": "wbgetentities", "ids": "|".join(qids), "props": "sitelinks", "sitefilter": "enwiki"})
    for q in qids:
        link = ent.get("entities", {}).get(q, {}).get("sitelinks", {}).get("enwiki")
        if link:
            return link["title"]
    return ""


def _claim(entity: dict, prop: str) -> str:
    for c in (entity.get("claims") or {}).get(prop, []):
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(v, str):
            return v
    return ""


def _chemicals(client: httpx.Client, titles: list[str]) -> dict[str, str]:
    """{linked title: SMILES} for the links that are chemical compounds on Wikidata
    (the item has a SMILES), following Wikipedia's redirects and capitalisation."""
    found: dict[str, str] = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        q = _get(client, WIKIPEDIA, {"action": "query", "titles": "|".join(chunk), "redirects": "1",
                                     "prop": "pageprops", "ppprop": "wikibase_item"}).get("query", {})
        final = {t: t for t in chunk}
        for step in ("normalized", "redirects"):
            moves = {m["from"]: m["to"] for m in q.get(step, [])}
            final = {t: moves.get(f, f) for t, f in final.items()}
        qid = {p["title"]: (p.get("pageprops") or {}).get("wikibase_item") for p in q.get("pages", [])}
        ids = sorted({qid[f] for f in final.values() if qid.get(f)})
        if not ids:
            continue
        ent = _get(client, WIKIDATA, {"action": "wbgetentities", "ids": "|".join(ids), "props": "claims"}).get("entities", {})
        smiles = {k: _claim(e, "P2017") or _claim(e, "P233") for k, e in ent.items()}
        for t, f in final.items():
            if smiles.get(qid.get(f) or ""):
                found[t] = smiles[qid[f]]
    return found


def _credits(client: httpx.Client, files: list[str]) -> dict[str, dict]:
    """Author, licence and page of each Commons file."""
    if not files:
        return {}
    data = _get(client, COMMONS, {"action": "query", "titles": "|".join("File:" + f for f in files),
                                  "prop": "imageinfo", "iiprop": "extmetadata|url"})
    out = {}
    for page in data.get("query", {}).get("pages", []):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        artist = re.sub(r"<[^>]+>", "", html.unescape((meta.get("Artist") or {}).get("value", ""))).strip()
        out[page.get("title", "").removeprefix("File:")] = {
            "author": artist[:80],
            "licence": (meta.get("LicenseShortName") or {}).get("value", ""),
            "page": info.get("descriptionurl", ""),
        }
    return out


def search(inchikey: str) -> tuple[dict, bool]:
    """(payload, complete); incomplete means Wikipedia failed and the result should not be cached."""
    base = {"available": True, "title": "", "section": "", "url": "", "paragraphs": [], "images": [],
            "stereo_ignored": False, "licence_url": LICENCE_URL, "_v": VERSION}
    if not enabled() or not inchikey:
        return {**base, "available": False}, not inchikey
    try:
        with httpx.Client(timeout=_timeout(), follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            title, stereo_ignored = _article(client, inchikey), False
            if not title and inchikey[15:25] != "UHFFFAOYSA":
                title = _article(client, inchikey[:14] + "-UHFFFAOYSA-N")
                stereo_ignored = bool(title)
            if not title:
                return base, True
            toc = _get(client, WIKIPEDIA, {"action": "parse", "page": title, "prop": "tocdata", "redirects": "1"})
            sections = toc.get("parse", {}).get("tocdata", {}).get("sections", [])
            chosen = None
            for pattern in HEADINGS:
                chosen = next((s for s in sections if re.search(pattern, re.sub(r"<[^>]+>", "", s["line"]), re.I)), None)
                if chosen:
                    break
            if chosen is None:
                return {**base, "title": title, "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"}, True
            body = _get(client, WIKIPEDIA, {"action": "parse", "page": title, "section": chosen["index"], "prop": "text",
                                            "redirects": "1", "disableeditsection": "1", "disablelimitreport": "1"})
            parsed = parse_section(body.get("parse", {}).get("text", ""))
            linked = sorted({t for p in parsed["paragraphs"] for _, _, t in p["links"]})
            chemicals = _chemicals(client, linked) if linked else {}
            credits = _credits(client, [im["file"] for im in parsed["images"]])
    except (httpx.HTTPError, ValueError, KeyError):
        return {**base, "available": False}, False
    paragraphs = [{"text": p["text"], "compounds": [{"start": s, "length": n, "name": t, "smiles": chemicals[t]}
                                                   for s, n, t in p["links"] if t in chemicals and t != title]}
                  for p in parsed["paragraphs"]]
    images = [{**im, **credits.get(im["file"], {"author": "", "licence": "", "page": ""})} for im in parsed["images"]]
    anchor = chosen.get("anchor") or ""
    return {**base, "title": title, "section": re.sub(r"<[^>]+>", "", chosen["line"]), "paragraphs": paragraphs, "images": images,
            "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}#{anchor}", "stereo_ignored": stereo_ignored}, True
