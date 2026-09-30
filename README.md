# Chem Illustrator

Enter an IUPAC name or SMILES to get a 2D drawing and an interactive 3D model.
Stereo descriptors in the name (R/S, E/Z, cis/trans) are parsed by OPSIN, shown
with wedge bonds and labels in 2D, and enforced in the 3D conformer. Unspecified
stereocentres are marked with a question mark.

Peptides, DNA and RNA can be built from a sequence (one- or three-letter codes, or
HELM). Users can register, log in, save molecules and search the saved list by
structure. SVG, PNG, MOL and SMILES downloads are available.

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

The Draw tab opens a Ketcher editor, full width (the side lists are hidden there).
Draw a structure, use the wedge or hash bond tool for stereocentres, then press Build 3D.
The result shows the SMILES instead of a name (no offline name generation). Copy to
editor loads any result into the editor. The editor bundle is loaded only when the tab
is first opened.

- **Insert template** adds a ready-made structure to the canvas: the twenty amino acids,
  nucleobases and nucleosides, sugars (open chain and ring forms), steroids and terpenes,
  heterocycles, carbocycles, common reagents and solvents (`frontend/src/tools/templates.ts`).
- The editor exports V3000, so Ketcher's enhanced stereo marks are kept: centres drawn as
  racemic (AND) or relative (OR) produce a warning on the result saying the model shows one
  of the configurations.
- A drawn structure or SMILES with a valence or aromaticity problem is reported per atom
  (`C2 has 5 bonds, more than C can carry`) instead of a generic parse failure.

## Mistyped names

- Unicode dashes and quotes, stray spaces and trailing punctuation are cleaned before parsing.
- If a stereo descriptor does not fit the name (for example `(2R)-propan-2-ol`), the structure is built without it and a warning is shown.
- Failed parses return a plain-English reason, the unreadable fragment, and up to three "did you mean" names. Suggestions are never applied automatically.
- The input box checks validity while typing and offers autocomplete from the example list, names built before, and `backend/app/data/common_names.txt`.
- OPSIN runs as one long-lived process per mode (strict, ignore-bad-stereo) instead of one JVM per request. A process that does not answer within `CHEM_OPSIN_TIMEOUT` seconds (default 30) is killed and restarted.
- OPSIN only reads systematic nomenclature. A name it cannot parse (protoporphyrin IX, hemin, aspirin) is looked up in PubChem, then NCI CACTUS, on build (not while typing); the result is cached and shown with a "looked up" tag and the record it came from. Trivial names can be ambiguous (PubChem's "rosarin" is a Rhodiola glycoside, not the expanded porphyrin) and some literature names (turcasarin) are in no database: paste a SMILES or draw those. `CHEM_NAME_LOOKUP=0` turns the lookup off, `CHEM_LOOKUP_TIMEOUT` (seconds, default 6) bounds each request.

## Analysis cards and tabs

Under every built molecule (endpoints under `/api/analysis`, code in `backend/app/{analysis,acidbase,isotopes,sugars,conformers,transforms}.py`, UI in `frontend/src/analysis/`):

- **Structure and bonding**: chiral / achiral / meso with the reason, VSEPR shapes with ideal and measured angles, ring aromaticity with the Huckel count, degrees of unsaturation from formula and structure, oxidation states, bond polarity with a dipole estimate drawn on the 3D model, hydrogen bond sites and an ESOL solubility estimate.
- **Acids and bases**: rule-based pKa sites, pH slider with the dominant species drawn, net charge and isoelectric point. Textbook values per group, not per-molecule predictions.
- **Isotope labels**: D, T, 13C, 15N, 18O and others, with the isotopic formula and exact mass shift.
- **Fischer and Haworth**: Fischer projections with D/L for sugars and amino acids; Haworth projections with alpha/beta and D/L, all read from the 3D model.
- **Conformational energy**: MMFF94 torsion scan around a chosen bond with a linked Newman projection; energies of the two chairs of a substituted ring.
- **Conformers and energy** (`backend/app/tools.py`): ETKDG + MMFF94 ensemble of up to 8 distinct conformers with energy above the lowest, Boltzmann population at 298 K and heavy-atom RMSD, each viewable in 3D; "Minimise model" gives the steric energy of the shown geometry before and after minimisation.
- **Properties**: elemental analysis (atoms, mass and mass % per element) under the usual descriptors.
- **Reactions** (`backend/app/reactiondb.py`): recorded chemistry from Daniel Lowe's
  text-mined US patent grants and applications (1976–Sep 2016,
  [CC0](https://doi.org/10.6084/m9.figshare.5104873)), the
  [Chemical Reaction Database](https://doi.org/10.5281/zenodo.18109268) (CC BY 4.0) and
  [Rhea](https://www.rhea-db.org) enzyme reactions (CC BY 4.0): up to five reaction types
  that use the molecule and five that make it, ranked by the number of distinct reactions,
  each with one example, preferring the simplest that reports a yield (scheme, source link,
  year, yield) and the reacting atoms highlighted. Enzyme reactions are listed separately with
  their EC numbers. Textbook routes come first, in their own group: equations written in
  English Wikipedia compound articles, and preparation sentences whose named compounds balance
  to the molecule atom for atom, each drawn and linked to the article revision it was read from
  (`backend/scripts/wiki_reactions.py`, CC BY-SA 4.0), and the same for the sentences of
  PubChem's Methods of Manufacturing, whose named compounds carry PubChem CIDs
  (`backend/scripts/hsdb_reactions.py`). Every stereoisomer of a structure is looked up
  together, and rows whose example is another stereoisomer's say so. Under "Made by" the card also shows how
  the molecule is produced, in text: the manufacturing methods PubChem takes from the Hazardous Substances Data Bank
  (`backend/app/manufacture.py`), and the production or synthesis section of its English
  Wikipedia article with the scheme pictures in it (`backend/app/wikipedia.py`, article found
  by InChIKey through Wikidata, text CC BY-SA 4.0, pictures credited from Wikimedia Commons).
  Compounds named in either open with a click. Reaction SMILES inputs get the functional groups lost and gained and a
  guess at the reaction type.
- **Literature** (`backend/app/literature*.py`): a card below Reactions with three lists.
  *ChemRxiv*: up to five preprints found by the molecule's PubChem name (then synonyms), via
  OpenAlex (Crossref as fallback), each with the abstract sentence that names it.
  *Journals*: articles PubChem links to the exact structure (PubMed), with details from
  Europe PMC, ranked by citations with recent articles and titles naming the molecule first.
  *Patents*: the US patents whose worked examples make or use the molecule, from the reaction
  index, with titles from PubChem, plus a link to PubChem's full patent list.
- **Reaction SMILES** (`A.B>>C`): drawn with agents over the arrow and an atom balance check. Atom-map numbers colour matching atoms on both sides. A stoichiometry grid takes coefficients and masses and returns mmol, equivalents, the limiting reagent, theoretical yield and percent yield.
- **Mechanisms tab**: twenty curved-arrow mechanisms drawn step by step with captions.

## Spectra

Every built molecule gets a Spectra card with four tabs. Hovering a peak or band
highlights the atoms responsible in the 2D drawing.

- **1H / 13C NMR**: number of signals is exact (symmetry classes of the structure);
  integrations are computed locally. Shifts come from the nmrshiftdb2 HOSE-code
  prediction service when reachable, otherwise from additive substituent rules
  (teaching accuracy only).
- **Couplings** (`backend/app/couplings.py`): first-order J values and multiplet patterns
  (d, dd, td, ...). 7 Hz across freely rotating bonds, Karplus J from the dihedral in the
  lowest-energy MMFF conformer inside rings, 16 / 10.5 Hz trans / cis on alkenes, 8 / 2 Hz
  ortho / meta, 2.5 Hz aldehyde; O-H and N-H are broad singlets. Equivalent partners that
  differ in J (axial / equatorial, cis / trans on a =CH2) are split apart. The spectrum
  draws each multiplet from its J values, exaggerated for visibility.
- **IR**: characteristic bands from the functional groups present, drawn as a synthetic
  transmittance curve, with the experimental spectrum from the NIST Chemistry WebBook
  overlaid when NIST has one.
- **Mass spec**: molecular-ion isotope pattern (Cl/Br/S visible), NIST's experimental EI
  spectrum when available, and a fragmentation tree (`backend/app/msfrag.py`): single-bond
  cleavages ranked by stability (acylium, benzylic/allylic, alpha to a heteroatom), the
  McLafferty rearrangement, neutral losses (H2O, CO, HCN, CO2, HX, NH3), then second-step
  ions (acylium −CO, tropylium −C2H2, alkyl −C2H4). Each ion is drawn with its charge and,
  with Cl / Br, its isotope cluster; an ion reachable both directly and stepwise is listed
  once under its precursor.

Results are cached per molecule (`SPECTRA_VERSION` in `backend/app/cache.py` invalidates
old rows when the payload changes). `CHEM_SPECTRA_LOOKUP=0` keeps everything local (no
nmrshiftdb2 or NIST requests); `CHEM_SPECTRA_TIMEOUT` (seconds, default 10) bounds each
request. Experimental data: NIST Chemistry WebBook, NIST Standard Reference Database 69.

### Reaction index

The Reactions card reads `backend/reactions.db` (override with `CHEM_REACTIONS_DB`), built
once on a developer machine and published as a public Hugging Face dataset. Lowe's USPTO
files (figshare 5104873, the grants and applications `*_smiles.7z`) are atom-mapped already;
Rhea (`rhea-reaction-smiles.tsv`, `rhea-directions.tsv`, `rhea2ec.tsv` from
<https://ftp.expasy.org/databases/rhea/tsv/>) and the Chemical Reaction Database
(`reactionSmilesFigShare2025.txt`, Zenodo 18109268) are mapped first with RXNMapper, which
runs in a throwaway environment so torch never enters the project (CRD takes a few hours;
the output is appended to, so a stopped run resumes). The Wikipedia equations are read from
the wikitext of every English article about a compound with an InChIKey in Wikidata
(about 22,000; `fetch` downloads them once, `extract` writes `wiki_reactions.tsv`):

```bash
cd backend
MAP='uv run --isolated --no-project --python 3.12 --with rxnmapper --with transformers>=4.40,<4.50 --with rdkit --with setuptools<81 python scripts/map_reactions.py'
$MAP rhea path/to/rhea-tsv-folder rhea_mapped.tsv
$MAP crd path/to/reactionSmilesFigShare2025.txt crd_mapped.tsv
uv run python scripts/wiki_reactions.py fetch wiki && uv run python scripts/wiki_reactions.py extract wiki
$MAP wiki wiki/wiki_reactions.tsv wiki_mapped.tsv
uv run python scripts/hsdb_reactions.py fetch hsdb && uv run python scripts/hsdb_reactions.py extract hsdb
$MAP hsdb hsdb/hsdb_reactions.tsv hsdb_mapped.tsv
uv run python scripts/build_reactions.py -j 8 --uspto 1976_Sep2016_USPTOgrants_smiles.rsmi \
    2001_Sep2016_USPTOapplications_smiles.rsmi --crd crd_mapped.tsv --rhea rhea_mapped.tsv \
    --wiki wiki_mapped.tsv --hsdb hsdb_mapped.tsv
HF_TOKEN=... uv run python scripts/reactions_index.py upload <hf-user>/chem-forge-reactions
```

`setup.sh` and the Docker build download it when `REACTIONS_REPO=<hf-user>/chem-forge-reactions`
is set; without it the card says the index is not installed. Literature lookups are cached per
molecule and source for 30 days; `CHEM_LITERATURE_LOOKUP=0` turns them off, and a free
`OPENALEX_API_KEY` avoids OpenAlex's rate limit on anonymous searches.

## Deploy: Azure VM

The app runs on one Azure VM (Ubuntu, `Standard_B2pls_v2`: 2 Arm vCPU, 4 GB RAM) with
Docker Compose, from `deploy/azure/`. Caddy sits in front and gets the HTTPS certificate
itself. Accounts and saved molecules live in a Docker volume on the VM's disk, so they
survive rebuilds. The VM does not sleep, so there are no cold starts.

Setup, once, from your machine:

1. Azure CLI (`brew install azure-cli`) and `az login`.
2. Create the VM. It generates the SSH key `~/.ssh/chemforge_azure` if missing, opens
   ports 80 and 443, installs Docker and clones this repository to `/opt/chemforge`:

   ```bash
   LOCATION=centralindia DNS_LABEL=chemillustrator ./deploy/azure/create-vm.sh
   ```

   The site is then `https://<DNS_LABEL>.<LOCATION>.cloudapp.azure.com`.
3. Fill in the settings on the VM, in `/opt/chemforge/deploy/azure/.env` (see
   `.env.example`; `SITE_ADDRESS` and `SECRET_KEY` are already set): `REACTIONS_REPO`
   (see Reaction index), optionally `OPENALEX_API_KEY`, `ADMIN_USERS` with the usernames
   (comma separated) that may open the Stats tab, and `ADMIN_SIGNUP_CODE` with a secret
   of your choice.

   ```bash
   ssh -i ~/.ssh/chemforge_azure azureuser@<host> nano /opt/chemforge/deploy/azure/.env
   ```

4. First deploy. The first build takes about 10 minutes:

   ```bash
   ./deploy/azure/deploy.sh
   ```

5. Register each admin name with the code (the sign up form cannot, so nobody
   else can claim the name first):

   ```bash
   curl -X POST https://<host>/api/auth/register \
     -H 'Content-Type: application/json' \
     -d '{"username": "<admin>", "password": "<password>", "admin_code": "<ADMIN_SIGNUP_CODE>"}'
   ```

   Names in `ADMIN_USERS` cannot be registered without it; accounts that
   already exist are unaffected.

`LOCATION`, `DNS_LABEL`, `KEY` and `HOST` override the defaults in every script.

### Automatic deploys

`.github/workflows/deploy.yml` deploys every push to main once CI has passed on it:
it connects to the VM over SSH, fast forwards `/opt/chemforge` to that commit (never
backwards, so an older run finishing late changes nothing), rebuilds, restarts and
checks `/api/health`. Runs never overlap. It can also be started by hand from the
Actions tab (Deploy, Run workflow).

It uses its own SSH key, not yours. On the VM that key is limited to running
`deploy/azure/update.sh`: no shell, no port forwarding. Set it up once, after the
first deploy and with the GitHub CLI signed in (`gh auth login`):

```bash
./deploy/azure/setup-ci.sh
```

This creates `~/.ssh/chemforge_github_deploy`, adds it to the VM with that limit, and
stores in the repository's Actions settings the secrets `AZURE_SSH_KEY` (the private
key) and `AZURE_KNOWN_HOSTS` (the VM's host key as your machine already trusts it, so
Actions refuses an impostor) and the variable `AZURE_HOST`. Until then the Deploy
workflow fails at the SSH step and nothing on the VM changes. To revoke it, delete
the `chemforge-github-deploy` line from `~/.ssh/authorized_keys` on the VM.

Manual deploys with `./deploy/azure/deploy.sh` still work alongside it.

### Backups

Optional: set `HF_DATASET_REPO` (`<hf-user>/chem-draw-data`, a private Hugging Face
dataset) and a **Write** `HF_TOKEN` (https://huggingface.co/settings/tokens) in `.env`,
and the app mirrors `data.db` there whenever it changed (every `HF_SYNC_SECONDS`,
default 120) and on shutdown. At startup it replaces the local `data.db` with the
latest copy from the dataset, so only one running deployment may use a given dataset.

`render.yaml` is the older Render free tier setup (512 MB, sleeps when idle, no disk,
so it relies on the dataset above); it is kept for reference.

Common molecules: the image build runs `backend/scripts/prewarm.py`, which caches every
name in `common_names.txt` into `backend/prewarm.db`; at startup rows missing from the
live database are imported, so common molecules are instant.

Rate limits are per client address, in separate buckets: building new
molecules and other heavy work (`RATE_LIMIT_PER_MIN`, default 30, burst
`RATE_LIMIT_BURST` 10; the analysis cards only count when they would build a
molecule that is not cached), the checks made while typing
(`TYPING_RATE_LIMIT_PER_MIN`, 120), and login / register
(`AUTH_RATE_LIMIT_PER_MIN`, 10). `X-Forwarded-For` is only trusted when
`TRUSTED_PROXY_HOPS` says how many proxies sit in front (Caddy on Azure: 1, set in
`deploy/azure/docker-compose.yml`); otherwise
anyone could send a new address with every request.

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

## Sequences and saved-list search

- Under the Name input, "Build from a peptide or nucleotide sequence" accepts a peptide as
  one-letter (`AGSK`) or three-letter (`Ala-Gly-Ser`) codes in the L or D series, DNA or
  RNA written 5' to 3', or HELM (`PEPTIDE1{A.G.S}$$$$`). The limit is the viewer's 150
  heavy atoms (about 18 amino acids or 7 nucleotides).
- The search box above the saved list takes a SMILES or SMARTS: entries containing it as a
  substructure are shown; with no substructure hit the list is ranked by Morgan / Tanimoto
  similarity instead.

## Notes

- Names with impossible stereo (for example `(1S,4R)-camphor`) are rejected with an error.
- Atom numbers in tooltips follow the model's atom order, not IUPAC locants.

## Licence

MIT, copyright 2026 S Rohan and Nitika Grover, BITS Pilani (see `LICENSE`).
Third-party packages, data and services keep their own terms; see
`THIRD_PARTY_NOTICES.md`.
