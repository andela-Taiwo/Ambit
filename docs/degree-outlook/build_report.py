#!/usr/bin/env python3
"""Build the English & International Relations career outlook report."""

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
OUT = HERE / "English-and-International-Relations-Outlook-2026.docx"
CHART = HERE / "pay_ranges.png"

NAVY = "0E2438"
TEAL = "1F6F78"
GOLD = "B07C33"
INK = "1A1A1A"
GRAY = "5F6B73"
MUTED = "8A969D"
LIGHT = "F2F5F7"
PALE = "E7F0F0"
RULE = "D8E0E5"
WHITE = "FFFFFF"

BODY_FONT = "Georgia"
HEAD_FONT = "Arial"
USABLE_CM = 16.6


def c(hex_str):
    return RGBColor.from_string(hex_str)


# --------------------------------------------------------------------------
# low-level helpers
# --------------------------------------------------------------------------
def _shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def _margins(cell, top=90, bottom=90, left=120, right=120):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for tag, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        node = OxmlElement(f"w:{tag}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        mar.append(node)
    tcPr.append(mar)


def _borders(cell, **edges):
    """edges: top=dict(sz=8, color='D8E0E5', val='single')"""
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge, spec in edges.items():
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), spec.get("val", "single"))
        el.set(qn("w:sz"), str(spec.get("sz", 8)))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), spec.get("color", RULE))
        borders.append(el)
    tcPr.append(borders)


def _table_borders(table, color=RULE, sz=6):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        borders.append(el)
    tblPr.append(borders)


def _no_borders(table):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tblPr.append(borders)


def _fixed_layout(table, widths_cm):
    tblPr = table._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    total = sum(widths_cm)
    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:w"), str(int(total / 2.54 * 1440)))
    tblW.set(qn("w:type"), "dxa")
    tblPr.append(tblW)
    grid = table._tbl.tblGrid
    for col, width in zip(grid.findall(qn("w:gridCol")), widths_cm):
        col.set(qn("w:w"), str(int(width / 2.54 * 1440)))
    for row in table.rows:
        for idx, width in enumerate(widths_cm):
            row.cells[idx].width = Cm(width)


# OOXML schema order for property containers. Word will repair or silently drop
# children it finds out of order, so we re-sort every container once at the end.
_ORDERS = {
    "w:pPr": [
        "w:pStyle", "w:keepNext", "w:keepLines", "w:pageBreakBefore", "w:framePr",
        "w:widowControl", "w:numPr", "w:suppressLineNumbers", "w:pBdr", "w:shd",
        "w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap",
        "w:overflowPunct", "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN",
        "w:bidi", "w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind",
        "w:contextualSpacing", "w:mirrorIndents", "w:suppressOverlap", "w:jc",
        "w:textDirection", "w:textAlignment", "w:textboxTightWrap",
        "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange",
    ],
    "w:rPr": [
        "w:rStyle", "w:rFonts", "w:b", "w:bCs", "w:i", "w:iCs", "w:caps",
        "w:smallCaps", "w:strike", "w:dstrike", "w:outline", "w:shadow",
        "w:emboss", "w:imprint", "w:noProof", "w:snapToGrid", "w:vanish",
        "w:webHidden", "w:color", "w:spacing", "w:w", "w:kern", "w:position",
        "w:sz", "w:szCs", "w:highlight", "w:u", "w:effect", "w:bdr", "w:shd",
        "w:fitText", "w:vertAlign", "w:rtl", "w:cs", "w:em", "w:lang",
        "w:eastAsianLayout", "w:specVanish", "w:oMath",
    ],
    "w:tcPr": [
        "w:cnfStyle", "w:tcW", "w:gridSpan", "w:hMerge", "w:vMerge",
        "w:tcBorders", "w:shd", "w:noWrap", "w:tcMar", "w:textDirection",
        "w:tcFitText", "w:vAlign", "w:hideMark", "w:headers", "w:cellIns",
        "w:cellDel", "w:cellMerge", "w:tcPrChange",
    ],
    "w:tblPr": [
        "w:tblStyle", "w:tblpPr", "w:tblOverlap", "w:bidiVisual",
        "w:tblStyleRowBandSize", "w:tblStyleColBandSize", "w:tblW", "w:jc",
        "w:tblCellSpacing", "w:tblInd", "w:tblBorders", "w:shd", "w:tblLayout",
        "w:tblCellMar", "w:tblLook", "w:tblCaption", "w:tblDescription",
        "w:tblPrChange",
    ],
    "w:trPr": [
        "w:cnfStyle", "w:divId", "w:gridBefore", "w:gridAfter", "w:wBefore",
        "w:wAfter", "w:cantSplit", "w:trHeight", "w:tblHeader",
        "w:tblCellSpacing", "w:jc", "w:hidden", "w:ins", "w:del", "w:trPrChange",
    ],
}


def _normalize(root):
    for tag, order in _ORDERS.items():
        ranked = [qn(item) for item in order]
        for container in root.iter(qn(tag)):
            children = list(container)
            children.sort(key=lambda el: ranked.index(el.tag) if el.tag in ranked else len(ranked))
            for child in children:
                container.remove(child)
                container.append(child)


def spacer(doc, height_cm):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = Cm(height_cm)
    run = paragraph.add_run(" ")
    run.font.size = Pt(1)
    return paragraph


def _row_props(row, header=False):
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))
    if header:
        trPr.append(OxmlElement("w:tblHeader"))


def _keep_next(paragraph):
    paragraph.paragraph_format.keep_with_next = True


def _space(run, twips=24):
    rPr = run._r.get_or_add_rPr()
    el = OxmlElement("w:spacing")
    el.set(qn("w:val"), str(twips))
    rPr.append(el)


def _rule_below(paragraph, color=RULE, sz=6, space=6):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(sz))
    bottom.set(qn("w:space"), str(space))
    bottom.set(qn("w:color"), color)
    pBdr.append(bottom)
    pPr.append(pBdr)


def _field(paragraph, instr, size=7.5, color=GRAY, bold=False):
    run = paragraph.add_run()
    run.font.size = Pt(size)
    run.font.color.rgb = c(color)
    run.font.name = HEAD_FONT
    run.bold = bold
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr_el = OxmlElement("w:instrText")
    instr_el.set(qn("xml:space"), "preserve")
    instr_el.text = instr
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr_el)
    run._r.append(fld_sep)
    run._r.append(fld_end)


# --------------------------------------------------------------------------
# text helpers
# --------------------------------------------------------------------------
def _add_runs(paragraph, text, size, color=INK, font=BODY_FONT, italic=False, bold=False):
    """Supports **bold** segments."""
    parts = text.split("**")
    for i, part in enumerate(parts):
        if not part:
            continue
        run = paragraph.add_run(part)
        run.font.name = font
        run.font.size = Pt(size)
        run.font.color.rgb = c(color)
        run.italic = italic
        run.bold = bold or (i % 2 == 1)
    return paragraph


def add_hyperlink(paragraph, url, text, size=7.6, color=TEAL):
    r_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    run = paragraph.add_run(text)
    run.font.name = HEAD_FONT
    run.font.size = Pt(size)
    run.font.color.rgb = c(color)
    element = run._r
    parent = element.getparent()
    parent.remove(element)
    hyperlink.append(element)
    parent.append(hyperlink)
    return hyperlink


def body(doc, text, size=10.5, space_after=7, color=INK, italic=False, spacing=1.14):
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(space_after)
    fmt.line_spacing = spacing
    fmt.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    _add_runs(paragraph, text, size, color=color, italic=italic)
    return paragraph


def lead(doc, text):
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(2)
    fmt.space_after = Pt(10)
    fmt.line_spacing = 1.2
    fmt.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _add_runs(paragraph, text, 12)
    return paragraph


def h1(doc, number, title, new_page=False):
    paragraph = doc.add_paragraph(style="Heading 1")
    fmt = paragraph.paragraph_format
    if new_page:
        fmt.page_break_before = True
        fmt.space_before = Pt(0)
    else:
        fmt.space_before = Pt(20)
    fmt.space_after = Pt(8)
    fmt.keep_with_next = True
    run = paragraph.add_run(f"{number}")
    run.font.name = HEAD_FONT
    run.font.size = Pt(9)
    run.font.bold = True
    run.font.color.rgb = c(GOLD)
    _space(run, 40)
    run2 = paragraph.add_run(f"   {title}")
    run2.font.name = HEAD_FONT
    run2.font.size = Pt(17)
    run2.font.bold = True
    run2.font.color.rgb = c(NAVY)
    _rule_below(paragraph, color=NAVY, sz=8, space=6)
    return paragraph


def h2(doc, title):
    paragraph = doc.add_paragraph(style="Heading 2")
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(13)
    fmt.space_after = Pt(4)
    fmt.keep_with_next = True
    run = paragraph.add_run(title)
    run.font.name = HEAD_FONT
    run.font.size = Pt(11.5)
    run.font.bold = True
    run.font.color.rgb = c(TEAL)
    return paragraph


def h3(doc, title):
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(9)
    fmt.space_after = Pt(2)
    fmt.keep_with_next = True
    run = paragraph.add_run(title)
    run.font.name = HEAD_FONT
    run.font.size = Pt(9.5)
    run.font.bold = True
    run.font.color.rgb = c(NAVY)
    _space(run, 12)
    return paragraph


def bullet(doc, text, size=10.3, space_after=4, indent=0.55):
    paragraph = doc.add_paragraph(style="List Bullet")
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(space_after)
    fmt.line_spacing = 1.1
    fmt.left_indent = Cm(indent)
    fmt.first_line_indent = Cm(-0.4)
    fmt.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _add_runs(paragraph, text, size)
    return paragraph


def numbered(doc, number, text, size=10.3):
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(6)
    fmt.line_spacing = 1.12
    fmt.left_indent = Cm(1.0)
    fmt.first_line_indent = Cm(-1.0)
    fmt.tab_stops.add_tab_stop(Cm(1.0), WD_TAB_ALIGNMENT.LEFT)
    fmt.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = paragraph.add_run(f"{number:02d}")
    run.font.name = HEAD_FONT
    run.font.size = Pt(9)
    run.font.bold = True
    run.font.color.rgb = c(GOLD)
    tab = paragraph.add_run("\t")
    tab.font.size = Pt(9)
    _add_runs(paragraph, text, size)
    return paragraph


def label_line(doc, label, text, label_color=GOLD):
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(3)
    fmt.space_after = Pt(6)
    fmt.line_spacing = 1.1
    fmt.left_indent = Cm(0.0)
    run = paragraph.add_run(label.upper())
    run.font.name = HEAD_FONT
    run.font.size = Pt(7.5)
    run.font.bold = True
    run.font.color.rgb = c(label_color)
    _space(run, 30)
    run2 = paragraph.add_run("   ")
    run2.font.size = Pt(8)
    _add_runs(paragraph, text, 9.5, color=GRAY)
    return paragraph


def callout(doc, label, text, fill=PALE, accent=TEAL, size=10.2):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _no_borders(table)
    _fixed_layout(table, [USABLE_CM])
    cell = table.cell(0, 0)
    _shade(cell, fill)
    _margins(cell, top=170, bottom=170, left=240, right=240)
    _borders(cell, left={"sz": 24, "color": accent}, top={"val": "nil"}, bottom={"val": "nil"}, right={"val": "nil"})
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(3)
    run = paragraph.add_run(label.upper())
    run.font.name = HEAD_FONT
    run.font.size = Pt(7.5)
    run.font.bold = True
    run.font.color.rgb = c(accent)
    _space(run, 36)
    inner = cell.add_paragraph()
    inner.paragraph_format.space_before = Pt(0)
    inner.paragraph_format.space_after = Pt(0)
    inner.paragraph_format.line_spacing = 1.15
    _add_runs(inner, text, size, color=NAVY)

    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.space_after = Pt(0)
    spacer.paragraph_format.line_spacing = 0.6
    return table


def quote(doc, text):
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.left_indent = Cm(0.3)
    fmt.space_before = Pt(10)
    fmt.space_after = Pt(12)
    fmt.line_spacing = 1.25
    _borders_p = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "18")
    left.set(qn("w:space"), "14")
    left.set(qn("w:color"), GOLD)
    _borders_p.append(left)
    paragraph._p.get_or_add_pPr().append(_borders_p)
    _add_runs(paragraph, text, 12.5, color=TEAL, italic=True, font="Georgia")
    return paragraph


def table(doc, headers, rows, widths, font_size=8.4, header_fill=NAVY, zebra=True,
          bold_first=True, align=None, caption=None, caption_above=True):
    if caption and caption_above:
        cap = doc.add_paragraph()
        cap.paragraph_format.space_before = Pt(8)
        cap.paragraph_format.space_after = Pt(3)
        cap.paragraph_format.keep_with_next = True
        label, sep, rest = caption.partition(". ")
        run = cap.add_run(label + (sep or ""))
        run.font.name = HEAD_FONT
        run.font.size = Pt(7.9)
        run.font.bold = True
        run.font.color.rgb = c(NAVY)
        if rest:
            run = cap.add_run(rest)
            run.font.name = HEAD_FONT
            run.font.size = Pt(7.9)
            run.font.color.rgb = c(GRAY)
        _space(run, 16)

    tbl = doc.add_table(rows=1, cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    hdr = tbl.rows[0]
    _row_props(hdr, header=True)
    for i, text in enumerate(headers):
        cell = hdr.cells[i]
        _shade(cell, header_fill)
        _margins(cell, top=100, bottom=100)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.line_spacing = 1.0
        run = paragraph.add_run(text.upper())
        run.font.name = HEAD_FONT
        run.font.size = Pt(font_size - 0.6)
        run.font.bold = True
        run.font.color.rgb = c(WHITE)
        _space(run, 14)

    for r_idx, row_data in enumerate(rows):
        row = tbl.add_row()
        _row_props(row)
        for i, text in enumerate(row_data):
            cell = row.cells[i]
            _margins(cell, top=100, bottom=100)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            if zebra and r_idx % 2 == 1:
                _shade(cell, LIGHT)
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_before = Pt(0)
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.05
            if align and align[i] == "right":
                paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            elif align and align[i] == "center":
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _add_runs(
                paragraph,
                text,
                font_size,
                color=NAVY if (bold_first and i == 0) else INK,
                font=HEAD_FONT,
                bold=(bold_first and i == 0),
            )

    _table_borders(tbl)
    _fixed_layout(tbl, widths)

    if caption and not caption_above:
        note = doc.add_paragraph()
        note.paragraph_format.space_before = Pt(4)
        note.paragraph_format.space_after = Pt(10)
        _add_runs(note, caption, 7.6, color=GRAY, italic=True)

    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.space_after = Pt(4)
    spacer.paragraph_format.line_spacing = 0.5
    return tbl


def figure(doc, path, width_cm, caption):
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(6)
    paragraph.paragraph_format.space_after = Pt(4)
    run = paragraph.add_run()
    run.add_picture(str(path), width=Cm(width_cm))
    docPr = doc.inline_shapes[-1]._inline.docPr
    docPr.set("descr", caption)
    docPr.set("title", "Entry-level monthly pay ranges by pathway")

    note = doc.add_paragraph()
    note.paragraph_format.space_before = Pt(0)
    note.paragraph_format.space_after = Pt(10)
    note.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _add_runs(note, caption, 7.6, color=GRAY, italic=True)


def page_break(doc):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.add_run().add_break(WD_BREAK.PAGE)


# --------------------------------------------------------------------------
# page furniture
# --------------------------------------------------------------------------
def setup(doc):
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(1.9)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    section.header_distance = Cm(0.9)
    section.footer_distance = Cm(0.9)
    section.different_first_page_header_footer = True

    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = c(INK)
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), BODY_FONT)
    rfonts.set(qn("w:hAnsi"), BODY_FONT)
    rfonts.set(qn("w:cs"), BODY_FONT)

    for name, size, color in (("Heading 1", 17, NAVY), ("Heading 2", 11.5, TEAL)):
        style = doc.styles[name]
        style.font.name = HEAD_FONT
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = c(color)
        style.font.italic = False
        srPr = style.element.get_or_add_rPr()
        srFonts = srPr.find(qn("w:rFonts"))
        if srFonts is None:
            srFonts = OxmlElement("w:rFonts")
            srPr.append(srFonts)
        for attr in ("ascii", "hAnsi", "cs", "eastAsia"):
            srFonts.set(qn(f"w:{attr}"), HEAD_FONT)
        for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
            if srFonts.get(qn(f"w:{attr}")) is not None:
                del srFonts.attrib[qn(f"w:{attr}")]

    header = section.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    hp.paragraph_format.space_after = Pt(6)
    run = hp.add_run("ENGLISH & INTERNATIONAL RELATIONS")
    run.font.name = HEAD_FONT
    run.font.size = Pt(7.2)
    run.font.bold = True
    run.font.color.rgb = c(NAVY)
    _space(run, 30)
    run2 = hp.add_run("   ·   CAREER & EARNINGS OUTLOOK 2026")
    run2.font.name = HEAD_FONT
    run2.font.size = Pt(7.2)
    run2.font.color.rgb = c(MUTED)
    _space(run2, 30)
    _rule_below(hp, color=RULE, sz=4, space=4)

    footer = section.footer
    fp = footer.paragraphs[0]
    fp.paragraph_format.tab_stops.add_tab_stop(Cm(USABLE_CM), WD_TAB_ALIGNMENT.RIGHT)
    run = fp.add_run("Prepared November 2026 · Nigeria and Africa")
    run.font.name = HEAD_FONT
    run.font.size = Pt(7.2)
    run.font.color.rgb = c(MUTED)
    fp.add_run("\t")
    run = fp.add_run("Page ")
    run.font.name = HEAD_FONT
    run.font.size = Pt(7.2)
    run.font.color.rgb = c(MUTED)
    _field(fp, "PAGE")


def cover(doc):
    spacer(doc, 2.4)

    kicker = doc.add_paragraph()
    kicker.paragraph_format.space_after = Pt(12)
    run = kicker.add_run("CAREER & EARNINGS OUTLOOK   ·   2026 EDITION")
    run.font.name = HEAD_FONT
    run.font.size = Pt(8.5)
    run.font.bold = True
    run.font.color.rgb = c(GOLD)
    _space(run, 60)

    title = doc.add_paragraph()
    title.paragraph_format.space_after = Pt(0)
    title.paragraph_format.line_spacing = 0.92
    run = title.add_run("English &")
    run.font.name = HEAD_FONT
    run.font.size = Pt(46)
    run.font.bold = True
    run.font.color.rgb = c(NAVY)

    title2 = doc.add_paragraph()
    title2.paragraph_format.space_after = Pt(10)
    title2.paragraph_format.line_spacing = 0.92
    run = title2.add_run("International Relations")
    run.font.name = HEAD_FONT
    run.font.size = Pt(46)
    run.font.bold = True
    run.font.color.rgb = c(NAVY)

    rule = doc.add_paragraph()
    rule.paragraph_format.space_before = Pt(0)
    rule.paragraph_format.space_after = Pt(14)
    rule.paragraph_format.right_indent = Cm(10.6)
    pPr = rule._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "24")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), GOLD)
    pBdr.append(bottom)
    pPr.append(pBdr)
    run = rule.add_run(" ")
    run.font.size = Pt(1)

    sub = doc.add_paragraph()
    sub.paragraph_format.space_after = Pt(0)
    sub.paragraph_format.line_spacing = 1.28
    sub.paragraph_format.right_indent = Cm(2.4)
    run = sub.add_run("What the degree is worth in Nigeria and Africa — and how to make it pay.")
    run.font.name = BODY_FONT
    run.font.size = Pt(15)
    run.font.color.rgb = c(GRAY)

    spacer(doc, 2.0)

    stats = [
        ("33.3%", "Youth unemployment,\nages 15–34"),
        ("41.2%", "Unemployment among\nrecent graduates"),
        ("52.4%", "Share of youth work\nthat is informal"),
    ]
    tbl = doc.add_table(rows=1, cols=3)
    _no_borders(tbl)
    _fixed_layout(tbl, [5.4, 5.4, 5.4])
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    for i, (number, label) in enumerate(stats):
        cell = tbl.cell(0, i)
        _margins(cell, top=0, bottom=0, left=0, right=340)
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.paragraph_format.line_spacing = 1.0
        run = paragraph.add_run(number)
        run.font.name = HEAD_FONT
        run.font.size = Pt(24)
        run.font.bold = True
        run.font.color.rgb = c(TEAL)
        inner = cell.add_paragraph()
        inner.paragraph_format.space_before = Pt(0)
        inner.paragraph_format.space_after = Pt(0)
        inner.paragraph_format.line_spacing = 1.05
        run = inner.add_run(label)
        run.font.name = HEAD_FONT
        run.font.size = Pt(7.8)
        run.font.color.rgb = c(GRAY)

    spacer(doc, 2.6)

    label = doc.add_paragraph()
    label.paragraph_format.space_after = Pt(6)
    run = label.add_run("INSIDE")
    run.font.name = HEAD_FONT
    run.font.size = Pt(7.2)
    run.font.bold = True
    run.font.color.rgb = c(MUTED)
    _space(run, 50)

    contents = [
        ("01", "The short answer"),
        ("02", "The market you are entering"),
        ("03", "What the degree gives you"),
        ("04", "Eight pathways"),
        ("05", "What you can realistically earn"),
        ("06", "The premium stack"),
        ("07", "The money case"),
        ("08", "Risks on the horizon"),
        ("09", "A five-year plan"),
        ("10", "Beyond Nigeria"),
        ("11", "The decision guide"),
        ("12", "Sources and notes"),
    ]
    rows = (len(contents) + 1) // 2
    grid = doc.add_table(rows=rows, cols=2)
    _no_borders(grid)
    _fixed_layout(grid, [8.3, 8.3])
    grid.alignment = WD_TABLE_ALIGNMENT.LEFT
    for idx, (num, title_text) in enumerate(contents):
        cell = grid.cell(idx % rows, idx // rows)
        _margins(cell, top=20, bottom=20, left=0, right=140)
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.paragraph_format.line_spacing = 1.0
        run = paragraph.add_run(f"{num}  ")
        run.font.name = HEAD_FONT
        run.font.size = Pt(7.4)
        run.font.bold = True
        run.font.color.rgb = c(GOLD)
        run = paragraph.add_run(title_text)
        run.font.name = BODY_FONT
        run.font.size = Pt(9)
        run.font.color.rgb = c(GRAY)

    spacer(doc, 1.4)

    meta = doc.add_paragraph()
    meta.paragraph_format.space_before = Pt(0)
    meta.paragraph_format.space_after = Pt(0)
    _add_runs(
        meta,
        "Prepared November 2026  ·  Nigeria focus, with regional and global routes  ·  Evidence notes at the end",
        8.0,
        color=MUTED,
        font=HEAD_FONT,
    )


# --------------------------------------------------------------------------
# content
# --------------------------------------------------------------------------
def section_one(doc):
    h1(doc, "01", "The short answer", new_page=True)
    lead(
        doc,
        "English and International Relations is a generalist degree in a labour market that hires "
        "specialists first. That is the whole story of its earnings: the certificate gets you into the "
        "queue, and what you attach to it decides where in the queue you stand.",
    )
    body(
        doc,
        "Graduates of this combination end up in diplomacy, development, communications, teaching, "
        "banking, energy and technology. They rarely get there because of the degree alone, and almost "
        "never at the same price. The data is blunt: youth unemployment among 15–34-year-olds is 33.3%, "
        "and among people who graduated in the last five years it is 41.2%. Yet a federal graduate entry "
        "post pays ₦123,273 a month before allowances, a national NGO programme officer can earn four "
        "times that, and a Nigerian with three years of experience writing for a US client can earn more "
        "than both. Same degree, same city, ten-fold spread. This report explains where the spread comes "
        "from — and how to get to the top of it.",
    )

    h2(doc, "Five findings")
    numbered(doc, 1, "**Entry is the bottleneck, not the ceiling.** Unemployment falls sharply with experience and with skills that are scarce. The problem is surviving the 12–36 months after NYSC without taking a job that caps your trajectory.")
    numbered(doc, 2, "**The headline rate is not your competition.** The 4.9% national unemployment figure counts anyone who worked for pay for an hour in the reference week. Your competition is the few thousand formal vacancies that open each year, and the people applying for them with referrals.")
    numbered(doc, 3, "**Pay is bimodal, not average.** The same certificate is worth ₦80,000 a month in a private secondary school and ₦600,000 on an energy company's stakeholder team. Averages hide this; ranges do not.")
    numbered(doc, 4, "**The degree's core skill is being repriced.** Fluency and structure are still scarce, but the market now pays for judgement, sourcing and domain knowledge rather than volume of prose — which is exactly what a good English and IR programme teaches, if you let it.")
    numbered(doc, 5, "**The financial case is made by the stack, not the certificate.** Numbers, a second language and a public portfolio move a graduate from the bottom band to the middle one faster than any master's degree.")

    callout(
        doc,
        "The verdict",
        "This degree is a good bet if you will treat it as three years of writing practice, plus a "
        "foreign language, plus two internships — and if you are willing to compete for a small number "
        "of formal jobs. It is a weak bet if you are choosing it because it is familiar, if you will not "
        "leave your home state for work, or if you expect the certificate to do the selling.",
    )

    h2(doc, "How to read the numbers")
    body(
        doc,
        "Salary figures here are indicative monthly gross ranges for 2026, compiled from published "
        "salary guides, job postings, federal civil-service scales and practitioner reports. Nigerian "
        "salary data is thin and self-reported, so the ranges are wide on purpose. Treat every figure as "
        "a negotiation anchor, not a benchmark.",
    )
    body(
        doc,
        "Labour-market statistics come from the National Bureau of Statistics (NBS) and from independent "
        "analyses of NBS microdata; where a figure is a secondary estimate, it is labelled as such. All "
        "naira figures are nominal. With inflation near 14%, a salary that does not move each year is a "
        "pay cut in real terms.",
    )


def section_two(doc):
    h1(doc, "02", "The market you are entering")
    body(
        doc,
        "Nigeria does not have a graduate unemployment crisis in the way the headlines suggest. It has a "
        "formal-employment crisis, which is different and, for a humanities graduate, worse. The official "
        "rate is low because the definition is generous and because most work happens outside the formal "
        "economy. Neither fact helps you find a job with a pension.",
    )

    table(
        doc,
        ["Indicator", "Latest", "Why it matters to you"],
        [
            ["Headline unemployment", "4.9% (Q4 2024)", "Flatters reality: one hour of paid work in a week counts as employed"],
            ["Youth unemployment, 15–34", "33.3%", "Your actual age cohort, not the national average"],
            ["Recent graduates, 0–5 years", "41.2%", "The queue you join at graduation"],
            ["Informal share of youth work", "52.4%", "Most employment is precarious and unrecorded"],
            ["Public sector share of youth jobs", "8.3%", "The civil-service route is narrow and shrinking"],
            ["Tertiary-educated unemployment", "23.1%", "A degree still helps — relatively"],
            ["National minimum wage", "₦70,000 / month", "The floor for formal work"],
            ["Federal civil service entry", "₦123,273 / month", "GL 08 step 1 — the benchmark government graduate job"],
            ["Headline inflation", "~14% (Oct 2026)", "Your salary must outrun this to stand still"],
        ],
        widths=[4.6, 3.5, 8.5],
        caption="Table 1. The labour market in nine numbers",
        caption_above=True,
    )
    body(
        doc,
        "Sources: NBS Labour Force Survey (headline and definition); NigeriaPolls analysis of NBS "
        "microdata, July 2026 (youth, graduate, informal and public-sector shares); Federal Civil Service "
        "Commission comparison figure via Profolio; BusinessDay inflation projection. Secondary estimates "
        "are indicative, not official releases.",
        size=7.8,
        color=GRAY,
        italic=True,
        space_after=12,
    )

    h2(doc, "What the numbers actually mean")
    body(
        doc,
        "Three things follow. First, the unemployment rate is close to meaningless as a measure of your "
        "prospects. Second, most young people who are working are in the informal sector, where earnings "
        "are volatile, untaxed and often below the minimum wage. Third, the public sector — the historical "
        "absorber of humanities graduates — now takes a small and shrinking share of young workers.",
    )
    body(
        doc,
        "So your competition is not the unemployment rate. It is the roughly fixed number of formal "
        "entry-level roles that open each year in Abuja, Lagos and Port Harcourt, and the informal "
        "networks that route candidates into them. A degree from a recognised university clears the first "
        "filter. After that, the differentiators are evidence of work, a referral, and a skill the "
        "employer cannot easily replace.",
    )

    callout(
        doc,
        "Plan for a queue, not a cliff",
        "Most graduates do find work eventually; the wait is long and the first job is often below the "
        "level the degree implies. Budget for a 12–24 month search rather than a six-month one, and keep "
        "a paid side skill running while you search. The graduates who suffer most are those who stop "
        "writing, stop applying and stop building evidence in the gap year.",
    )

    h2(doc, "What changed between 2024 and 2026")
    bullet(doc, "**Aid contracted.** The 2025 freeze and dismantling of US development funding removed a large block of Nigerian NGO and contractor roles — particularly in communications, programme management and monitoring and evaluation. The sector that absorbed IR graduates a decade ago is now smaller and more competitive.")
    bullet(doc, "**Inflation cooled but did not disappear.** Headline inflation is around 14%, down from the 2023–24 peak. Salaries have not caught up, and public-sector pay reviews have lagged prices.")
    bullet(doc, "**The naira stayed weak.** That makes remote work paid in dollars disproportionately valuable, and makes local salaries look worse in hard currency than they did in 2023.")
    bullet(doc, "**Hiring shifted towards hybrid skills.** Tech and financial services continued to hire, but favoured roles that combine writing with data, compliance or customer-facing work over pure content roles.")
    bullet(doc, "**Federal recruitment stayed periodic.** Centralised civil-service cycles open briefly and close fast, with long gaps between them. Missing a window can cost two years.")


def section_three(doc):
    h1(doc, "03", "What the degree actually gives you")
    body(
        doc,
        "The programme is not vocational, and it is a mistake to pretend otherwise. What it builds is a "
        "set of cognitive and rhetorical capabilities that employers say they cannot find in graduates — "
        "even as they decline to pay much for them at entry level. The gap between those two facts is "
        "where your career strategy lives.",
    )

    table(
        doc,
        ["Capability", "What employers buy with it", "How to prove it"],
        [
            ["Argument and structure", "Briefs, proposals, policy memos that survive scrutiny", "A two-page policy brief on a live Nigerian issue"],
            ["Source evaluation", "Research, fact-checking, due diligence, compliance", "A research note with footnoted, verifiable sources"],
            ["Audience switching", "Donor reports, executive summaries, press materials", "The same issue written for three different readers"],
            ["Comparative politics", "Risk analysis, public affairs, government relations", "A country or state risk memo with scenarios"],
            ["Cultural and language competence", "Diplomacy, field roles, localisation", "A B2 language certificate plus in-country experience"],
            ["Close reading", "Editing, legal-adjacent work, discourse and reputational analysis", "An editorial test, or a published edit with tracked changes"],
        ],
        widths=[4.0, 6.3, 6.3],
        caption="Table 2. Six capabilities and their market value",
    )

    h2(doc, "What it does not give you")
    bullet(doc, "**Numbers, unless you choose them.** Most English and IR curricula stop at basic statistics. The jobs that pay best increasingly assume Excel, SQL or evaluation design.")
    bullet(doc, "**Sector knowledge.** You will know how the UN system works; you will not know how a Nigerian health programme is budgeted, or how a gas project's community agreement is drafted.")
    bullet(doc, "**A network.** The strongest graduate outcomes in Nigeria run through referrals. Your lecturers, alumni and internship supervisors are the network — treat them as such from year one.")
    bullet(doc, "**A licence.** There is no bar exam equivalent. Nothing converts this degree into a credential that employers must accept, which is why the portfolio matters more here than in law or medicine.")

    quote(
        doc,
        "The degree teaches you to read the world carefully. It pays you only when you can sell that "
        "reading to someone with a budget.",
    )


def section_four(doc):
    h1(doc, "04", "Eight pathways", new_page=True)
    body(
        doc,
        "These are ordered roughly by how many graduates they absorb, not by prestige. Each entry gives "
        "the realistic route in, what the work is, what it pays, and the single first move that most "
        "improves your odds.",
    )

    # 4.1
    h2(doc, "4.1  Government, diplomacy and public service")
    body(
        doc,
        "The Federal Civil Service Commission recruits Foreign Affairs Officer II at SGL 08 for holders "
        "of a degree in the social sciences and humanities, with NYSC discharge; a parallel SGL 09 grade "
        "exists for master's holders. The January 2025 round is the template: a short application window, "
        "a national pool, federal-character balancing, and a posting to the Ministry of Foreign Affairs in "
        "Abuja before any mission abroad. New entrants train at the Nigerian Foreign Service Academy in "
        "Lagos, then rotate between headquarters and embassies.",
    )
    body(
        doc,
        "Pay is modest at the start — SGL 08 step 1 is ₦123,273 a month, the same graduate grade as the "
        "rest of the federal service — but the non-cash value is real: pensionable tenure, structured "
        "training, and eventually a posting abroad with allowances and diplomatic status. Promotion runs "
        "from Officer II through Officer I, Senior, Principal and Assistant Chief. A master's enters you "
        "one grade higher and compresses the ladder.",
    )
    body(
        doc,
        "Competition is severe and the process is opaque. The ministry has publicly disclaimed fake "
        "\"foreign service recruitment\" exercises at least twice since 2025. Applications run only "
        "through the FCSC portal, and no payment is ever required. State civil services, legislative "
        "aides and local government roles are lower-profile alternatives with faster entry.",
    )
    label_line(doc, "Pay", "₦123,000/month at entry (GL 08/1) plus allowances; overseas postings materially change the package.")
    label_line(doc, "First move", "Open an FCSC portal account now and set an alert; add French, Arabic or Mandarin while you wait for a cycle.")

    # 4.2
    h2(doc, "4.2  Development, humanitarian and NGO work")
    body(
        doc,
        "Historically the largest employer of IR graduates in Nigeria, and still the sector where the "
        "degree is most directly relevant. Roles include programme officer, monitoring and evaluation "
        "officer, communications officer, grants and partnerships, safeguarding, and logistics "
        "coordination. The work suits people who can write a donor report, read a budget line, and sit in "
        "a community meeting without patronising anyone.",
    )
    body(
        doc,
        "The sector contracted sharply after the 2025 US funding withdrawal: fewer international NGOs, "
        "smaller portfolios, more short-term contracts. What remains favours candidates with measurable "
        "field experience, donor literacy (logframes, indicators, compliance) and a specialism — "
        "protection, health, livelihoods or climate.",
    )
    body(
        doc,
        "Pay is the widest band in this report. A national NGO might start at ₦250,000; an international "
        "NGO at ₦400,000–₦600,000; a UN national officer post several multiples of that on the UN's own "
        "national salary scale. The catch is that the best-paid roles expect a master's and three to five "
        "years of experience.",
    )
    label_line(doc, "Pay", "₦250,000–₦600,000/month at entry, national to international NGO; UN national officer roles sit well above that.")
    label_line(doc, "First move", "Volunteer with a local NGO for one full project cycle, and learn to build a logframe and a budget in Excel.")

    # 4.3
    h2(doc, "4.3  Media, publishing and corporate communications")
    body(
        doc,
        "Journalism in Nigeria is poorly paid relative to its influence — ₦100,000–₦300,000 at entry is "
        "common, and payment is irregular at smaller outlets. Corporate communications, public relations "
        "and internal communications pay better and are more stable: banks, telecoms, energy companies and "
        "consultancies all need people who can write a press release, a speech and an annual report "
        "without supervision.",
    )
    body(
        doc,
        "The hiring test is a portfolio, not a certificate. Three published pieces and one "
        "internal-communications sample will do more than a first-class degree in many cases — and they "
        "are the fastest thing on this list to build.",
    )
    label_line(doc, "Pay", "₦100,000–₦300,000/month in journalism; ₦150,000–₦400,000 in corporate or agency communications.")
    label_line(doc, "First move", "Publish three pieces in a real outlet — campus paper, online platform, think-tank blog — and keep them in one link.")

    # 4.4
    h2(doc, "4.4  Education and edtech")
    body(
        doc,
        "Teaching absorbs more humanities graduates than any other sector and pays least at the bottom: "
        "private secondary schools in Lagos commonly offer ₦80,000–₦150,000, public schools somewhat more "
        "with pension and benefits. The premium end is international schools and exam preparation — "
        "IELTS, SAT, A-levels — where ₦250,000–₦600,000 is achievable with a recognised teaching "
        "qualification and strong spoken English.",
    )
    body(
        doc,
        "Adjacent routes pay better for the same skill: international admissions consulting "
        "(₦150,000–₦300,000 plus commission), curriculum and content roles at edtech companies, and "
        "corporate training. A CELTA or TESOL opens international-school and overseas tutoring markets; "
        "TRCN registration is required for regulated teaching posts.",
    )
    label_line(doc, "Pay", "₦80,000–₦200,000/month in private schools; ₦250,000–₦600,000 in international schools and premium exam prep.")
    label_line(doc, "First move", "If teaching is the plan, register with TRCN and start tutoring for exam prep; if not, treat education as a bridge, not a destination.")

    # 4.5
    h2(doc, "4.5  Oil, gas and extractives")
    body(
        doc,
        "The highest-paying conventional employer of IR graduates, and the hardest to enter. Community "
        "relations, social performance, government affairs and stakeholder engagement teams need people "
        "who can map stakeholders, run a grievance mechanism, write an ESG disclosure and hold a difficult "
        "meeting in a host community. The work is concentrated in Lagos, Abuja, Port Harcourt and Warri, "
        "and much of it is hired through contractors rather than the majors directly.",
    )
    body(
        doc,
        "Pay reflects the risk and the scarcity: ₦400,000–₦900,000 a month at entry-to-mid level is "
        "realistic, with contractor premiums. The catch is volume — very few seats, heavily networked, and "
        "a sector under pressure to decarbonise.",
    )
    label_line(doc, "Pay", "₦400,000–₦900,000/month at entry to mid level, often on renewable contracts without pension.")
    label_line(doc, "First move", "Target the service companies that supply the majors, and learn the language of social performance and local content.")

    # 4.6
    h2(doc, "4.6  Banking, consulting and financial services")
    body(
        doc,
        "Graduate trainee schemes are largely discipline-agnostic and remain one of the most reliable "
        "routes into formal employment. Within banks, the natural fits are compliance and KYC, corporate "
        "affairs, human resources, ESG and customer experience; in consulting, public-sector and "
        "development practices value the ability to read policy and write a coherent slide.",
    )
    body(
        doc,
        "Entry pay is ₦200,000–₦450,000 a month for trainees, rising quickly with performance. The "
        "trade-off is that the work rewards numeracy and process discipline more than essay-writing, so "
        "the degree is a starting point rather than an advantage.",
    )
    label_line(doc, "Pay", "₦200,000–₦450,000/month as a trainee, with fast increments for strong performers.")
    label_line(doc, "First move", "Practise aptitude tests early, learn Excel properly, and apply to every trainee scheme in your final year — they open and close fast.")

    # 4.7
    h2(doc, "4.7  Technology and global remote work")
    body(
        doc,
        "The arbitrage route. Nigerian companies pay ₦300,000–₦900,000 for content, policy, "
        "trust-and-safety, localisation, customer success and research-operations roles; global companies "
        "pay $800–$2,500 a month for the same work done remotely, which at current exchange rates is "
        "transformational.",
    )
    body(
        doc,
        "What gets you in is not the degree but one demonstrable hard skill: SEO and content strategy, "
        "SQL, a design tool, a CRM, or a portfolio of published work. The degree supplies the writing and "
        "judgement; the tool supplies the proof.",
    )
    label_line(doc, "Pay", "₦300,000–₦900,000/month locally; $800–$2,500/month for remote entry-level roles with global companies.")
    label_line(doc, "First move", "Pick one hard skill, build one public artefact — a newsletter, a dashboard, a rewritten help centre — and apply to global job boards weekly.")

    # 4.8
    h2(doc, "4.8  Research, think tanks and academia")
    body(
        doc,
        "Nigeria's policy research ecosystem — NIIA, CDD, Nextier, university centres and the Abuja "
        "offices of international research programmes — hires research assistants and programme officers "
        "who can design a study, clean a dataset and write a policy brief. The work is intellectually the "
        "closest to the degree, and the worst paid relative to the skills it demands until you reach "
        "senior research or donor-funded programme leadership.",
    )
    body(
        doc,
        "A master's is effectively the entry ticket for serious research roles, and a PhD for academia. "
        "Funding is the constraint; the funding routes are in section 10.",
    )
    label_line(doc, "Pay", "₦200,000–₦450,000/month as a research assistant; senior research and programme roles exceed ₦1m.")
    label_line(doc, "First move", "Write one policy brief on a live Nigerian issue and send it to three think tanks; learn Stata, R or Python basics.")

    table(
        doc,
        ["Pathway", "Route in", "Entry pay (₦/month)", "Competition", "5-year realistic range"],
        [
            ["Government / diplomacy", "FCSC examination", "123,000", "Very high, periodic", "250,000–400,000 + allowances"],
            ["Development / NGO", "Programme assistant", "250,000–600,000", "High", "600,000–1,200,000"],
            ["Media / comms", "Portfolio + internship", "100,000–400,000", "Medium", "400,000–900,000"],
            ["Education / edtech", "TRCN, CELTA, tutoring", "80,000–600,000", "Medium", "300,000–900,000"],
            ["Oil, gas / extractives", "Contractor entry", "400,000–900,000", "Very high", "900,000–2,000,000"],
            ["Banking / consulting", "Graduate trainee scheme", "200,000–450,000", "High", "600,000–1,500,000"],
            ["Tech / global remote", "Portfolio + global apply", "300,000–900,000", "Medium", "900,000–3,000,000+"],
            ["Research / think tank", "RA role + master's", "200,000–450,000", "High", "500,000–1,200,000"],
        ],
        widths=[3.3, 3.6, 3.3, 2.8, 3.6],
        font_size=8.0,
        caption="Table 3. Pathways compared. Pay is indicative monthly gross; competition reflects credible applicants per place, not advertised roles.",
    )


def section_five(doc):
    h1(doc, "05", "What you can realistically earn", new_page=True)
    body(
        doc,
        "Two graduates of the same programme, five years out, can differ by a factor of five or more. The chart "
        "below shows the ranges behind that spread for entry-level roles. The dot is a midpoint, not a "
        "promise; the bar is the range within which most offers land.",
    )
    figure(
        doc,
        CHART,
        16.0,
        "Figure 1. Entry-level monthly gross pay by pathway, 2026. Ranges compiled from published salary "
        "guides, job postings and practitioner reports; the civil-service bar begins at the published "
        "CONPSS GL 08 step 1 rate and its upper end assumes allowances. Treat all figures as indicative.",
    )

    h2(doc, "Three patterns")
    bullet(doc, "**The floor is low and flat.** Teaching, journalism and small NGOs cluster at ₦80,000–₦250,000, and those salaries move slowly. Years of service buy security there, not income.")
    bullet(doc, "**The middle is where most careers settle.** Corporate communications, banking and programme management reach ₦400,000–₦700,000 by year five with competent performance and one job change.")
    bullet(doc, "**The ceiling is set by sector, not seniority.** Energy, global remote work and senior development roles pay multiples of the local median, and they are gated by specialist skills rather than years served.")

    h2(doc, "Reading pay correctly")
    bullet(doc, "**Gross is not net.** PAYE and pension can take 10–25% of a formal salary. Informal work is untaxed but unprotected, and the difference matters when you need a mortgage or a visa.")
    bullet(doc, "**The package matters.** HMO cover, transport, housing, a 13th month and a training budget are often worth more than the base salary difference between two offers.")
    bullet(doc, "**Contract is not staff.** Many energy and NGO roles are annual contracts with no pension and no notice. Price that risk into the salary you ask for.")
    bullet(doc, "**Currency is the biggest lever.** A ₦600,000 salary is roughly $400–$500 at 2026 rates. A $1,500 remote salary is several times that for the same skills. No other change available to a Nigerian graduate moves pay as much.")
    bullet(doc, "**Survey data is thin.** PayScale's Nigerian sample for communications officers is 13 profiles, averaging ₦2.05m a year, with early-career pay at ₦1.75m. Directionally useful, statistically fragile.")

    callout(
        doc,
        "A useful rule",
        "Compare offers on three axes, not one: cash today, skills acquired in the next 24 months, and "
        "access to the next job. A lower salary at an employer whose name opens doors is often the better "
        "trade in your first two years — but only if the skills are real and the name travels.",
        fill=LIGHT,
        accent=GOLD,
    )


def section_six(doc):
    h1(doc, "06", "The premium stack")
    body(
        doc,
        "The difference between the bottom and middle bands is rarely talent. It is the presence of two or "
        "three additions that an employer can verify in under a minute. These are the five with the best "
        "return for the effort.",
    )

    h2(doc, "1. Numbers")
    body(
        doc,
        "Excel to SQL to basic evaluation design. Every programme, policy and communications role now "
        "involves some measurement: reach, spend, indicators, conversion. A graduate who can build a clean "
        "dashboard is rarer than one who can write a good essay, and is paid accordingly.",
    )
    label_line(doc, "Cheapest route", "One free Excel/SQL course, then rebuild a real dataset — a state budget, an NGO's reach figures — into a one-page dashboard.")

    h2(doc, "2. A second language")
    body(
        doc,
        "French is the highest-return language in West Africa; Arabic matters for the Sahel and for "
        "humanitarian work; Mandarin and Portuguese appear in trade and energy roles. Adverts for the "
        "foreign affairs cadre have named French, Spanish, Portuguese and Chinese as an added advantage. "
        "Language competence is also the cheapest signal of seriousness "
        "available to a humanities graduate, because it is certified rather than claimed.",
    )
    label_line(doc, "Cheapest route", "Alliance Française or Confucius Institute evening classes to B2, then a DELF/DALF or HSK certificate.")

    h2(doc, "3. A public portfolio")
    body(
        doc,
        "Three published pieces, one policy brief, one internal-communications sample. This replaces the "
        "sentence \"I am a strong writer\", which every candidate writes and no employer believes. A "
        "portfolio also survives the AI screening stage, because it is a link rather than an adjective.",
    )
    label_line(doc, "Cheapest route", "Pitch three pieces to outlets that publish students; write one brief for a think tank or NGO; host everything on one page.")

    h2(doc, "4. Sector depth")
    body(
        doc,
        "Pick one sector — energy, health, governance, humanitarian, finance — and learn its vocabulary, "
        "its funders and its recurring arguments. Domain knowledge is what generalist AI tools cannot "
        "supply and what generalist graduates lack. It is also what makes a mid-career move possible "
        "without starting again.",
    )
    label_line(doc, "Cheapest route", "One internship plus twenty informational interviews inside the sector, and read its trade press for six months.")

    h2(doc, "5. Global exposure")
    body(
        doc,
        "A remote internship for a foreign organisation, a fellowship, a regional programme, or a "
        "conference paper. Each is a credential that signals you can operate outside the Nigerian market, "
        "and each widens the set of employers who will read your CV.",
    )
    label_line(doc, "Cheapest route", "ECOWAS Young Professionals Programme (under 35, open to graduates of member states), UN Volunteers, or a remote internship with a diaspora-led organisation.")

    table(
        doc,
        ["Multiplier", "Time to build", "Typical pay effect", "What it unlocks"],
        [
            ["Numbers", "3–6 months", "+20–40% at entry", "M&E, programme management, consulting"],
            ["Second language", "12–24 months", "+15–35%, or a required filter", "Diplomacy, regional bodies, field roles"],
            ["Public portfolio", "3–6 months", "Converts interviews into offers", "Comms, media, policy, remote work"],
            ["Sector depth", "12 months", "+30–60% by mid-career", "Energy, health, governance, finance"],
            ["Global exposure", "6–18 months", "Often 2× or more", "Remote work, international NGOs, master's funding"],
        ],
        widths=[3.6, 3.2, 4.4, 5.4],
        caption="Table 4. What each multiplier is worth. Effects are indicative and compound: two multipliers together are worth more than the sum of each alone.",
    )


def section_seven(doc):
    h1(doc, "07", "The money case")
    body(
        doc,
        "A degree is a four-year investment with a delayed and uncertain return. In Nigeria the tuition is "
        "often the smallest part of the cost; living costs and forgone earnings are larger, and they "
        "differ enormously between a federal university in your home state and a private university in "
        "Lagos.",
    )

    table(
        doc,
        ["Institution type", "Tuition / year", "Living and other / year", "Four-year total"],
        [
            ["Federal university", "₦60,000–₦250,000", "₦400,000–₦900,000", "₦2.0m–₦4.6m"],
            ["State university", "₦100,000–₦350,000", "₦400,000–₦900,000", "₦2.4m–₦5.0m"],
            ["Private university", "₦1.5m–₦6.0m", "₦900,000–₦2.0m", "₦9.6m–₦32m"],
        ],
        widths=[4.2, 4.0, 4.2, 4.2],
        caption="Table 5. Approximate cost of a four-year degree, 2026. Tuition varies by programme and by state; private fees at the top end exceed ₦6m a year. Figures exclude forgone earnings.",
    )

    body(
        doc,
        "The break-even calculation is less interesting than it looks, because the degree's value is not "
        "mainly the salary premium. It is access: to the civil service, to master's programmes, to visa "
        "categories and to most formal graduate schemes. Without it, those doors are closed regardless of "
        "skill. That access is worth paying for; the salary premium alone often is not.",
    )

    table(
        doc,
        ["Scenario", "Time to first formal job", "Entry pay", "Year 5", "Year 10", "Cumulative, 10 years"],
        [
            ["Pessimistic", "24+ months, informal bridge", "₦100,000", "₦180,000", "₦300,000", "≈ ₦23m"],
            ["Base", "12 months", "₦200,000", "₦350,000", "₦600,000", "≈ ₦52m"],
            ["Optimistic", "6 months", "₦350,000", "₦700,000", "₦1,400,000", "≈ ₦115m"],
        ],
        widths=[2.6, 4.4, 2.6, 2.2, 2.2, 2.6],
        font_size=8.0,
        caption="Table 6. Rough ten-year nominal earnings under three scenarios. Nominal figures ignore inflation, which has averaged well above 15% since 2023; the ordering, not the absolute numbers, is the point.",
    )

    body(
        doc,
        "On the base case, a federal degree pays back its cost within two to three years of formal "
        "employment, and a private degree within five to seven. The pessimistic case is the one to plan "
        "for: two years of search and informal work before a formal role, and a decade to recover a "
        "private-university outlay. That is the case in which the degree still works as a credential but "
        "fails as an investment.",
    )

    callout(
        doc,
        "The real investment",
        "The certificate is not the investment; the four years are. Internships, languages, tools and "
        "grades determine the return far more than the course title does. A student who graduates with a "
        "portfolio and two internships has already beaten most of the optimistic scenario's assumptions.",
    )


def section_eight(doc):
    h1(doc, "08", "Risks on the horizon")
    body(
        doc,
        "Six risks are specific enough to plan around. None of them makes the degree a bad choice; all "
        "of them change what you should do while studying.",
    )

    table(
        doc,
        ["Risk", "What it does to you", "How to hedge"],
        [
            ["AI compresses entry-level writing", "Shrinks junior content, translation and research-assistant tasks — the traditional first rung", "Own judgement, sourcing and sector data; publish work that shows analysis, not volume"],
            ["Aid sector contraction", "Fewer NGO and contractor roles after the 2025 US funding withdrawal", "Diversify across government, foundations, private sector and regional bodies"],
            ["Naira volatility and inflation", "Real pay falls even when nominal pay rises", "Build a dollar-linked income stream; renegotiate annually, not every three years"],
            ["Oversupply of humanities graduates", "More applicants than formal roles, especially in Lagos and Abuja", "Differentiate with the stack, not the certificate; consider less saturated cities"],
            ["Credential inflation", "A master's becomes the standard for NGO, diplomacy and research roles", "Plan and fund a master's early; do not drift into one at 30 with no funding"],
            ["Emigration of peers", "Networks thin out; competition for local roles shifts", "Treat emigration as an option to keep open, not a plan that solves everything"],
        ],
        widths=[4.2, 6.4, 6.0],
        font_size=8.0,
        caption="Table 7. Risks and hedges",
    )

    body(
        doc,
        "The AI risk deserves a sentence of its own. The tasks most exposed are exactly the ones graduates "
        "used to be hired for: drafting, summarising, translating, basic research. The tasks that are not "
        "exposed are judgement under uncertainty, relationships, field presence and accountability for a "
        "decision. A degree that trains you to argue and verify is still useful; a degree treated as a "
        "licence to produce prose is not.",
    )


def section_nine(doc):
    h1(doc, "09", "A five-year plan")
    body(
        doc,
        "This is the difference between the base and optimistic scenarios, written as a checklist. It "
        "assumes a four-year degree and one year of NYSC, and it is deliberately specific.",
    )

    table(
        doc,
        ["Year", "Focus", "Evidence you can show", "Milestone"],
        [
            ["100 level", "Writing, GPA, one language", "Six graded essays; beginner French or Mandarin", "CGPA 3.5+; language class enrolled"],
            ["200 level", "Tools and first exposure", "Excel/SQL certificate; one volunteer role", "First internship or NGO placement"],
            ["300 level", "SIWES and portfolio", "Three published pieces; one policy brief", "Internship converted into a reference"],
            ["400 level", "Launch", "Final-year project on your chosen sector; 50 applications", "Graduate trainee or NGO offer before graduation"],
            ["NYSC year", "Strategic posting", "Posting in Abuja, Lagos or a sector employer", "Conversion to staff or a strong referral"],
        ],
        widths=[2.3, 4.3, 6.4, 3.6],
        font_size=8.0,
        caption="Table 8. The five-year plan",
    )

    body(
        doc,
        "Years six to eight are the fork. One path is specialisation: a master's, a professional "
        "certificate, and a move into a senior technical or managerial role. The other is geography: a "
        "regional or international move, through a fellowship, a remote role or a funded master's. Both "
        "are easier if you decided by year three rather than after graduation, because funding deadlines "
        "and language requirements are set well in advance.",
    )


def section_ten(doc):
    h1(doc, "10", "Beyond Nigeria")
    body(
        doc,
        "The regional and global routes are the highest-leverage moves available, and most are "
        "under-applied for. Few require family money as a precondition; all require planning a year or more ahead.",
    )

    h2(doc, "Regional and international programmes")
    bullet(doc, "**ECOWAS Young Professionals Programme.** Open to graduates of member states under 35, with profiles including communication, project management, political science and law. Apply with a CV, motivation letter, diplomas and nationality documents; selection is competitive but the pool is regional rather than global.")
    bullet(doc, "**African Union and UN routes.** AU youth programmes, UN Volunteers and Junior Professional Officer schemes. Most expect a master's, two years of experience and at least one additional language.")
    bullet(doc, "**Study in the region.** Ghana, Kenya and South Africa offer recognised degrees at lower cost than the UK or US, and a regional network that is useful for NGO and diplomacy careers.")

    h2(doc, "Funded master's routes")
    bullet(doc, "**Chevening (UK).** Fully funded one-year master's; requires two years of work experience and a leadership record. Applications typically open in August and close in November.")
    bullet(doc, "**Commonwealth Scholarships (UK).** For development-relevant master's degrees; nominations run through national agencies, usually in late autumn.")
    bullet(doc, "**DAAD EPOS (Germany).** Development-related postgraduate courses; usually requires two years of professional experience.")
    bullet(doc, "**Erasmus Mundus (EU).** Joint master's programmes with full funding; deadlines cluster between October and January.")
    bullet(doc, "**Mastercard Foundation Scholars.** For African students with financial need and academic strength, at partner universities.")

    callout(
        doc,
        "Timing note",
        "Funding deadlines fall in the year before study, often while you are still in NYSC or in your "
        "first job. The single most common reason strong candidates miss these routes is that they started "
        "looking after graduation. Start in your final year.",
        fill=LIGHT,
        accent=GOLD,
    )


def section_eleven(doc):
    h1(doc, "11", "The decision guide")
    body(
        doc,
        "Score each statement from 1 (not true of me) to 5 (very true). The total is less important than "
        "which items score low — those are the ones to fix or to design around.",
    )

    table(
        doc,
        ["Statement", "Score (1–5)"],
        [
            ["I will write regularly even when no one is grading me.", ""],
            ["I am willing to move to another state, or country, for the right first job.", ""],
            ["I will take a maths or data course even though it is not required.", ""],
            ["I can name three specific employers I want to work for, and why.", ""],
            ["I have, or will build, a public portfolio before graduation.", ""],
            ["I can fund, or win funding for, a master's within five years if needed.", ""],
        ],
        widths=[14.0, 2.6],
        font_size=8.6,
        zebra=True,
        caption=None,
    )

    body(
        doc,
        "A total of 24–30 suggests the degree will work as a platform. A total of 16–23 is workable but "
        "conditional: fix the two lowest items before graduation. Below 16, the degree is being chosen for "
        "the wrong reasons, and a more applied programme — or a different combination — is likely to pay "
        "better.",
        space_after=10,
    )

    h2(doc, "If you are choosing now")
    bullet(doc, "**Pair it deliberately.** Combined honours with law, economics, mass communication or computer science is worth more than either half alone, because it produces a graduate who can write and do something else.")
    bullet(doc, "**Choose the institution for its writing centre, language options and internship pipeline**, not its slogan. Ask where last year's graduates went.")
    bullet(doc, "**Check that the programme includes a language and a methods course.** If it does not, you will have to buy them separately.")
    bullet(doc, "**Avoid programmes with no external examination, no internship requirement and no alumni network.** Those are the ones whose graduates struggle most.")

    h2(doc, "If you have already chosen")
    bullet(doc, "**This month:** build a one-page portfolio site and publish one piece.")
    bullet(doc, "**This term:** start a language class and one data course.")
    bullet(doc, "**This year:** secure one internship, paid or unpaid, in a sector you might actually enter.")
    bullet(doc, "**Before graduation:** apply to ten graduate schemes and five NGOs, and ask three people for referrals.")


def section_twelve(doc):
    h1(doc, "12", "Sources and notes")
    body(
        doc,
        "Figures are as at November 2026. Salary ranges are compiled estimates, not survey measurements; "
        "where a published figure exists, it is cited below. Labour-market statistics are official NBS "
        "releases or independent analyses of NBS microdata, labelled accordingly in the text.",
        size=9.2,
        color=GRAY,
    )

    sources = [
        ("National Bureau of Statistics — Labour Force Survey, headline and employment rate (4.9%, Q4 2024)", "tradingeconomics.com/nigeria/unemployment-rate"),
        ("NigeriaPolls — ‘Youth Unemployment in Nigeria: What the Data Really Shows’, July 2026 (youth, graduate, informal and public-sector shares)", "nigeriapolls.com/blog/youth-unemployment-data-nigeria"),
        ("Profolio — Foreign Service Officer guide, citing Federal Civil Service Commission January 2025 postings and the CONPSS GL 08 rate", "profolio.ng/foreign-service-officer/job-description"),
        ("BusinessDay — inflation projection, November 2026", "businessday.ng/backpage/article/nigeria-inflation-seen-easing-to-13-99-in-october/"),
        ("Gidi Naija — salary structure for English and education graduates (indicative bands)", "gidinaija.ng/salary-structure-of-education-and-english-language-graduate-in-nigeria/"),
        ("PayScale — Communications Officer salary in Nigeria, 2026 (n=13)", "payscale.com/research/NG/Job=Communications_Officer/Salary"),
        ("ECOWAS — Young Professionals Programme, eligibility and application", "youngprofessional.ecowas.int/en/faq/"),
        ("Hivos / Eu SEE — consequences of the US funding freeze on civil society", "eusee.hivos.org/the-consequences-of-the-us-funding-freeze-extend-far-beyond-budgets-and-balance-sheets/"),
        ("AllAfrica — aid withdrawal and Nigeria's insurgency crisis", "allafrica.com/view/group/main/main/id/00092671.html"),
    ]
    for i, (title, url) in enumerate(sources, start=1):
        paragraph = doc.add_paragraph()
        fmt = paragraph.paragraph_format
        fmt.left_indent = Cm(0.9)
        fmt.first_line_indent = Cm(-0.9)
        fmt.space_after = Pt(5)
        fmt.line_spacing = 1.05
        run = paragraph.add_run(f"{i}.  ")
        run.font.name = HEAD_FONT
        run.font.size = Pt(8.2)
        run.font.bold = True
        run.font.color.rgb = c(GOLD)
        run = paragraph.add_run(title + "  ")
        run.font.name = BODY_FONT
        run.font.size = Pt(8.6)
        run.font.color.rgb = c(INK)
        add_hyperlink(paragraph, "https://" + url, url)

    note = doc.add_paragraph()
    note.paragraph_format.space_before = Pt(14)
    _add_runs(
        note,
        "Compiled November 2026. This report is an independent analysis for planning purposes; it is not "
        "financial, legal or immigration advice. Verify current figures, deadlines and eligibility before "
        "acting on them.",
        7.6,
        color=MUTED,
        italic=True,
    )


def main():
    doc = Document()
    setup(doc)
    cover(doc)
    section_one(doc)
    section_two(doc)
    section_three(doc)
    section_four(doc)
    section_five(doc)
    section_six(doc)
    section_seven(doc)
    section_eight(doc)
    section_nine(doc)
    section_ten(doc)
    section_eleven(doc)
    section_twelve(doc)

    for container in [doc.element] + [sec.header._element for sec in doc.sections] + [sec.footer._element for sec in doc.sections]:
        _normalize(container)

    doc.core_properties.title = "English & International Relations: undergraduate degree potential in Nigeria and Africa"
    doc.core_properties.subject = "Career and earnings outlook, 2026"
    doc.core_properties.author = "Prepared for Taiwo Sokunbi"
    doc.core_properties.keywords = "Nigeria, graduate employment, international relations, career, earnings"

    doc.save(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
