"""Publish or fetch the reaction index (reactions.db) through a Hugging Face dataset.

The index is built from openly licensed data (USPTO CC0, CRD and Rhea CC BY 4.0),
so the dataset can be public; the server then downloads it at image build time
without a token.

  upload:   HF_TOKEN=... uv run python scripts/reactions_index.py upload <user>/chem-forge-reactions
  download: uv run python scripts/reactions_index.py download <user>/chem-forge-reactions

`download` with no repo argument reads REACTIONS_REPO and does nothing when it is unset.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILENAME = "reactions.db"


def upload(repo: str, path: Path) -> None:
    from huggingface_hub import HfApi

    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("Set HF_TOKEN to a Hugging Face token with write access.")
    api = HfApi(token=token)
    api.create_repo(repo, repo_type="dataset", private=False, exist_ok=True)
    api.upload_file(
        path_or_fileobj=str(path),
        path_in_repo=FILENAME,
        repo_id=repo,
        repo_type="dataset",
        commit_message="Update reaction index",
    )
    print(f"Uploaded {path} ({path.stat().st_size / 1e6:.0f} MB) to https://huggingface.co/datasets/{repo}")


def download(repo: str, path: Path) -> None:
    from huggingface_hub import hf_hub_download

    # Straight into the target folder (not the shared HF cache), so the Docker
    # image holds one copy of the file, not two.
    got = Path(hf_hub_download(repo_id=repo, filename=FILENAME, repo_type="dataset",
                               token=os.environ.get("HF_TOKEN") or None, local_dir=path.parent))
    if got.resolve() != path.resolve():
        shutil.move(got, path)
    shutil.rmtree(path.parent / ".cache", ignore_errors=True)  # download bookkeeping only
    print(f"Downloaded {FILENAME} from {repo} to {path} ({path.stat().st_size / 1e6:.0f} MB)")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("upload", "download"):
        sys.exit(__doc__)
    repo = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("REACTIONS_REPO", "")
    path = Path(os.environ.get("CHEM_REACTIONS_DB", str(ROOT / FILENAME)))
    if not repo:
        if sys.argv[1] == "download":
            print("REACTIONS_REPO not set: skipping the reaction index download.")
            return
        sys.exit("Name the dataset repo, e.g. <user>/chem-forge-reactions.")
    upload(repo, path) if sys.argv[1] == "upload" else download(repo, path)


if __name__ == "__main__":
    main()
