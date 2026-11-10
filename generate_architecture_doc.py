from pathlib import Path
import re
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "SYSTEM_ARCHITECTURE_AND_MODULE_WORKFLOWS.md"
OUTPUT = ROOT / "SYSTEM_ARCHITECTURE_AND_MODULE_WORKFLOWS.docx"


def add_cell_shading(cell, fill):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def add_bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    p.add_run(text)
    return p

def add_number(doc, text):
    p = doc.add_paragraph(style="List Number")
    p.add_run(text)
    return p

def add_code_diagram(doc, code):
    # Use an editable, monospaced workflow representation so diagram content
    # stays readable in Word even without an installed Mermaid renderer.
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.18)
    p.paragraph_format.right_indent = Inches(0.12)
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_together = True
    run = p.add_run(code.strip())
    run.font.name = "Consolas"
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(31, 55, 78)
    ppr = p._p.get_or_add_pPr()
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "F1F5F9")
    ppr.append(shd)


def add_rich_text(doc, text):
    # Small Markdown subset: bold and inline code.
    parts = re.split(r"(\*\*.*?\*\*|`.*?`)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            run = doc.add_paragraph().add_run(part[2:-2])
            run.bold = True
        else:
            # Inline code is styled in the paragraph assembled below.
            pass
    p = doc.add_paragraph()
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            r = p.add_run(part[2:-2])
            r.bold = True
        elif part.startswith("`") and part.endswith("`"):
            r = p.add_run(part[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(9)
            r.font.color.rgb = RGBColor(31, 78, 121)
        else:
            p.add_run(part)
    return p

def main():
    markdown = SOURCE.read_text(encoding="utf-8")
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10)
    normal.font.color.rgb = RGBColor(38, 50, 56)
    for style_name, size, color in [
        ("Title", 26, "12304A"),
        ("Heading 1", 19, "12304A"),
        ("Heading 2", 14, "176B87"),
        ("Heading 3", 11, "286A7B"),
    ]:
        style = doc.styles[style_name]
        style.font.name = "Aptos Display"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)

    # Header and page numbering footer.
    header = section.header.paragraphs[0]
    header.text = "EDUSEKAI  |  SYSTEM ARCHITECTURE & WORKFLOWS"
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header.runs[0].font.size = Pt(8)
    header.runs[0].font.color.rgb = RGBColor(100, 116, 139)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = footer.add_run("EduSekai · System architecture and module workflows")
    fr.font.size = Pt(8)
    fr.font.color.rgb = RGBColor(100, 116, 139)

    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("EDU Sekai\nSystem Architecture & Module Workflows")
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sr = subtitle.add_run("How the system is built and how each module works")
    sr.italic = True
    sr.font.color.rgb = RGBColor(71, 85, 105)
    note = doc.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    nr = note.add_run("Reflects the code on main as of 11 November 2026.")
    nr.font.size = Pt(9)
    nr.font.color.rgb = RGBColor(100, 116, 139)
    doc.add_paragraph()

    # The Markdown headings contain the contents map; use Word's built-in field.
    doc.add_heading("Contents", level=1)
    toc = doc.add_paragraph()
    run = toc.add_run()
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), 'TOC \\o "1-3" \\h \\z \\u')
    run._r.addnext(fld)
    doc.add_page_break()

    lines = markdown.splitlines()
    in_fence = False
    code_lines = []
    paragraph_lines = []
    for line in lines:
        if line.strip().startswith("```"):
            if not in_fence:
                if paragraph_lines:
                    add_rich_text(doc, " ".join(paragraph_lines).strip())
                    paragraph_lines = []
                in_fence = True
                code_lines = []
            else:
                add_code_diagram(doc, "\n".join(code_lines))
                in_fence = False
            continue
        if in_fence:
            code_lines.append(line)
            continue
        if not line.strip():
            if paragraph_lines:
                add_rich_text(doc, " ".join(paragraph_lines).strip())
                paragraph_lines = []
            continue
        if line.startswith("# "):
            continue  # Cover title already contains the document title.
        if line.startswith("## "):
            if paragraph_lines:
                add_rich_text(doc, " ".join(paragraph_lines).strip())
                paragraph_lines = []
            doc.add_heading(line[3:].strip(), level=1)
        elif line.startswith("### "):
            if paragraph_lines:
                add_rich_text(doc, " ".join(paragraph_lines).strip())
                paragraph_lines = []
            doc.add_heading(line[4:].strip(), level=2)
        elif line.startswith("> "):
            if paragraph_lines:
                add_rich_text(doc, " ".join(paragraph_lines).strip())
                paragraph_lines = []
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.2)
            r = p.add_run(line[2:].replace("**", ""))
            r.italic = True
            r.font.color.rgb = RGBColor(71, 85, 105)
        elif line.startswith("- "):
            if paragraph_lines:
                add_rich_text(doc, " ".join(paragraph_lines).strip())
                paragraph_lines = []
            add_bullet(doc, line[2:].replace("**", ""))
        elif re.match(r"^\d+\.\s", line):
            if paragraph_lines:
                add_rich_text(doc, " ".join(paragraph_lines).strip())
                paragraph_lines = []
            add_number(doc, re.sub(r"^\d+\.\s", "", line).replace("**", ""))
        else:
            paragraph_lines.append(line.strip())

    if paragraph_lines:
        add_rich_text(doc, " ".join(paragraph_lines).strip())

    doc.core_properties.title = "EduSekai — System Architecture and Module Workflows"
    doc.core_properties.subject = "Current architecture and module workflow documentation"
    doc.core_properties.author = "EduSekai"
    doc.save(OUTPUT)
    print(f"Created {OUTPUT.name} ({OUTPUT.stat().st_size:,} bytes)")

if __name__ == "__main__":
    main()
