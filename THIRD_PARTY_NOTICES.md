# Third-party notices

Chem Illustrator is released under the MIT License (see `LICENSE`). It depends on the
open-source packages, data and online services listed below. None of their source
code is copied into this repository; the packages are installed by `npm` and
`uv`/`pip` and keep their own licenses. Anyone redistributing a built copy of
Chem Illustrator (for example a Docker image or a frontend bundle) must also follow
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
available at <https://www.apache.org/licenses/LICENSE-2.0>. Chem Illustrator uses
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
| RXNMapper, with PyTorch and Transformers (index building only, in a separate environment) | MIT / BSD-3-Clause / Apache-2.0 | Atom-mapping the Rhea and CRD reactions |

Chem Illustrator also needs a Java runtime (for example OpenJDK) to run OPSIN. It is
installed separately and is not distributed with this repository.

## Data

- **Chemical reactions from US patents (1976–Sep 2016)**, Daniel Lowe, figshare,
  <https://doi.org/10.6084/m9.figshare.5104873>, released under CC0 1.0. The
  Reactions tab reads an index built from this set (`backend/scripts/build_reactions.py`);
  the index is distributed separately (a Hugging Face dataset, downloaded into the
  Docker image at build time), and `backend/tests/fixtures_reactions.rsmi` holds 88 of
  its rows as a test fixture. Both the grants and the applications files are used.
- **Chemical Reaction Database**, Rik van der Lingen, Zenodo,
  <https://doi.org/10.5281/zenodo.18109268>, released under CC BY 4.0. Reactions from
  patents and papers, atom-mapped with RXNMapper and added to the reaction index; examples
  from it cite the dataset. `backend/tests/fixtures_reactions_crd.tsv` holds one mapped row.
- **Rhea**, the reaction knowledgebase, SIB Swiss Institute of Bioinformatics,
  <https://www.rhea-db.org>, released under CC BY 4.0. Bansal, P. et al. Rhea, the reaction
  knowledgebase in 2022. *Nucleic Acids Res.* **2022**, 50 (D1), D693–D700. Enzyme
  reactions (left-to-right direction, no generic R groups) are atom-mapped with RXNMapper
  and added to the reaction index, each linked to its Rhea entry and EC numbers.
  `backend/tests/fixtures_reactions_rhea.tsv` holds two mapped rows.
- **Wikipedia**, English Wikipedia articles about chemical compounds, by Wikipedia
  contributors, text under CC BY-SA 4.0. `backend/scripts/wiki_reactions.py` reads the
  reaction equations and preparation sentences in these articles (found through Wikidata
  InChIKeys, CC0) and turns them into reaction SMILES for the reaction index. Each reaction
  shown links to the article revision it came from.
- **Hazardous Substances Data Bank** (HSDB), U.S. National Library of Medicine, through
  PubChem (<https://pubchem.ncbi.nlm.nih.gov/source/11933>), a U.S. government work.
  `backend/scripts/hsdb_reactions.py` turns the sentences of its Methods of Manufacturing,
  whose compounds carry PubChem CIDs, into reactions for the reaction index; each one links
  to the compound's PubChem section and names the reference the method cites.

## Online services

When they can be reached, the backend queries these services at runtime. No
data from them is bundled in this repository. Results are shown with a note
naming the source, and use of each service is subject to its provider's terms.

- **PubChem**, National Center for Biotechnology Information (NCBI), U.S.
  National Library of Medicine: resolving names and structures; the PubMed articles and
  patent records linked to a compound for the Literature card.
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
  preprints, and details of the journal articles PubChem links, for the Literature card. OpenAlex metadata is released under CC0.
  Priem, J.; Piwowar, H.; Orr, R. OpenAlex: A fully-open index of scholarly works,
  authors, venues, institutions, and concepts. arXiv:2205.01833, **2022**.
  Only titles, authors, dates, journals, citation counts, DOIs and a short abstract excerpt
  are shown; each links to the article or to the preprint on **ChemRxiv**, where the work's
  own licence applies.
- **Google Patents**: the Reactions and Literature cards link each patent to its page.
- **PubChem, Hazardous Substances Data Bank (HSDB)**, U.S. National Library of Medicine:
  the "Methods of Manufacturing" text shown under "Made by", each method with the
  reference HSDB gives for it, linked to the compound's PubChem page.
- **Wikidata** and **Wikipedia** (Wikimedia Foundation): the article for a structure is
  found through its InChIKey on Wikidata (CC0), and the production or synthesis section of
  the English Wikipedia article is shown under "Made by". Wikipedia text is licensed under
  CC BY-SA 4.0 (<https://creativecommons.org/licenses/by-sa/4.0/>); the card names the
  article, links to it and states the licence. Scheme pictures are shown from **Wikimedia
  Commons** with their author and licence as given on each file's page.

## Software citations

If you use Chem Illustrator in teaching or research, please also cite the main tools
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
- Schwaller, P.; Hoover, B.; Reymond, J.-L.; Strobelt, H.; Laino, T. Extraction of organic
  chemistry grammar from unsupervised learning of chemical reactions. *Sci. Adv.* **2021**,
  7 (15), eabe4166. <https://doi.org/10.1126/sciadv.abe4166>
