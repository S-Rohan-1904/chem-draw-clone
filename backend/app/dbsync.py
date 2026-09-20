"""Keep the SQLite file alive across container restarts by mirroring it to a
Hugging Face dataset repo. Only active when HF_DATASET_REPO and HF_TOKEN are
set; otherwise a no-op.

Startup: download the latest copy (if any) to CHEM_DB_PATH.
Runtime: a background thread snapshots the DB with sqlite's backup API and
uploads it whenever it changed, at most every HF_SYNC_SECONDS (default 120).
Shutdown: one final upload.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

log = logging.getLogger("dbsync")

REPO = os.environ.get("HF_DATASET_REPO", "")
TOKEN = os.environ.get("HF_TOKEN", "")
INTERVAL = int(os.environ.get("HF_SYNC_SECONDS", "120"))
REMOTE_NAME = "data.db"

_stop = threading.Event()
_thread: threading.Thread | None = None
_last_mtime = 0.0


def enabled() -> bool:
    return bool(REPO and TOKEN)


def _snapshot(db_path: str) -> str:
    """Consistent copy of the live DB (safe while the app is writing)."""
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(tmp)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    return tmp


def pull(db_path: str) -> None:
    if not enabled():
        return
    from huggingface_hub import hf_hub_download
    from huggingface_hub.utils import EntryNotFoundError, RepositoryNotFoundError

    try:
        cached = hf_hub_download(REPO, REMOTE_NAME, repo_type="dataset", token=TOKEN)
    except (EntryNotFoundError, RepositoryNotFoundError):
        log.info("no remote %s yet; starting fresh", REMOTE_NAME)
        return
    except Exception as e:  # noqa: BLE001
        log.warning("could not pull DB: %s", e)
        return
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(db_path).write_bytes(Path(cached).read_bytes())
    global _last_mtime
    _last_mtime = os.path.getmtime(db_path)
    log.info("restored %s from %s", db_path, REPO)


def push(db_path: str) -> None:
    if not enabled() or not os.path.exists(db_path):
        return
    from huggingface_hub import HfApi

    tmp = _snapshot(db_path)
    try:
        HfApi(token=TOKEN).upload_file(
            path_or_fileobj=tmp,
            path_in_repo=REMOTE_NAME,
            repo_id=REPO,
            repo_type="dataset",
            commit_message="sync data.db",
        )
        log.info("uploaded %s to %s", REMOTE_NAME, REPO)
    except Exception as e:  # noqa: BLE001
        log.warning("could not push DB: %s", e)
    finally:
        os.unlink(tmp)


def _loop(db_path: str) -> None:
    global _last_mtime
    while not _stop.wait(INTERVAL):
        try:
            mtime = os.path.getmtime(db_path)
        except OSError:
            continue
        if mtime != _last_mtime:
            push(db_path)
            _last_mtime = mtime


def start(db_path: str) -> None:
    global _thread
    if not enabled():
        return
    from huggingface_hub import HfApi

    try:
        HfApi(token=TOKEN).create_repo(REPO, repo_type="dataset", private=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        log.warning("could not ensure dataset repo: %s", e)
    pull(db_path)
    _thread = threading.Thread(target=_loop, args=(db_path,), daemon=True, name="dbsync")
    _thread.start()


def stop(db_path: str) -> None:
    if not enabled():
        return
    _stop.set()
    push(db_path)
