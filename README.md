# IUPAC Structure Viewer

Enter an IUPAC name or SMILES to get a 2D drawing and an interactive 3D model.
Stereo descriptors in the name (R/S, E/Z, cis/trans) are parsed by OPSIN, shown
with wedge bonds and labels in 2D, and enforced in the 3D conformer. Unspecified
stereocentres are marked with a question mark.

Users can register, log in and save molecules. SVG, PNG, MOL and SMILES downloads
are available.

## Stack

- Backend: FastAPI + RDKit + [py2opsin](https://github.com/JacksonBurns/py2opsin) (OPSIN, needs a JVM), SQLite via SQLAlchemy, argon2 password hashing, JWT bearer auth.
- Frontend: Vite + React + TypeScript, [3Dmol.js](https://3dmol.csb.pitt.edu/) for the 3D viewer, [Ketcher](https://github.com/epam/ketcher) for drawing.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node 20+
- Java 8+ (macOS: `brew install openjdk`)

## Run

```bash
./setup.sh
```

installs Python and Node dependencies and writes `backend/.env` with a generated `SECRET_KEY`. Once. Then:

```bash
./start.sh
```

starts the backend on http://localhost:8000 and the site on http://localhost:5173. Open the second one. Ctrl-C stops both.

`BACKEND_PORT` and `FRONTEND_PORT` override the ports. Homebrew's `openjdk` is found automatically; set `JAVA_HOME` if Java lives elsewhere.

Tests: `cd backend && uv run pytest -n auto` (with Java on `PATH`).

Results are cached in SQLite: input text maps to SMILES (skips OPSIN), and
canonical SMILES maps to the full result (skips depiction and 3D embedding).
Responses carry `cached: true` on a hit. Delete `backend/data.db` or the
`name_cache` / `molecule_cache` tables to clear it.

JWTs are signed with `SECRET_KEY` from `backend/.env` (see `backend/.env.example`).
Regenerate with `openssl rand -base64 48`. Set `CHEM_DB_PATH` to move the SQLite file.

## Drawing

The Draw tab opens a Ketcher editor. Draw a structure, use the wedge or hash bond
tool for stereocentres, then press Build 3D. The result shows the SMILES instead of a
name (no offline name generation). Edit structure loads any result into the editor.
The editor bundle is loaded only when the tab is first opened.

## Mistyped names

- Unicode dashes and quotes, stray spaces and trailing punctuation are cleaned before parsing.
- If a stereo descriptor does not fit the name (for example `(2R)-propan-2-ol`), the structure is built without it and a warning is shown.
- Failed parses return a plain-English reason, the unreadable fragment, and up to three "did you mean" names. Suggestions are never applied automatically.
- The input box checks validity while typing and offers autocomplete from the example list, names built before, and `backend/app/data/common_names.txt`.
- OPSIN runs as one long-lived process per mode (strict, ignore-bad-stereo) instead of one JVM per request.

## Deploy (free): Render

Hugging Face Spaces only offer static hosting for free, so the backend runs on a
Render free web service instead (Docker, 512 MB RAM, no card). It sleeps after 15
minutes without traffic and wakes on the next visit in about a minute. New molecules
are slow on the small CPU; repeats are served from the cache.

`render.yaml` describes the service. Free instances have no persistent disk, so
saved molecules and accounts are mirrored to a private Hugging Face dataset
(free with an HF account): the app restores `data.db` from it at startup and uploads
a snapshot whenever it changed (every `HF_SYNC_SECONDS`, default 120) and on shutdown.
Without `HF_TOKEN` and `HF_DATASET_REPO` the app still runs, with a throwaway database.

Setup:

1. Hugging Face account (https://huggingface.co/join) and a **Write** token
   (https://huggingface.co/settings/tokens).
2. Render account (https://render.com, sign in with GitHub).
3. Render dashboard, New, Blueprint, pick this repo. Render reads `render.yaml`.
4. When prompted, fill `HF_TOKEN` with the token and `HF_DATASET_REPO` with
   `<hf-user>/chem-draw-data`. `SECRET_KEY` is generated.
5. Deploy. First build takes about 10 minutes.

Cold starts: the image build runs `backend/scripts/prewarm.py`, which caches every name
in `common_names.txt` into `backend/prewarm.db`; at startup rows missing from the live
database are imported, so common molecules are instant even on the small CPU. To keep
the free instance from sleeping during class hours, point a free external ping (for
example cron-job.org) at `https://<your-app>.onrender.com/api/health` every 10 minutes.

Local container run:

```bash
SECRET_KEY=$(openssl rand -base64 48) docker compose up --build
```

## API

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/molecule` | `{input}` | name, SMILES or molfile. Returns `{smiles, svg, molblock, stereo, formula, mw, inchi, inchikey, warnings, cached}`; on 400: `{detail, input, highlight, suggestions}` |
| POST | `/api/molecule/check` | `{input}` | parse only: `{ok, reason?, highlight?, warnings?}` |
| GET | `/api/molecule/suggest?q=` | | `{names}` autocomplete |
| POST | `/api/molecule/png` | `{smiles, width}` | PNG image |
| POST | `/api/auth/register` | `{username, password}` | → `{token, username}` |
| POST | `/api/auth/login` | `{username, password}` | → `{token, username}` |
| GET | `/api/auth/me` | | bearer |
| GET/POST | `/api/saved` | `{label, input_text, smiles}` | bearer |
| DELETE | `/api/saved/{id}` | | bearer |

## Notes

- Names with impossible stereo (for example `(1S,4R)-camphor`) are rejected with an error.
- Atom numbers in tooltips follow the model's atom order, not IUPAC locants.
