"""Papers whose reactions in the Open Reaction Database use or make a molecule.

The index (app/data/ord_papers.db, built by scripts/ord_papers.py from the ORD's public
data, CC BY-SA 4.0) maps each InChIKey to the DOIs of the papers its reactions
come from, with the paper's details read from OpenAlex at build time. It is a
local file, so the lookup needs no network and is not cached. When the file is
missing the source is simply left out. Never raises.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "ord_papers.db"
LIMIT = 20
_LOCAL = threading.local()


def db_path() -> Path:
    return Path(os.environ.get("CHEM_ORD_DB", str(DEFAULT_PATH)))


def _connection() -> sqlite3.Connection | None:
    """One read-only connection per thread (sqlite3 connections are not shared across threads)."""
    path = db_path()
    con = getattr(_LOCAL, "con", None)
    if con is not None and getattr(_LOCAL, "path", None) == path:
        return con
    if not path.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    except sqlite3.Error:
        return None
    _LOCAL.con, _LOCAL.path = con, path
    return con


def available() -> bool:
    return _connection() is not None


def search(inchikey: str) -> dict:
    """{available, items, total} in the journal sources' payload shape."""
    con = _connection()
    if con is None:
        return {"available": True, "items": [], "total": 0, "installed": False}
    try:
        rows = con.execute(
            "SELECT p.doi, p.title, p.authors, p.journal, p.year, p.cited_by, p.oa_url, p.type, l.roles, l.reactions "
            "FROM links l JOIN papers p ON p.doi = l.doi WHERE l.inchikey = ? ORDER BY l.reactions DESC, p.cited_by DESC LIMIT ?",
            (inchikey, LIMIT)).fetchall()
        total = con.execute("SELECT COUNT(*) FROM links WHERE inchikey = ?", (inchikey,)).fetchone()[0]
    except sqlite3.Error:
        return {"available": True, "items": [], "total": 0, "installed": False}
    items = [{
        "title": title, "authors": authors or "", "journal": journal or "", "year": year, "date": "", "doi": doi, "pmid": "",
        "url": f"https://doi.org/{doi}", "cited_by": cited_by or 0, "type": kind or "article", "oa_url": oa_url or "",
        "ord": {"roles": roles.split(","), "reactions": reactions},
    } for doi, title, authors, journal, year, cited_by, oa_url, kind, roles, reactions in rows if title]
    return {"available": True, "items": items, "total": total, "installed": True}
