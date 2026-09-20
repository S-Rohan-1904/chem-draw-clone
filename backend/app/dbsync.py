"""Keep the SQLite file alive across container restarts by mirroring it to a
Hugging Face dataset repo. Only active when HF_DATASET_REPO and HF_TOKEN are
set; otherwise a no-op.

Startup: download the latest copy (if any) to CHEM_DB_PATH.
Runtime: a background thread snapshots the DB with sqlite's backup API and
uploads it whenever it changed, at most every HF_SYNC_SECONDS (default 120).
Shutdown: one final upload, only if the DB changed since the last sync.

Zero-downtime deploys start the new instance while the old one is still
serving, and the old one uploads its final state only when it stops. So for
the first few minutes, while the local DB is still untouched, the new
instance keeps watching the dataset and re-pulls if a newer commit appears.
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
_remote_sha: str | None = None
_LATE_PULL_WINDOW = int(os.environ.get("HF_LATE_PULL_SECONDS", "300"))
status: dict = {"enabled": False, "restored": False, "last_upload": None, "last_error": None}


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


def _remote_revision() -> str | None:
    from huggingface_hub import HfApi

    try:
        return HfApi(token=TOKEN).dataset_info(REPO).sha
    except Exception:  # noqa: BLE001
        return None


def pull(db_path: str) -> None:
    global _remote_sha
    if not enabled():
        return
    from huggingface_hub import hf_hub_download
    from huggingface_hub.utils import EntryNotFoundError, RepositoryNotFoundError

    try:
        _remote_sha = _remote_revision()
        cached = hf_hub_download(REPO, REMOTE_NAME, repo_type="dataset", token=TOKEN, revision=_remote_sha)
    except (EntryNotFoundError, RepositoryNotFoundError):
        log.warning("no remote %s in %s yet; starting fresh", REMOTE_NAME, REPO)
        return
    except Exception as e:  # noqa: BLE001
        log.warning("could not pull DB: %s", e)
        status["last_error"] = f"pull: {e}"
        return
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(db_path).write_bytes(Path(cached).read_bytes())
    global _last_mtime
    _last_mtime = os.path.getmtime(db_path)
    status["restored"] = True
    log.warning("restored %s from %s", db_path, REPO)


def push(db_path: str) -> None:
    global _remote_sha, _last_mtime
    if not enabled() or not os.path.exists(db_path):
        return
    from huggingface_hub import HfApi

    tmp = _snapshot(db_path)
    try:
        _last_mtime = os.path.getmtime(db_path)
        HfApi(token=TOKEN).upload_file(
            path_or_fileobj=tmp,
            path_in_repo=REMOTE_NAME,
            repo_id=REPO,
            repo_type="dataset",
            commit_message="sync data.db",
        )
        status["last_upload"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _remote_sha = _remote_revision()
        log.warning("uploaded %s to %s", REMOTE_NAME, REPO)
    except Exception as e:  # noqa: BLE001
        status["last_error"] = f"push: {e}"
        log.warning("could not push DB: %s", e)
    finally:
        os.unlink(tmp)


def _changed_locally(db_path: str) -> bool:
    try:
        return os.path.getmtime(db_path) != _last_mtime
    except OSError:
        return False


def _loop(db_path: str) -> None:
    started = time.time()
    while not _stop.wait(INTERVAL if time.time() - started > _LATE_PULL_WINDOW else 20):
        if _changed_locally(db_path):
            push(db_path)
        elif time.time() - started <= _LATE_PULL_WINDOW:
            # Untouched so far: adopt a newer remote copy (old instance's final upload).
            sha = _remote_revision()
            if sha and sha != _remote_sha:
                log.warning("newer remote DB found after startup; re-pulling")
                pull(db_path)


def start(db_path: str) -> None:
    global _thread
    if not enabled():
        log.warning("DB sync disabled: set HF_TOKEN and HF_DATASET_REPO to persist data across restarts")
        return
    status["enabled"] = True
    from huggingface_hub import HfApi

    try:
        HfApi(token=TOKEN).create_repo(REPO, repo_type="dataset", private=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        status["last_error"] = f"create_repo: {e}"
        log.warning("could not ensure dataset repo %s: %s", REPO, e)
    pull(db_path)
    _thread = threading.Thread(target=_loop, args=(db_path,), daemon=True, name="dbsync")
    _thread.start()


def stop(db_path: str) -> None:
    if not enabled():
        return
    _stop.set()
    if _changed_locally(db_path):
        push(db_path)
    else:
        log.warning("DB unchanged since last sync; skipping final upload")
