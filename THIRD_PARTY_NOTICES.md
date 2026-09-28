# Third-party notices

Chem Forge is released under the MIT License (see `LICENSE`). It depends on the
open-source packages, data and online services listed below. None of their source
code is copied into this repository; the packages are installed by `npm` and
`uv`/`pip` and keep their own licenses. Anyone redistributing a built copy of
Chem Forge (for example a Docker image or a frontend bundle) must also follow
those licenses, which in practice means keeping their copyright and licence
notices. The installed packages ship them (`node_modules/<pkg>/LICENSE`, and
the `*.dist-info` folders for Python packages).

## Frontend (npm)

| Package | Licence | Use |
| --- | --- | --- |
| Ketcher (`ketcher-core`, `ketcher-react`, `ketcher-standalone`), EPAM Systems | Apache-2.0 | 2D structure editor |
| Indigo (`indigo-ketcher`), EPAM Systems, pulled in by Ketcher | Apache-2.0 | Chemistry engine for the editor |
| 3Dmol.js (`3dmol`) | BSD-3-Clause | 3D molecule viewer |
| React, React DOM | MIT | UI framework |

Ketcher and Indigo are licensed under the Apache License, Version 2.0. A copy is
available at <https://www.apache.org/licenses/LICENSE-2.0>. Chem Forge uses
these packages unmodified.

## Backend (Python)

| Package | Licence | Use |
| --- | --- | --- |
| RDKit | BSD-3-Clause | Cheminformatics: parsing, depiction, conformers, descriptors |
| OPSIN (Java; the `py2opsin` wheel bundles the OPSIN jar) | MIT | IUPAC name to structure |
| py2opsin | MIT | Python wrapper for the OPSIN jar |
| NumPy | BSD-3-Clause | Numerics |
| FastAPI | MIT | Web API |
| Pydantic | MIT | Request and response models |
| SQLAlchemy | MIT | Database |
| Uvicorn | BSD-3-Clause | ASGI server |
| RapidFuzz | MIT | Fuzzy name matching |
| ReportLab (open-source toolkit) | BSD-3-Clause | PDF worksheets |
| PyJWT | MIT | Login tokens |
| argon2-cffi | MIT | Password hashing |
| python-dotenv | BSD-3-Clause | Configuration |
| python-multipart | Apache-2.0 | Form parsing |
| huggingface_hub | Apache-2.0 | Optional database backup; reaction index download |
| httpx (installed with huggingface_hub) | BSD-3-Clause | HTTP calls to the online services below |
| pytest, pytest-xdist (development and testing) | MIT / MIT | Tests |

Chem Forge also needs a Java runtime (for example OpenJDK) to run OPSIN. It is
installed separately and is not distributed with this repository.

## Data

- **Chemical reactions from US patents (1976–Sep 2016)**, Daniel Lowe, figshare,
  <https://doi.org/10.6084/m9.figshare.5104873>, released under CC0 1.0. The
  Reactions tab reads an index built from this set (`backend/scripts/build_reactions.py`);
  the index is distributed separately (a Hugging Face dataset, downloaded into the
  Docker image at build time), and `backend/tests/fixtures_reactions.rsmi` holds 88 of
  its rows as a test fixture.

## Online services

When they can be reached, the backend queries these services at runtime. No
data from them is bundled in this repository. Results are shown with a note
naming the source, and use of each service is subject to its provider's terms.

- **PubChem**, National Center for Biotechnology Information (NCBI), U.S.
  National Library of Medicine: resolving names and structures.
  Kim, S. et al. *Nucleic Acids Res.* **2023**, 51 (D1), D1373–D1380.
- **NCI/CADD Chemical Identifier Resolver (CACTUS)**, National Cancer
  Institute: fallback name resolution.
- **nmrshiftdb2**, University of Cologne: predicted ¹H and ¹³C NMR shifts
  using HOSE codes. Steinbeck, C.; Kuhn, S. *Phytochemistry* **2004**, 65,
  2711–2717.
- **NIST Chemistry WebBook**, NIST Standard Reference Database Number 69:
  experimental IR and mass spectra. Linstrom, P. J.; Mallard, W. G., Eds.
  National Institute of Standards and Technology, Gaithersburg, MD.
  <https://doi.org/10.18434/T4D303>. NIST reference data is not relicensed
  under this project's MIT License.
- **OpenAlex** (OurResearch), with **Crossref** as a fallback: finding ChemRxiv
  preprints for the Literature tab. OpenAlex metadata is released under CC0.
  Priem, J.; Piwowar, H.; Orr, R. OpenAlex: A fully-open index of scholarly works,
  authors, venues, institutions, and concepts. arXiv:2205.01833, **2022**.
  Only titles, authors, dates and DOIs are shown; each links to the preprint on
  **ChemRxiv**, where the preprint's own licence applies.
- **Google Patents**: the Reactions tab links each example to its patent page.

## Software citations

If you use Chem Forge in teaching or research, please also cite the main tools
it builds on:

- RDKit: Open-Source Cheminformatics. <https://www.rdkit.org>
- Lowe, D. M.; Corbett, P. T.; Murray-Rust, P.; Glen, R. C. Chemical Name to
  Structure: OPSIN, an Open Source Solution. *J. Chem. Inf. Model.* **2011**,
  51 (3), 739–753. <https://doi.org/10.1021/ci100384d>
- Rego, N.; Koes, D. 3Dmol.js: Molecular Visualization with WebGL.
  *Bioinformatics* **2015**, 31 (8), 1322–1324.
  <https://doi.org/10.1093/bioinformatics/btu829>
- Ketcher, EPAM Systems. <https://github.com/epam/ketcher>
- Lowe, D. Chemical reactions from US patents (1976–Sep2016). figshare, **2017**.
  <https://doi.org/10.6084/m9.figshare.5104873>
