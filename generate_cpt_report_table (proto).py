#!/usr/bin/env python3
"""
Génération du rapport CPT (Sondage au Pénétromètre Statique)
Reproduction fidèle de la mise en page Excel avec reportlab.
Script standalone - génère le PDF dans le même répertoire que le script.
"""


import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import black
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ---------------------------------------------------------------------------
# LOGO — modifier ce chemin pour pointer vers votre fichier logo
# Formats supportés : PNG, JPG. Mettre None pour ne pas afficher de logo.
# ---------------------------------------------------------------------------
LOGO_PATH = "icons/inisma.jpg"
LOGO_WIDTH = 145
LOGO_HEIGHT = 70
LOGO_V_OFFSET = 15  # augmenter pour remonter ecore (valeur en points)


# ---------------------------------------------------------------------------
# CARACTÈRE PHI
# ---------------------------------------------------------------------------
PHI = "\u03C6"  # ϕ — forme ingénieur (trait vertical)

# ---------------------------------------------------------------------------
# POLICES — Calibri sur Windows, Carlito (clone open-source) en fallback
# ---------------------------------------------------------------------------
def register_fonts():
    """Enregistre Calibri (Windows) ou Carlito (Linux fallback), puis Arial."""
    calibri_paths = {
        "Calibri":      ["C:/Windows/Fonts/calibri.ttf",
                         "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf"],
        "Calibri-Bold": ["C:/Windows/Fonts/calibrib.ttf",
                         "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf"],
    }
    for name, paths in calibri_paths.items():
        for p in paths:
            if os.path.exists(p):
                try:
                    pdfmetrics.registerFont(TTFont(name, p))
                    break
                except Exception:
                    continue

    # --- Arial (pour les colonnes ϕ', ϕ_u, Nq, Nγ) ---
    arial_paths = {
        "Arial":      ["C:/Windows/Fonts/arial.ttf",
                       "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"],
        "Arial-Bold": ["C:/Windows/Fonts/arialbd.ttf",
                       "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf"],
    }
    for name, paths in arial_paths.items():
        for p in paths:
            if os.path.exists(p):
                try:
                    pdfmetrics.registerFont(TTFont(name, p))
                    break
                except Exception:
                    continue


register_fonts()


FONT_NORMAL = "Calibri"
FONT_BOLD = "Calibri-Bold"

try:
    pdfmetrics.getFont(FONT_NORMAL)
except KeyError:
    FONT_NORMAL = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"

# Polices Arial (fallback sur Calibri si Arial absent)
try:
    pdfmetrics.getFont("Arial")
    FONT_ARIAL      = "Arial"
    FONT_ARIAL_BOLD = "Arial-Bold"
except KeyError:
    FONT_ARIAL      = FONT_NORMAL
    FONT_ARIAL_BOLD = FONT_BOLD


# ---------------------------------------------------------------------------
# DATA
# ---------------------------------------------------------------------------
HEADER_INFO = {
    "location": "MONCEAU-SUR-SAMBRE",
    "street": "Chemin des Raleurs",
    "test_type": "SONDAGE AU PENETROMETRE STATIQUE",
    "test_id": "P2",
    "company_line1": "Géotechnique et Environnement Sol - 32(0)65/40 34 34 - Fax: 32(0)65/34 80 05",
    "company_line2": "Avenue Gouverneur Cornez 4, B-7000 Mons (Belgique) - www.bcrc.be",
    "dossier": "48969",
    "date": "11/2024",
    "prof_atteinte": "10,00 m",
    "cote_depart": "44,95 m",
}


# fmt: off
DATA_ROWS = [
    ("0,20", "44,75",   "7,3",   "0,04", "31,7", "31,7", "22,4", "19,8",  "1,5",  "3,1", "303,2"),
    ("0,40", "44,55",  "13,3",   "0,07", "31,2", "31,2", "21,1", "18,3",  "1,8",  "3,2", "276,6"),
    ("0,60", "44,35",  "11,4",   "0,11", "30,0", "27,7", "15,7", "10,7",  "1,4",  "2,3", "158,5"),
    ("0,80", "44,15",  "11,4",   "0,14", "30,0", "25,5", "13,6",  "7,8",  "1,4",  "2,0", "118,9"),
    ("1,00", "43,95",   "9,4",   "0,18", "30,0", "22,2", "11,1",  "4,7",  "1,3",  "1,6",  "78,5"),
    ("1,20", "43,75",   "9,4",   "0,22", "30,0", "20,6", "10,2",  "3,8",  "1,3",  "1,6",  "65,4"),
    ("1,40", "43,55",  "15,4",   "0,25", "30,0", "23,5", "12,0",  "5,7",  "1,8",  "2,3",  "91,8"),
    ("1,60", "43,35",  "19,6",   "0,29", "30,0", "24,3", "12,6",  "6,5",  "2,2",  "2,7", "101,8"),
    ("1,80", "43,15",  "21,6",   "0,32", "30,0", "24,2", "12,5",  "6,3",  "2,4",  "2,9",  "99,8"),
    ("2,00", "42,95",  "16,6",   "0,36", "30,0", "21,1", "10,4",  "4,0",  "2,1",  "2,4",  "69,0"),
    ("2,20", "42,75",  "21,6",   "0,40", "30,0", "22,5", "11,3",  "5,0",  "2,5",  "2,9",  "81,6"),
    ("2,40", "42,55",  "23,6",   "0,43", "30,0", "22,5", "11,3",  "5,0",  "2,7",  "3,1",  "81,8"),
    ("2,60", "42,35",  "31,7",   "0,47", "30,0", "24,3", "12,6",  "6,5",  "3,3",  "3,8", "101,6"),
    ("2,80", "42,15",  "41,7",   "0,50", "30,0", "25,9", "13,9",  "8,1",  "3,9",  "4,6", "124,1"),
    ("3,00", "41,95",  "47,7",   "0,54", "30,0", "26,4", "14,4",  "8,8",  "4,4",  "5,1", "132,5"),
    ("3,20", "41,75",  "33,7",   "0,58", "30,0", "23,1", "11,7",  "5,4",  "3,7",  "4,1",  "87,7"),
    ("3,40", "41,55",  "35,7",   "0,61", "30,0", "23,1", "11,7",  "5,4",  "3,9",  "4,3",  "87,5"),
    ("3,60", "41,35",  "41,8",   "0,65", "30,0", "23,9", "12,3",  "6,1",  "4,3",  "4,8",  "96,8"),
    ("3,80", "41,15",  "39,8",   "0,68", "30,0", "23,1", "11,7",  "5,4",  "4,3",  "4,7",  "87,3"),
    ("4,00", "40,95",  "41,8",   "0,72", "30,0", "23,1", "11,7",  "5,4",  "4,5",  "4,9",  "87,1"),
    ("4,20", "40,75",  "45,8",   "0,76", "30,0", "23,4", "12,0",  "5,7",  "4,8",  "5,3",  "90,9"),
    ("4,40", "40,55",  "43,8",   "0,79", "30,0", "22,7", "11,4",  "5,1",  "4,8",  "5,2",  "83,0"),
    ("4,60", "40,35",  "46,0",   "0,83", "30,0", "22,7", "11,4",  "5,1",  "5,0",  "5,4",  "83,3"),
    ("4,80", "40,15",  "44,0",   "0,86", "30,0", "22,0", "11,0",  "4,6",  "5,0",  "5,4",  "76,3"),
    ("5,00", "39,95",  "44,0",   "0,90", "30,0", "21,6", "10,8",  "4,4",  "5,1",  "5,4",  "73,3"),
    ("5,20", "39,75",  "48,0",   "0,94", "30,0", "22,0", "11,0",  "4,6",  "5,4",  "5,8",  "76,9"),
    ("5,40", "39,55", "100,0",   "0,97", "30,0", "27,5", "15,5", "10,4",  "8,1",  "8,9", "154,3"),
    ("5,60", "39,35", "121,1",   "1,01", "30,0", "28,6", "16,7", "12,3",  "9,1", "10,1", "180,2"),
    ("5,80", "39,15", "221,1",   "1,04", "31,9", "31,9", "23,0", "20,6", "13,1", "14,8", "317,7"),
    ("6,00", "38,95", "281,1",   "1,08", "33,0", "33,0", "26,1", "24,3", "15,4", "17,4", "390,4"),
    ("6,20", "38,75", "321,1",   "1,12", "33,5", "33,5", "27,7", "26,4", "16,9", "19,0", "431,6"),
    ("6,40", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("6,60", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("6,80", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("7,00", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("7,20", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("7,40", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("7,60", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("7,80", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("8,00", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("8,20", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("8,40", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("8,60", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("8,80", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("9,00", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("9,20", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("9,40", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("9,60", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("9,80", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
    ("10,00", "38,55", "341,1",   "1,15", "33,6", "33,6", "28,2", "27,0", "17,7", "19,9", "444,1"),
]
# fmt: on


# ---------------------------------------------------------------------------
# LAYOUT
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = A4

LEFT_MARGIN = 15 * mm
RIGHT_MARGIN = 15 * mm
TOP_MARGIN = 14 * mm
BOTTOM_MARGIN = 10 * mm
TABLE_WIDTH = PAGE_W - LEFT_MARGIN - RIGHT_MARGIN

LOGO_LEFT = LEFT_MARGIN
LABELS_LEFT = LEFT_MARGIN + LOGO_WIDTH + 10

META_BLOCK_WIDTH = 120
META_X_LABEL = LEFT_MARGIN + TABLE_WIDTH - META_BLOCK_WIDTH
META_X_VALUE = LEFT_MARGIN + TABLE_WIDTH - 8

COL_RATIOS = [1.0, 1.0, 1.2, 1.2, 0.8, 0.8, 0.8, 0.8, 1.1, 1.1, 1.1]
_total_ratio = sum(COL_RATIOS)
COL_WIDTHS = [r / _total_ratio * TABLE_WIDTH for r in COL_RATIOS]

ROW_HEIGHT = 12.25
HEADER_ROW_HEIGHT = 17
UNIT_ROW_HEIGHT = 16

FONT_SIZE_COL_HEADER = 11
FONT_SIZE_COL_UNIT = 11
FONT_SIZE_DATA = 10
FONT_SIZE_TITLE = 16
FONT_SIZE_SUBTITLE = 11
FONT_SIZE_TEST_TYPE = 10
FONT_SIZE_SMALL = 7
FONT_SIZE_META = 8
FONT_SIZE_FOOTER = 10

FOOTER_BOX_HEIGHT = 40


def col_x(col_index):
    return LEFT_MARGIN + sum(COL_WIDTHS[:col_index])


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------
def draw_header(c, top_y):
    y = top_y

    c.setFont(FONT_BOLD, FONT_SIZE_TITLE)
    c.drawString(LABELS_LEFT, y, HEADER_INFO["location"])
    y -= 14

    c.setFont(FONT_BOLD, FONT_SIZE_SUBTITLE)
    c.drawString(LABELS_LEFT, y, HEADER_INFO["street"])
    y -= 18

    c.setFont(FONT_BOLD, FONT_SIZE_TEST_TYPE)
    c.drawString(LABELS_LEFT, y, HEADER_INFO["test_type"])
    type_w = pdfmetrics.stringWidth(HEADER_INFO["test_type"], FONT_BOLD, FONT_SIZE_TEST_TYPE)
    c.setFont(FONT_BOLD, 13)
    c.drawString(LABELS_LEFT + type_w + 15, y, HEADER_INFO["test_id"])
    y -= 13

    c.setFont(FONT_NORMAL, FONT_SIZE_SMALL)
    c.drawString(LABELS_LEFT, y, HEADER_INFO["company_line1"])
    y -= 8
    c.drawString(LABELS_LEFT, y, HEADER_INFO["company_line2"])
    y -= 8

    # --- Logo centré verticalement sur les 3 lignes principales ---
    # On exclut les 2 lignes société (7pt) qui tiraient le centre vers le bas
    text_visual_top    = top_y + FONT_SIZE_TITLE * 0.75        # ≈ top_y + 12
    text_visual_bottom = top_y - 17 - 18 - FONT_SIZE_TEST_TYPE * 0.25  # ≈ top_y - 37
    text_center_y      = (text_visual_top + text_visual_bottom) / 2     # ≈ top_y - 12.5

    if LOGO_PATH and os.path.exists(LOGO_PATH):
        logo_y = text_center_y - LOGO_HEIGHT / 2 + LOGO_V_OFFSET

        try:
            c.drawImage(LOGO_PATH, LOGO_LEFT, logo_y,
                        width=LOGO_WIDTH, height=LOGO_HEIGHT,
                        preserveAspectRatio=True, anchor='sw', mask='auto')
        except Exception as e:
            print(f"ATTENTION: impossible de charger le logo: {e}")

    meta_y = top_y + 2
    for label, key, dy in [("Dossier:", "dossier", 0),
                           ("Date:", "date", -13),
                           ("Prof. Atteinte:", "prof_atteinte", -18),
                           ("Cote de départ:", "cote_depart", -13)]:
        meta_y += dy
        c.setFont(FONT_NORMAL, FONT_SIZE_META)
        c.drawString(META_X_LABEL, meta_y, label)
        c.setFont(FONT_BOLD, FONT_SIZE_META)
        c.drawRightString(META_X_VALUE, meta_y, HEADER_INFO[key])

    return y


# ---------------------------------------------------------------------------
# TEXTE avec indices / exposants / grec
# ---------------------------------------------------------------------------
def draw_text_with_sub_super(c, x, y, fragments, font_name, font_size,
                             alignment="center", col_width=0, font_bold=None):
    """
    Dessine du texte avec support indices (sub), exposants (super) et gras.
    fragments: liste de (texte, style) avec style parmi:
        'normal', 'bold', 'sub', 'super'
    font_bold: police bold à utiliser (défaut : FONT_BOLD global)
    """
    if font_bold is None:
        font_bold = FONT_BOLD

    # Passe 1 : calcul largeur totale
    total_width = 0
    for text, style in fragments:
        sz = font_size * 0.65 if style in ("sub", "super") else font_size
        fn = font_bold if style == "bold" else font_name
        total_width += pdfmetrics.stringWidth(text, fn, sz)

    # Position de départ selon alignement
    if alignment == "center":
        draw_x = x + col_width / 2 - total_width / 2
    elif alignment == "right":
        draw_x = x + col_width - total_width - 2
    else:
        draw_x = x + 2

    # Passe 2 : dessin
    for text, style in fragments:
        if style in ("sub", "super"):
            sz = font_size * 0.65
            fn = font_name
            dy = -font_size * 0.12 if style == "sub" else font_size * 0.35
            c.setFont(fn, sz)
            c.drawString(draw_x, y + dy, text)
            draw_x += pdfmetrics.stringWidth(text, fn, sz)
        else:
            sz = font_size
            fn = font_bold if style == "bold" else font_name
            c.setFont(fn, sz)
            c.drawString(draw_x, y, text)
            draw_x += pdfmetrics.stringWidth(text, fn, sz)


# ---------------------------------------------------------------------------
# EN-TÊTE TABLEAU
# ---------------------------------------------------------------------------
def draw_table_header(c, y):
    """Titres + unités dans un seul bloc sans trait horizontal interne."""
    n_cols = len(COL_WIDTHS)
    total_h = HEADER_ROW_HEIGHT + UNIT_ROW_HEIGHT
    block_top = y
    block_bottom = y - total_h
    row_sep_y = y - HEADER_ROW_HEIGHT

    # Cadre unique
    c.setStrokeColor(black)
    c.setLineWidth(0.8)
    c.rect(LEFT_MARGIN, block_bottom, TABLE_WIDTH, total_h, stroke=1, fill=0)

    # Séparateurs verticaux
    for i in range(1, n_cols):
        c.line(col_x(i), block_top, col_x(i), block_bottom)

    # --- Titres colonnes ---
    labels = [
        [("Prof", "bold")],
        [("Cote", "bold")],
        [("q", "bold"), ("c", "sub")],
        [("q'", "bold"), ("o", "sub")],
        [(PHI + "'", "bold")],                        # ϕ'
        [(PHI, "bold"), ("u", "sub")],                 # ϕ_u
        [("N", "bold"), ("q", "sub")],
        [("N", "bold"), ("\u03B3", "sub")],            # N_γ
        [("P", "bold"), ("adm,60", "sub")],
        [("P", "bold"), ("adm,150", "sub")],
        [("C", "bold")],
    ]

    # Colonnes dont les titres sont en Arial (indices 4 à 7 : ϕ', ϕ_u, Nq, Nγ)
    ARIAL_COL_INDICES = {4, 5, 6, 7}

    text_y = row_sep_y + (HEADER_ROW_HEIGHT - FONT_SIZE_COL_HEADER) / 2 + 1
    for i, frags in enumerate(labels):
        if i in ARIAL_COL_INDICES:
            draw_text_with_sub_super(c, col_x(i), text_y, frags, FONT_ARIAL,
                                     FONT_SIZE_COL_HEADER, "center", COL_WIDTHS[i],
                                     font_bold=FONT_ARIAL_BOLD)
        else:
            draw_text_with_sub_super(c, col_x(i), text_y, frags, FONT_BOLD,
                                     FONT_SIZE_COL_HEADER, "center", COL_WIDTHS[i])

    # --- Unités ---
    units = [
        [("[m]", "normal")],
        [("[m]", "normal")],
        [("[kg/cm", "normal"), ("2", "super"), ("]", "normal")],
        [("[kg/cm", "normal"), ("2", "super"), ("]", "normal")],
        [("[°]", "normal")],
        [("[°]", "normal")],
        [("[/]", "normal")],
        [("[/]", "normal")],
        [("[kg/cm", "normal"), ("2", "super"), ("]", "normal")],
        [("[kg/cm", "normal"), ("2", "super"), ("]", "normal")],
        [("[/] \u03B1=1,5", "normal")],
    ]

    text_y = block_bottom + (UNIT_ROW_HEIGHT - FONT_SIZE_COL_UNIT) / 2 + 1
    for i, frags in enumerate(units):
        draw_text_with_sub_super(c, col_x(i), text_y, frags, FONT_NORMAL,
                                 FONT_SIZE_COL_UNIT, "center", COL_WIDTHS[i])

    return block_bottom


# ---------------------------------------------------------------------------
# DONNÉES
# ---------------------------------------------------------------------------
def draw_data_rows(c, y_start, data):
    n_rows = len(data)
    n_cols = len(COL_WIDTHS)
    block_height = n_rows * ROW_HEIGHT
    data_top = y_start
    data_bottom = y_start - block_height

    c.setStrokeColor(black)
    c.setLineWidth(0.8)
    c.rect(LEFT_MARGIN, data_bottom, TABLE_WIDTH, block_height, stroke=1, fill=0)

    for i in range(1, n_cols):
        c.line(col_x(i), data_top, col_x(i), data_bottom)

    for row_idx, row in enumerate(data):
        row_y = data_top - (row_idx + 1) * ROW_HEIGHT
        text_y = row_y + (ROW_HEIGHT - FONT_SIZE_DATA) / 2 + 1
        for col_idx, value in enumerate(row):
            c.setFont(FONT_NORMAL, FONT_SIZE_DATA)
            c.drawRightString(col_x(col_idx) + COL_WIDTHS[col_idx] - 3, text_y, value)

    return data_bottom


# ---------------------------------------------------------------------------
# PIED DE PAGE
# ---------------------------------------------------------------------------
def draw_footer_line_with_m3(c, x, y, prefix, font_name, font_size):
    """Dessine une ligne contenant [kg/m³] avec exposant manuel."""
    c.setFont(font_name, font_size)
    c.drawString(x, y, prefix)
    w = pdfmetrics.stringWidth(prefix, font_name, font_size)
    c.drawString(x + w, y, "[kg/m")
    w += pdfmetrics.stringWidth("[kg/m", font_name, font_size)
    small_sz = font_size * 0.65
    c.setFont(font_name, small_sz)
    c.drawString(x + w, y + font_size * 0.35, "3")
    w += pdfmetrics.stringWidth("3", font_name, small_sz)
    c.setFont(font_name, font_size)
    c.drawString(x + w, y, "]")


def draw_footer_box(c, y):
    c.setStrokeColor(black)
    c.setLineWidth(0.8)
    c.rect(LEFT_MARGIN, y, TABLE_WIDTH, FOOTER_BOX_HEIGHT, stroke=1, fill=0)

    line_y = y + FOOTER_BOX_HEIGHT - 13
    draw_footer_line_with_m3(c, LEFT_MARGIN + 5, line_y,
                             "Masse volumique du sol saturé: 2000 ",
                             FONT_NORMAL, FONT_SIZE_FOOTER)

    line_y -= 12
    draw_footer_line_with_m3(c, LEFT_MARGIN + 5, line_y,
                             "Masse volumique du sol: 1800 ",
                             FONT_NORMAL, FONT_SIZE_FOOTER)

    line_y -= 12
    frags = [
        ("P", "bold"),
        ("adm,B", "sub"),
        (" = pression admissible sous une semelle de B cm de largeur "
         "(avec un coefficient de sécurité égal à 2)", "normal"),
    ]
    draw_text_with_sub_super(c, LEFT_MARGIN + 5, line_y, frags, FONT_NORMAL,
                             FONT_SIZE_FOOTER, "left", TABLE_WIDTH)


# ---------------------------------------------------------------------------
# GÉNÉRATION
# ---------------------------------------------------------------------------
def generate_report(output_path):
    c = canvas.Canvas(output_path, pagesize=A4)
    c.setTitle("CPT Report - Sondage au Pénétromètre Statique")

    top_y = PAGE_H - TOP_MARGIN
    header_end_y = draw_header(c, top_y)

    table_start_y = header_end_y - 8
    header_end = draw_table_header(c, table_start_y)
    draw_data_rows(c, header_end, DATA_ROWS)

    draw_footer_box(c, BOTTOM_MARGIN)

    c.save()
    print(f"PDF généré : {output_path}")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output = os.path.join(script_dir, "CPT_REPORT.pdf")
    generate_report(output)
