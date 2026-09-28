"""Printable worksheets: a grid of structures, with or without names, plus
an answer key page."""

from __future__ import annotations

import io

from rdkit import Chem
from rdkit.Chem import rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .chem import ChemError

COLS, ROWS = 2, 4


def _png(smiles: str, annotate: bool, px: int = 600) -> bytes:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ChemError(f"Invalid SMILES: {smiles}")
    rdDepictor.Compute2DCoords(mol)
    Chem.WedgeMolBonds(mol, mol.GetConformer())
    d = rdMolDraw2D.MolDraw2DCairo(px, int(px * 0.7))
    d.drawOptions().addStereoAnnotation = annotate  # R/S labels would give stereo questions away
    d.drawOptions().bondLineWidth = 3
    d.DrawMolecule(mol)
    d.FinishDrawing()
    return d.GetDrawingText()


def build_pdf(title: str, items: list[dict], show_names: bool, answer_key: bool) -> bytes:
    """items: [{name, smiles}]. Returns PDF bytes."""
    if not items:
        raise ChemError("No molecules to print.")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    margin = 15 * mm
    cell_w = (w - 2 * margin) / COLS
    cell_h = (h - 2 * margin - 14 * mm) / ROWS
    per_page = COLS * ROWS
    pages = (len(items) + per_page - 1) // per_page

    def header(text: str, page: int):
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin, h - margin, text)
        c.setFont("Helvetica", 9)
        c.drawRightString(w - margin, h - margin, f"Page {page}")
        if not show_names:
            c.drawString(margin, h - margin - 5 * mm, "Name: ______________________________")

    for p in range(pages):
        header(title, p + 1)
        for k, item in enumerate(items[p * per_page : (p + 1) * per_page]):
            col, row = k % COLS, k // COLS
            x = margin + col * cell_w
            y = h - margin - 14 * mm - (row + 1) * cell_h
            c.setStrokeColorRGB(0.85, 0.85, 0.85)
            c.rect(x + 2 * mm, y + 2 * mm, cell_w - 4 * mm, cell_h - 4 * mm)
            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica", 9)
            c.drawString(x + 4 * mm, y + cell_h - 7 * mm, f"{p * per_page + k + 1}.")
            img = ImageReader(io.BytesIO(_png(item["smiles"], annotate=show_names)))
            img_w = cell_w - 10 * mm
            img_h = img_w * 0.7
            if img_h > cell_h - 20 * mm:
                img_h = cell_h - 20 * mm
                img_w = img_h / 0.7
            c.drawImage(img, x + (cell_w - img_w) / 2, y + 10 * mm, img_w, img_h, mask="auto")
            c.setFont("Helvetica", 8.5)
            if show_names:
                c.drawCentredString(x + cell_w / 2, y + 5 * mm, item["name"][:70])
            else:
                c.line(x + 6 * mm, y + 6 * mm, x + cell_w - 6 * mm, y + 6 * mm)
        c.showPage()

    if answer_key and not show_names:
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin, h - margin, f"{title}: answer key")
        c.setFont("Helvetica", 10)
        y = h - margin - 10 * mm
        for i, item in enumerate(items):
            c.drawString(margin, y, f"{i + 1}. {item['name']}")
            y -= 6 * mm
            if y < margin:
                c.showPage()
                c.setFont("Helvetica", 10)
                y = h - margin
        c.showPage()
    c.save()
    return buf.getvalue()
