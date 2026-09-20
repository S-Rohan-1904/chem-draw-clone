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
name (no offline name generation). Copy to editor loads any result into the editor.
The editor bundle is loaded only when the tab is first opened.

## Mistyped names

- Unicode dashes and quotes, stray spaces and trailing punctuation are cleaned before parsing.
- If a stereo descriptor does not fit the name (for example `(2R)-propan-2-ol`), the structure is built without it and a warning is shown.
- Failed parses return a plain-English reason, the unreadable fragment, and up to three "did you mean" names. Suggestions are never applied automatically.
- The input box checks validity while typing and offers autocomplete from the example list, names built before, and `backend/app/data/common_names.txt`.
- OPSIN runs as one long-lived process per mode (strict, ignore-bad-stereo) instead of one JVM per request.
- OPSIN only reads systematic nomenclature. A name it cannot parse (protoporphyrin IX, hemin, aspirin) is looked up in PubChem, then NCI CACTUS, on build (not while typing); the result is cached and shown with a "looked up" tag and the record it came from. Trivial names can be ambiguous (PubChem's "rosarin" is a Rhodiola glycoside, not the expanded porphyrin) and some literature names (turcasarin) are in no database: paste a SMILES or draw those. `CHEM_NAME_LOOKUP=0` turns the lookup off, `CHEM_LOOKUP_TIMEOUT` (seconds, default 6) bounds each request.

## Analysis cards and tabs

Under every built molecule (endpoints under `/api/analysis`, code in `backend/app/{analysis,acidbase,isotopes,sugars,conformers,transforms}.py`, UI in `frontend/src/analysis/`):

- **Structure and bonding**: chiral / achiral / meso with the reason, VSEPR shapes with ideal and measured angles, ring aromaticity with the Huckel count, degrees of unsaturation from formula and structure, oxidation states, bond polarity with a dipole estimate drawn on the 3D model, hydrogen bond sites and an ESOL solubility estimate.
- **Acids and bases**: rule-based pKa sites, pH slider with the dominant species drawn, net charge and isoelectric point. Textbook values per group, not per-molecule predictions.
- **Isotope labels**: D, T, 13C, 15N, 18O and others, with the isotopic formula and exact mass shift.
- **Fischer and Haworth**: Fischer projections with D/L for sugars and amino acids; Haworth projections with alpha/beta and D/L, all read from the 3D model.
- **Conformational energy**: MMFF94 torsion scan around a chosen bond with a linked Newman projection; energies of the two chairs of a substituted ring.
- **Reactions**: textbook reaction templates applied to the molecule (regiochemistry by Markovnikov, Zaitsev, Hofmann and ortho/para/meta rules) and one-step retrosynthetic disconnections; reaction SMILES inputs are classified and given an SN1/SN2/E1/E2 note.
- **Mechanisms tab**: twenty curved-arrow mechanisms drawn step by step with captions.

## Spectra

Every built molecule gets a Spectra card with four tabs. Hovering a peak or band
highlights the atoms responsible in the 2D drawing.

- **1H / 13C NMR**: number of signals is exact (symmetry classes of the structure);
  integration and n+1 multiplicities are computed locally. Shifts come from the
  nmrshiftdb2 HOSE-code prediction service when reachable, otherwise from additive
  substituent rules (teaching accuracy only).
- **IR**: characteristic bands from the functional groups present, drawn as a synthetic
  transmittance curve, with the experimental spectrum from the NIST Chemistry WebBook
  overlaid when NIST has one.
- **Mass spec**: molecular-ion isotope pattern (Cl/Br/S visible), likely fragment cations
  from single-bond cleavages ranked by stability (acylium, benzylic/allylic, alpha to a
  heteroatom), and NIST's experimental EI spectrum when available.

Results are cached per molecule. `CHEM_SPECTRA_LOOKUP=0` keeps everything local (no
nmrshiftdb2 or NIST requests); `CHEM_SPECTRA_TIMEOUT` (seconds, default 10) bounds each
request. Experimental data: NIST Chemistry WebBook, NIST Standard Reference Database 69.

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
   `<hf-user>/chem-draw-data`, and `ADMIN_USERS` with the usernames (comma
   separated) that may open the Stats tab. `SECRET_KEY` is generated.
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
| POST | `/api/tools/elemental` | `{smiles}` | mass % per element |
| POST | `/api/tools/sequence` | `{kind, sequence}` | peptide / d-peptide / dna / rna / helm to SMILES |
| POST | `/api/tools/conformers` | `{smiles, n}` | MMFF94 conformer ensemble with relative energies and populations |
| POST | `/api/tools/minimise` | `{smiles}` | energy of the shown model before and after minimisation |
| POST | `/api/tools/search` | `{query, mode}` | substructure / similarity search over the user's saved molecules (bearer) |
| POST | `/api/auth/register` | `{username, password}` | → `{token, username}` |
| POST | `/api/auth/login` | `{username, password}` | → `{token, username}` |
| GET | `/api/auth/me` | | bearer |
| GET/POST | `/api/saved` | `{label, input_text, smiles}` | bearer |
| DELETE | `/api/saved/{id}` | | bearer |

## Tools

- Properties card: elemental analysis (mass % per element).
- Name tab: build a peptide (one- or three-letter codes), DNA, RNA or HELM sequence.
- Conformers card: ETKDG + MMFF94 ensemble with relative energies, Boltzmann populations and RMSD; each conformer opens in a small 3D view. "Minimise model" reports the steric energy of the displayed geometry.
- Reactions: stoichiometry grid (coefficients, masses, mmol, equivalents, limiting reagent, theoretical and percent yield). Atom-mapped reaction SMILES colour matching atoms on both sides.
- Saved list: search by SMILES/SMARTS substructure, falling back to Morgan/Tanimoto similarity.
- Draw tab: "Insert template" adds amino acids, nucleobases, sugars, steroids, heterocycles and common reagents to the canvas. The editor exports V3000, so Ketcher's enhanced stereo marks (racemic AND, relative OR) are read and reported as a warning on the result.
- Invalid structures (valence, unkekulisable rings) are reported per atom instead of a generic parse failure.
- 1H NMR: first-order coupling constants and multiplet patterns (dd, td, ...). 7 Hz across freely rotating bonds, Karplus dihedrals from the lowest-energy conformer in rings, 16 / 10.5 Hz trans / cis on alkenes, 8 / 2 Hz ortho / meta; peaks are drawn with their real splitting.
- Mass spec: fragmentation tree. Single cleavages, McLafferty rearrangement and neutral losses (H2O, CO, HCN, CO2, HX, NH3), then second-step ions (acylium −CO, tropylium −C2H2, alkyl −C2H4); each ion has a drawing and, with Cl / Br, its isotope cluster.
- The Draw tab hides the side lists so the editor gets the full width.

## Notes

- Names with impossible stereo (for example `(1S,4R)-camphor`) are rejected with an error.
- Atom numbers in tooltips follow the model's atom order, not IUPAC locants.
