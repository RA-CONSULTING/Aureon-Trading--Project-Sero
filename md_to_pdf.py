#!/usr/bin/env python3
"""
Convert Markdown pitch deck to PDF using reportlab.
"""
import sys
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    from reportlab.lib import colors
except ImportError:
    print("reportlab not available. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab", "-q"])
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    from reportlab.lib import colors


def md_to_pdf(md_path: str, pdf_path: str):
    md_file = Path(md_path)
    content = md_file.read_text(encoding="utf-8")

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DeckTitle",
        parent=styles["Title"],
        fontSize=26,
        leading=32,
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=18,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )

    subtitle_style = ParagraphStyle(
        "DeckSubtitle",
        parent=styles["Normal"],
        fontSize=14,
        leading=20,
        textColor=colors.HexColor("#4a4a6a"),
        spaceAfter=24,
        alignment=TA_CENTER,
        fontName="Helvetica-Oblique",
    )

    slide_title_style = ParagraphStyle(
        "SlideTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=26,
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=14,
        spaceBefore=20,
        fontName="Helvetica-Bold",
        borderPadding=(0, 0, 6, 0),
        borderColor=colors.HexColor("#4a4a6a"),
        borderWidth=0,
    )

    heading2_style = ParagraphStyle(
        "DeckHeading2",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#2a2a4e"),
        spaceAfter=8,
        spaceBefore=12,
        fontName="Helvetica-Bold",
    )

    heading3_style = ParagraphStyle(
        "DeckHeading3",
        parent=styles["Heading3"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#3a3a5e"),
        spaceAfter=6,
        spaceBefore=10,
        fontName="Helvetica-Bold",
    )

    body_style = ParagraphStyle(
        "DeckBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#2a2a2a"),
        spaceAfter=8,
        alignment=TA_JUSTIFY,
    )

    bullet_style = ParagraphStyle(
        "DeckBullet",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#2a2a2a"),
        spaceAfter=6,
        leftIndent=18,
        bulletIndent=8,
        bulletFontName="Helvetica-Bold",
    )

    code_style = ParagraphStyle(
        "DeckCode",
        parent=styles["Code"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1a1a2e"),
        backColor=colors.HexColor("#f4f4f8"),
        leftIndent=12,
        rightIndent=12,
        spaceAfter=10,
        spaceBefore=6,
        fontName="Courier",
    )

    footer_style = ParagraphStyle(
        "DeckFooter",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#888888"),
        alignment=TA_CENTER,
        spaceBefore=6,
    )

    elements = []
    slide_number = 0

    lines = content.splitlines()
    i = 0
    in_code_block = False
    code_lines = []
    in_table = False
    table_rows = []
    table_aligns = []

    while i < len(lines):
        line = lines[i]

        # Code blocks
        if line.strip().startswith("```"):
            if in_code_block:
                # End code block
                code_text = "<br/>".join(code_lines)
                elements.append(Paragraph(code_text, code_style))
                elements.append(Spacer(1, 6))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_lines.append(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            i += 1
            continue

        # Tables
        if line.strip().startswith("|") and not in_table:
            in_table = True
            table_rows = []
            # Skip header separator line if present
            i += 1
            if i < len(lines) and "---" in lines[i] and lines[i].strip().startswith("|"):
                i += 1
            continue

        if in_table:
            if not line.strip().startswith("|"):
                # End table
                if table_rows:
                    table_data = []
                    for row in table_rows:
                        cells = [c.strip() for c in row.split("|") if c.strip() or c == ""]
                        # Remove empty first/last cells from split
                        if cells and cells[0] == "":
                            cells = cells[1:]
                        if cells and cells[-1] == "":
                            cells = cells[:-1]
                        styled_cells = []
                        for cell in cells:
                            cell = cell.replace("**", "").strip()
                            cell = cell.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                            styled_cells.append(Paragraph(f"<font size='9'>{cell}</font>", body_style))
                        table_data.append(styled_cells)

                    if table_data:
                        col_count = max(len(r) for r in table_data)
                        col_widths = [doc.width / col_count] * col_count
                        t = Table(table_data, colWidths=col_widths)
                        t.setStyle(TableStyle([
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fafafa")),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]))
                        elements.append(t)
                        elements.append(Spacer(1, 10))
                in_table = False
                table_rows = []
                continue
            else:
                table_rows.append(line)
                i += 1
                continue

        # Horizontal rule / slide separator
        if line.strip() == "---":
            if slide_number > 0:
                elements.append(PageBreak())
            slide_number += 1
            i += 1
            continue

        # Slide titles (H1 ## Slide X: Title)
        if line.startswith("## "):
            title_text = line[3:].strip()
            title_text = title_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            elements.append(Paragraph(title_text, slide_title_style))
            i += 1
            continue

        # H2
        if line.startswith("### "):
            h2_text = line[4:].strip()
            h2_text = h2_text.replace("**", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            elements.append(Paragraph(f"<b>{h2_text}</b>", heading2_style))
            i += 1
            continue

        # H3
        if line.startswith("#### "):
            h3_text = line[5:].strip()
            h3_text = h3_text.replace("**", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            elements.append(Paragraph(f"<b>{h3_text}</b>", heading3_style))
            i += 1
            continue

        # Title slide H1
        if line.startswith("# ") and slide_number == 0:
            title_text = line[2:].strip()
            title_text = title_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            elements.append(Spacer(1, 80))
            elements.append(Paragraph(title_text, title_style))
            i += 1
            continue

        # Bold text handling
        def format_bold(text):
            # Handle **bold** -> <b>bold</b>
            import re
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
            return text

        # Bullet points
        if line.strip().startswith("- ") or line.strip().startswith("* "):
            bullet_text = line.strip()[2:]
            bullet_text = format_bold(bullet_text)
            bullet_text = bullet_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            bullet_text = bullet_text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
            elements.append(Paragraph(f"• {bullet_text}", bullet_style))
            i += 1
            continue

        # Numbered lists
        if line.strip() and line.strip()[0].isdigit() and ". " in line.strip()[:4]:
            num_text = line.strip()
            num_text = format_bold(num_text)
            num_text = num_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            num_text = num_text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
            elements.append(Paragraph(num_text, bullet_style))
            i += 1
            continue

        # Empty lines
        if not line.strip():
            i += 1
            continue

        # Regular paragraph
        para_text = line.strip()
        para_text = format_bold(para_text)
        para_text = para_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        para_text = para_text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
        elements.append(Paragraph(para_text, body_style))
        i += 1

    # End any remaining table
    if in_table and table_rows:
        table_data = []
        for row in table_rows:
            cells = [c.strip() for c in row.split("|") if c.strip() or c == ""]
            if cells and cells[0] == "":
                cells = cells[1:]
            if cells and cells[-1] == "":
                cells = cells[:-1]
            styled_cells = []
            for cell in cells:
                cell = cell.replace("**", "").strip()
                cell = cell.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                styled_cells.append(Paragraph(f"<font size='9'>{cell}</font>", body_style))
            table_data.append(styled_cells)

        if table_data:
            col_count = max(len(r) for r in table_data)
            col_widths = [doc.width / col_count] * col_count
            t = Table(table_data, colWidths=col_widths)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fafafa")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(t)

    # Footer on each page
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        footer_text = "R&A CONSULTING | HNC Framework Pitch Deck | HNC-VER-2025-0407-001"
        canvas.drawCentredString(doc.width / 2 + doc.leftMargin, 0.5 * cm, footer_text)
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)
    print(f"PDF generated: {pdf_path}")


if __name__ == "__main__":
    md_path = r"C:\Users\user\.kimi_openclaw\workspace\HNC_Framework_Pitch_Deck.md"
    pdf_path = r"C:\Users\user\.kimi_openclaw\workspace\HNC_Framework_Pitch_Deck.pdf"
    md_to_pdf(md_path, pdf_path)
