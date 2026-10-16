# ChemDraw gap list

What ChemDraw does that the Draw tab and analysis cards do not, ranked by value
to this site against effort. Sources: the public ChemDraw 17.1 User Guide
(PerkinElmer, 2018) and Revvity release notes up to v26. Nothing here comes from
ChemDraw's code.

Effort: **S** about a day, **M** a few days, **L** a week or more, **XL** a research project.

## Already covered

Ketcher 3.14 (the Draw tab) already has:

- Bonds: single, double, triple, aromatic, wedge, hash, either (wavy), crossed
  double, dative, any, query bonds.
- Chains, ring templates, charges, radicals, isotopes.
- R-groups and S-groups (polymer brackets, superatoms, data groups).
- Enhanced stereo (ABS/AND/OR), CIP labels and Check Structure.
- Clean Up (layout), aromatize and dearomatize, flip and rotate, Calculated Values.
- Reaction arrows: plain, equilibrium, unbalanced, retrosynthetic, failed
  (no-go), elliptical arc, multi-tail.
- Reaction plus and atom mapping (manual and automatic).
- Shapes (ellipse, rectangle, line, polyline), text with sub- and superscript.
- Functional group and salt/solvent libraries.
- Open and save as MOL, RXN, SMILES, SMARTS, InChI, CML, KET, CDX and CDXML, plus SVG/PNG.
- Basic hover hotkeys: an element letter changes an atom, 1/2/3 changes bond order.

The rest of the site already has:

- Name to structure (OPSIN, then PubChem and CACTUS).
- 1H/13C NMR, which goes further than ChemNMR.
- Mass spec fragments.
- A stoichiometry grid (for reaction SMILES only).
- Properties and elemental analysis.
- Stereo descriptors.
- Sequence and HELM builder.
- 3D viewer.
- Structure templates.
- Saved-structure search.

## Tier 1: the things that make it feel like ChemDraw

| # | Gap | What ChemDraw does | Effort |
|---|-----|--------------------|--------|
| 1 | **Sprout hotkeys** | Hover over an atom and press: `1` single bond (linear), `0` single bond (cyclic), `2` C=O or acetyl, `3`/`a` phenyl, `4`/`5` wedge or hash plus Me, `6`/`7` cyclohexyl or cyclopentyl (spiro on a ring carbon), `8` =CH2, `9` gem-dimethyl or isopropyl, `z` alkyne. Shift+letter gives Ph, Ac, Na, Si, B, COOMe; `m`/`e` give Me/Et. `.` adds an attachment point, `'` an atom number, `=` opens nicknames, `/` opens atom properties. | M |
| 2 | **Bond hotkeys** | Hover over a bond and press: `a` fuse benzene, `z` fuse cyclopentadiene, `v` fuse cyclopropane, `4`-`8` fuse an n-membered ring, `9`/`0` fuse a chair cyclohexane. `l`/`r`/`c` move the double-bond line left, right or centre. `w`/`h`/Shift+`h` give wedge, hashed wedge or hashed. `y` wavy, `b` bold, `d` dashed, `f` bring to front. | M |
| 3 | **Keyboard hotspot navigation** | Arrow keys walk atom to bond to atom; Shift+arrow jumps atom to atom; Enter opens the label editor on the hotspot. Ctrl+arrow on a selection adds a reaction arrow and copies the selection to the other side. Without a hotspot, single letters switch tools (`x` bond, Shift+`x` chain, `t` text, `e` arrows, `j` benzene, `u` cyclohexane, Space marquee). | M |
| 4 | **Curved electron-pushing arrows** | Bezier arrows with full or half (fishhook) heads that snap to atoms, bonds and lone pairs and follow them when the structure moves. The curvature is dragged from a midpoint handle. Ketcher's arcs are free-floating, not anchored. | L |
| 5 | **Chemical symbols** | Lone-pair dots, radical dots, and circled + and − placed freely around an atom, for mechanism drawings. Ketcher keeps radicals only as an atom property. | M |
| 6 | **Document styles** | One-click ACS Document 1996, RSC and Wiley presets for bond length, line width, bold width, hash spacing, margin, font and size. Ketcher has these settings; it lacks the presets and a way to apply them to the whole canvas. | S |
| 7 | **Bond rendering details** | Bold and bold-wedge bonds, hollow wedge, hashed (non-wedge) bonds, and the double-bond position chosen per bond. Crossing gaps: the rear bond is cut where a front bond crosses it, which chair and perspective drawings need. This needs Ketcher render patches or post-processing of the SVG. | M-L |
| 8 | **Conformer templates on the canvas** | Chair, boat and Newman templates with their perspective 2D coordinates. Our chair and Newman pictures are analysis output only, and templates go in as SMILES, so their geometry is lost. Ship molfile templates instead. | S |

## Tier 2: teaching and illustration value

| # | Gap | What ChemDraw does | Effort |
|---|-----|--------------------|--------|
| 9 | **TLC plate tool** | Lanes, a baseline and a solvent front, with draggable spots that show Rf live. Spots can be shaded or tailing, and lanes labelled. | M |
| 10 | **Orbitals and drawing elements** | s, p, d, sp, sp2 and sp3 lobes (plain, shaded or filled, with phase colour), shaded spheres and arcs at 90/120/180/270°. Own SVG artwork, not ChemDraw's. | M |
| 11 | **Lab glassware clip art** | Flasks, condensers, columns and funnels that snap together (ChemDraw's Clipware and BioDraw templates). We have to draw our own set. | M |
| 12 | **Stoichiometry grid for drawn reactions** | ChemDraw puts the grid under a drawn scheme. The backend grid exists; send it the drawn reaction (Ketcher RXN to reaction SMILES) and show the grid under the canvas. | S |
| 13 | **Mass fragmentation tool** | Drag a cut line across bonds and get each fragment's formula and m/z drawn beside it. Our msfrag code could compute the fragment from the cut bond set. | M |
| 14 | **Colour and highlighting** | Colour per atom, bond or object; ring fill colour (v19); atom numbers shown on the canvas. Ketcher 3 has a highlight API, so this is mostly UI. | S-M |
| 15 | **Chemical text auto-format** | Typing H2SO4 or CH3CO2Et in a caption gives subscripts automatically; a formula-style or chemical-style caption option. | S |
| 16 | **Name to structure in the canvas** | Type or paste a name onto the canvas and convert it in place. We can reuse the existing `/api/molecule` path, then `addFragment`. | S |
| 17 | **Struct to name for any structure** | Ours names only what PubChem knows (`/api/molecule/name/{inchikey}`). ChemDraw generates IUPAC names for new structures. A real naming engine is XL; an honest "not in PubChem" fallback plus OPSIN round-trip checks is S. | S / XL |

## Tier 3: layout and power-user features

| # | Gap | Effort |
|---|-----|--------|
| 18 | Align, distribute, group and ungroup; bring to front and send to back for objects | M |
| 19 | Fixed length and fixed angle toggles (Ctrl+L, Ctrl+E), rulers, crosshair, an Info window showing position, angle and distance | M |
| 20 | Frames around a selection (box, brackets, braces); daggers | S |
| 21 | Pen tool: freehand Bezier curves with editable control points, which can become arrows | M |
| 22 | Custom nicknames: define your own abbreviation (OTBS, Ts, Boc); type it as an atom label; expand or contract | S-M |
| 23 | Expand generic structures (Markush enumeration of R-groups and alternative groups) | M |
| 24 | Structure perspective: rotate a 2D drawing in 3D, using RDKit coordinates | M |
| 25 | Turn on Ketcher's macromolecule (biopolymer) editor; it is currently off with `disableMacromoleculesEditor` | S |
| 26 | Copy as CDXML or MOL to the clipboard, and paste from ChemDraw; CDXML/CDX download for built molecules | S |
| 27 | Tables, multi-page documents and posters, page setup | M |

## Out of scope

ChemDraw/Excel, CombiChem, ChemScript, add-ins, ChemDraw Cloud, OLE embedding in
Office, SciFinder and Reaxys search, and the gel electrophoresis tool. These are
desktop or licensed integrations a website cannot reproduce, or have no value here.

## Where looking at ChemDraw's behaviour helps

The docs say what these features do, not exactly how. These are the behaviours to
check against the real program, then write our own code that matches:

1. Sprout and fusion geometry: the angle a sprouted bond takes for each substitution
   pattern, which side a fused ring goes on, and how chair orientations 9 and 0 differ.
2. Double-bond line placement: which side the second line goes on in rings and chains
   when the user has not chosen one.
3. Label justification: when a label flips to HO, H3C or H2N, and where charges and
   H counts sit.
4. Clean Up Structure: how far atoms may move and how ring shapes and angles are snapped.
5. Curved arrows: default curvature, and where the ends attach on atoms, bonds and lone pairs.
6. Style presets: the exact values of the ACS 1996, RSC and Wiley sheets (these are
   also published in journal author guides).

## Suggested order

1. Quick wins (S): items 6, 8, 12, 16, 25 and 26.
2. The ChemDraw keyboard feel: items 1-3 together, as one key-handler module over the Ketcher editor API.
3. Mechanisms: items 4 and 5, then 7 (crossing gaps for chairs).
4. Teaching tools: items 9, 10, 11 and 13.
