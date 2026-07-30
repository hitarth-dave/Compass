"""One-page birth-chart card, rendered as a VECTOR PDF.

Replaces the old raster PNG share card, which had two quality problems:
  1. It was a 1080x1350 bitmap — roughly 90 DPI on A4, so it blurred badly
     when printed or zoomed.
  2. It looked for PT_Serif TTFs under backend/assets/fonts/, which were
     never committed to the repo, so every text draw silently fell back to
     PIL's ~11px default bitmap font. That is why every label on the old
     card rendered tiny regardless of the size passed in.

This module uses ReportLab's built-in Type 1 fonts (Times/Helvetica), which
are vector, always present, and need no font files on disk — so the
missing-font failure mode cannot come back.

The card is designed to work for two audiences at once: attractive enough
to show someone as a personal "who I am" card, and complete enough that an
astrologer can actually read the chart from it without asking follow-ups.
"""

from io import BytesIO
from typing import Dict, List, Optional

from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas

# --- Brand palette (matches the app's CSS variables) ---
BG = Color(247 / 255, 241 / 255, 225 / 255)
INK = Color(15 / 255, 61 / 255, 46 / 255)
GOLD = Color(122 / 255, 90 / 255, 7 / 255)
MUTED = Color(92 / 255, 106 / 255, 90 / 255)
HAIRLINE = Color(15 / 255, 61 / 255, 46 / 255, alpha=0.22)
PANEL = Color(1, 1, 1, alpha=0.42)

SERIF = "Times-Roman"
SERIF_BOLD = "Times-Bold"
SERIF_ITALIC = "Times-Italic"
SANS = "Helvetica"
SANS_BOLD = "Helvetica-Bold"

PAGE_W, PAGE_H = A4
MARGIN = 34

# Text anchor points for each house in a North Indian (diamond) chart,
# expressed as fractions of the square's side with the origin at the
# TOP-LEFT and y increasing downward. House 1 is the upper-centre triangle
# and the houses run anticlockwise from there, which is the standard
# North Indian arrangement.
NORTH_INDIAN_HOUSE_ANCHORS = {
    1: (0.50, 0.19),
    2: (0.25, 0.09),
    3: (0.09, 0.25),
    4: (0.28, 0.50),
    5: (0.09, 0.75),
    6: (0.25, 0.91),
    7: (0.50, 0.81),
    8: (0.75, 0.91),
    9: (0.91, 0.75),
    10: (0.72, 0.50),
    11: (0.91, 0.25),
    12: (0.75, 0.09),
}

SIGN_ABBR = [
    "Ar", "Ta", "Ge", "Cn", "Le", "Vi",
    "Li", "Sc", "Sg", "Cp", "Aq", "Pi",
]


def _text_center(c, x, y, text, font, size, color):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawCentredString(x, y, text)


def _text_left(c, x, y, text, font, size, color):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawString(x, y, text)


def _letterspaced(text: str, spacing: str = " ") -> str:
    return spacing.join(list(text))


def _wrap_text(c, text: str, font: str, size: float, max_width: float) -> List[str]:
    """Word-wraps text to fit max_width, measured with the actual font
    metrics rather than a guessed character count — replaces the old blunt
    text[:118] truncation, which could cut a sentence off mid-word."""
    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = current + " " + word
        if c.stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_north_indian_chart(c, x, y, size, title, asc_sign_idx, planets, subtitle=""):
    """Draws one North Indian diamond chart with its outer square, both
    diagonals and the inner diamond, then places the sign number and the
    planets sitting in each house. (x, y) is the BOTTOM-LEFT corner in
    ReportLab's y-up coordinate space."""
    top = y + size

    def px(fx, fy):
        """Fractional top-left-origin coords -> absolute ReportLab coords."""
        return x + fx * size, top - fy * size

    _text_center(c, x + size / 2, top + 20, title, SANS_BOLD, 8, GOLD)
    if subtitle:
        _text_center(c, x + size / 2, top + 9, subtitle, SANS, 6.5, MUTED)

    c.setFillColor(PANEL)
    c.rect(x, y, size, size, stroke=0, fill=1)

    c.setStrokeColor(INK)
    c.setLineWidth(1.1)
    c.rect(x, y, size, size, stroke=1, fill=0)

    c.setStrokeColor(HAIRLINE)
    c.setLineWidth(0.7)
    # Both diagonals
    c.line(x, y, x + size, top)
    c.line(x, top, x + size, y)
    # Inner diamond through the side midpoints
    mid_t, mid_r = (x + size / 2, top), (x + size, y + size / 2)
    mid_b, mid_l = (x + size / 2, y), (x, y + size / 2)
    c.line(*mid_t, *mid_r)
    c.line(*mid_r, *mid_b)
    c.line(*mid_b, *mid_l)
    c.line(*mid_l, *mid_t)

    by_house: Dict[int, List[Dict]] = {}
    for p in planets:
        by_house.setdefault(p.get("house", 0), []).append(p)

    for house in range(1, 13):
        fx, fy = NORTH_INDIAN_HOUSE_ANCHORS[house]
        cx, cy = px(fx, fy)
        sign_idx = (asc_sign_idx + house - 1) % 12

        _text_center(c, cx, cy + 5, f"{SIGN_ABBR[sign_idx]} {sign_idx + 1}", SANS_BOLD, 5.6, GOLD)

        occupants = by_house.get(house, [])
        if not occupants:
            continue
        # Two per line keeps busy houses from overflowing their triangle.
        # Retrograde uses a plain ASCII "R" — the previous superscript-R
        # character (U+1D3F) isn't in the base PDF font's encoding, so it
        # silently rendered as a missing-glyph box instead of a letter.
        rows: List[str] = []
        for i in range(0, len(occupants), 2):
            pair = occupants[i:i + 2]
            rows.append(" ".join(
                p["symbol"] + ("R" if p.get("retrograde") else "") for p in pair
            ))
        line_y = cy - 3
        for row in rows:
            _text_center(c, cx, line_y, row, SANS_BOLD, 6.6, INK)
            line_y -= 7.4


def _draw_section_label(c, x, y, label, width=None):
    _text_left(c, x, y, _letterspaced(label.upper()), SANS_BOLD, 6.4, GOLD)
    if width:
        c.setStrokeColor(HAIRLINE)
        c.setLineWidth(0.6)
        c.line(x, y - 4, x + width, y - 4)


def _fmt_deg(deg: float) -> str:
    d = int(deg)
    m = int(round((deg - d) * 60))
    if m == 60:
        d, m = d + 1, 0
    return f"{d}\u00b0{m:02d}'"


def generate_chart_card_pdf(
    name: str,
    birth_line: str,
    chart: Dict,
    navamsa: Dict,
    dasha_line: str,
    about_lines: Optional[List[str]] = None,
) -> bytes:
    """Renders the one-page A4 card and returns PDF bytes."""
    buf = BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"{name} — Compass Astro birth chart")
    c.setAuthor("Compass Astro")

    # Background + frame
    c.setFillColor(BG)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    c.setStrokeColor(INK)
    c.setLineWidth(1.2)
    c.rect(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN, stroke=1, fill=0)

    inner_l = MARGIN + 20
    inner_r = PAGE_W - MARGIN - 20
    inner_w = inner_r - inner_l
    cursor = PAGE_H - MARGIN - 34

    # ---------- Header ----------
    _text_center(c, PAGE_W / 2, cursor, _letterspaced("COMPASS ASTRO"), SANS_BOLD, 7.5, GOLD)
    cursor -= 27
    _text_center(c, PAGE_W / 2, cursor, name[:42], SERIF_BOLD, 25, INK)
    cursor -= 15
    _text_center(c, PAGE_W / 2, cursor, birth_line, SANS, 7.6, MUTED)
    cursor -= 10

    asc = chart["ascendant"]
    planets = chart["planets"]
    by_name = {p["name"]: p for p in planets}
    moon = by_name.get("Moon", {})
    sun = by_name.get("Sun", {})

    headline = (
        f"{asc.get('sign_en', '')} Lagna  \u00b7  "
        f"{moon.get('sign_en', '')} Moon  \u00b7  "
        f"{moon.get('nakshatra', '')} {moon.get('pada', '')}"
    )
    _text_center(c, PAGE_W / 2, cursor, headline, SERIF_ITALIC, 10, GOLD)
    cursor -= 13

    c.setStrokeColor(GOLD)
    c.setLineWidth(0.8)
    c.line(PAGE_W / 2 - 60, cursor, PAGE_W / 2 + 60, cursor)
    cursor -= 20

    # ---------- Charts (D1 + D9) ----------
    chart_size = 196
    gap = inner_w - 2 * chart_size
    chart_y = cursor - chart_size
    _draw_north_indian_chart(
        c, inner_l, chart_y, chart_size,
        "RASI \u00b7 D1", asc["sign_idx"], planets,
        subtitle="the visible life",
    )
    _draw_north_indian_chart(
        c, inner_l + chart_size + gap, chart_y, chart_size,
        "NAVAMSA \u00b7 D9", navamsa["ascendant"]["sign_idx"], navamsa["planets"],
        subtitle="the inner strength",
    )
    cursor = chart_y - 22

    # ---------- Current period ----------
    _draw_section_label(c, inner_l, cursor, "Current period", inner_w)
    cursor -= 15
    _text_left(c, inner_l, cursor, dasha_line, SERIF, 9, INK)
    cursor -= 20

    # ---------- Planetary positions ----------
    _draw_section_label(c, inner_l, cursor, "Planetary positions", inner_w)
    cursor -= 14

    col = [inner_l, inner_l + 62, inner_l + 128, inner_l + 168, inner_l + 208, inner_l + 310]
    headers = ["PLANET", "SIGN", "DEG", "HOUSE", "NAKSHATRA", "DIGNITY"]
    for cx_, h in zip(col, headers):
        _text_left(c, cx_, cursor, h, SANS_BOLD, 5.8, MUTED)
    cursor -= 3
    c.setStrokeColor(HAIRLINE)
    c.setLineWidth(0.5)
    c.line(inner_l, cursor, inner_r, cursor)
    cursor -= 10

    nature = chart.get("planet_nature", {})
    for p in planets:
        pname = p["name"] + (" (R)" if p.get("retrograde") else "")
        tags = list(p.get("dignity") or [])
        func = (nature.get(p["name"]) or {}).get("functional")
        if func:
            tags.append(func.capitalize())
        dignity_txt = ", ".join(tags) if tags else "\u2014"

        _text_left(c, col[0], cursor, pname, SANS_BOLD, 7.4, INK)
        _text_left(c, col[1], cursor, p.get("sign_en", ""), SANS, 7.4, INK)
        _text_left(c, col[2], cursor, _fmt_deg(p.get("degree_in_sign", 0)), SANS, 7.4, MUTED)
        _text_left(c, col[3], cursor, str(p.get("house", "")), SANS, 7.4, INK)
        _text_left(c, col[4], cursor, f"{p.get('nakshatra', '')} {p.get('pada', '')}", SANS, 7.4, MUTED)
        _text_left(c, col[5], cursor, dignity_txt[:34], SANS, 7.4, GOLD if tags else MUTED)
        cursor -= 10.6

    cursor -= 8

    # ---------- Strengths | Yogas (two columns) ----------
    col_w = (inner_w - 22) / 2
    right_l = inner_l + col_w + 22
    top_of_block = cursor

    _draw_section_label(c, inner_l, cursor, "Planetary strength", col_w)
    cursor -= 14

    shadbala = chart.get("shadbala") or {}
    ranked = sorted(
        ((k, v.get("total_rupas", 0)) for k, v in shadbala.items()),
        key=lambda kv: kv[1], reverse=True,
    )
    if ranked:
        _text_left(c, inner_l, cursor, "Strongest", SANS_BOLD, 6.6, MUTED)
        cursor -= 10
        for pname, rupas in ranked[:3]:
            _text_left(c, inner_l, cursor, f"{pname}", SANS_BOLD, 7.6, INK)
            _text_left(c, inner_l + 74, cursor, f"{rupas:.2f} rupas", SANS, 7.4, GOLD)
            cursor -= 10
        cursor -= 3
        _text_left(c, inner_l, cursor, "Weakest", SANS_BOLD, 6.6, MUTED)
        cursor -= 10
        for pname, rupas in ranked[-2:]:
            _text_left(c, inner_l, cursor, f"{pname}", SANS_BOLD, 7.6, INK)
            _text_left(c, inner_l + 74, cursor, f"{rupas:.2f} rupas", SANS, 7.4, MUTED)
            cursor -= 10
    else:
        _text_left(c, inner_l, cursor, "\u2014", SANS, 7.4, MUTED)
        cursor -= 10
    left_bottom = cursor

    # Right column — yogas
    cursor = top_of_block
    yogas = chart.get("yogas") or []
    _draw_section_label(c, right_l, cursor, f"Yogas detected ({len(yogas)})", col_w)
    cursor -= 14
    if yogas:
        for yg in yogas[:5]:
            _text_left(c, right_l, cursor, yg.get("name", "")[:46], SANS_BOLD, 7.4, INK)
            cursor -= 9
            detail = (yg.get("detail") or "")
            for line in _wrap_text(c, detail, SANS, 6.4, col_w)[:2]:
                _text_left(c, right_l, cursor, line, SANS, 6.4, MUTED)
                cursor -= 8
            cursor -= 3
    else:
        _text_left(c, right_l, cursor, "No major yogas in the detected set.", SANS, 7.4, MUTED)
        cursor -= 10

    cursor = min(left_bottom, cursor) - 4

    # ---------- Ashtakavarga ----------
    sav = (chart.get("ashtakavarga") or {}).get("sav") or []
    if sav:
        total = sum(sav)
        _draw_section_label(c, inner_l, cursor, f"Ashtakavarga \u00b7 SAV by house (total {total})", inner_w)
        cursor -= 24
        cell_w = inner_w / 12
        asc_sign = asc["sign_idx"]
        best = max(sav) if sav else 0
        worst = min(sav) if sav else 0
        for h in range(12):
            sign_idx = (asc_sign + h) % 12
            bindus = sav[sign_idx]
            cx_ = inner_l + h * cell_w + cell_w / 2
            _text_center(c, cx_, cursor + 9, f"H{h + 1}", SANS, 5.6, MUTED)
            emphasis = GOLD if bindus == best else (MUTED if bindus == worst else INK)
            font = SANS_BOLD if bindus in (best, worst) else SANS
            _text_center(c, cx_, cursor, str(bindus), font, 8.4, emphasis)
        cursor -= 8
        c.setStrokeColor(HAIRLINE)
        c.setLineWidth(0.5)
        c.line(inner_l, cursor, inner_r, cursor)
        cursor -= 8

    # ---------- About ----------
    # Bigger type, word-wrapped (not blunt character-truncated — the old
    # version could cut a line off mid-word), and capped by how much room
    # is actually left above the footer so this can never overlap it
    # regardless of how much text the model returns.
    if about_lines:
        _draw_section_label(c, inner_l, cursor, "What the classics say about this chart", inner_w)
        cursor -= 16
        about_font_size = 9.4
        line_height = 13.5
        footer_safe_top = MARGIN + 22 + 20  # foot_y + clearance above the rule
        wrapped: List[str] = []
        for line in about_lines:
            wrapped.extend(_wrap_text(c, line, SERIF, about_font_size, inner_w))
        max_lines = max(1, int((cursor - footer_safe_top) / line_height))
        for line in wrapped[:max_lines]:
            _text_left(c, inner_l, cursor, line, SERIF, about_font_size, INK)
            cursor -= line_height

    # ---------- Footer ----------
    foot_y = MARGIN + 22
    c.setStrokeColor(HAIRLINE)
    c.setLineWidth(0.5)
    c.line(inner_l, foot_y + 18, inner_r, foot_y + 18)
    _text_left(c, inner_l, foot_y + 7, "Sidereal \u00b7 Lahiri ayanamsa \u00b7 Swiss Ephemeris \u00b7 North Indian style", SANS, 6.2, MUTED)
    c.setFont(SANS_BOLD, 6.6)
    c.setFillColor(GOLD)
    c.drawRightString(inner_r, foot_y + 7, "compass-vert-one.vercel.app")

    c.showPage()
    c.save()
    return buf.getvalue()


# Rendering DPI for the PNG. A4 at 200 DPI is 1654x2339 px — large enough to
# stay sharp when zoomed on a phone or printed at normal size, small enough
# (~400 KB) to send over WhatsApp without being recompressed into mush.
PNG_DPI = 200


def generate_chart_card_png(*args, **kwargs) -> bytes:
    """Same card, delivered as a PNG so it saves to the camera roll and
    shares like a normal photo.

    The layout is still drawn as vector first and only rasterized at the
    final step — that's what keeps the text crisp. Rendering straight to a
    bitmap (the old approach) is what made the previous card blurry.

    Rasterizing via pypdfium2 rather than a system tool like poppler is
    deliberate: it ships as a self-contained manylinux wheel, so there's no
    apt package to install on Render and no way for the renderer to go
    missing on a fresh deploy — the same class of failure as the absent
    font files that broke the original card.
    """
    import pypdfium2 as pdfium

    pdf_bytes = generate_chart_card_pdf(*args, **kwargs)
    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        bitmap = doc[0].render(scale=PNG_DPI / 72)
        img = bitmap.to_pil().convert("RGB")
        out = BytesIO()
        img.save(out, format="PNG", optimize=True)
        return out.getvalue()
    finally:
        doc.close()
