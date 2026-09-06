"""One-off: extract bhoys_eyes_part_1_v1.1.2.docx to markdown.

Stdlib only: zipfile + ElementTree over word/document.xml. Paragraphs
become markdown lines; Word heading styles become '## ' headings; a
paragraph that is entirely uppercase/short is promoted to a heading.
"""
from __future__ import annotations

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

SRC = Path("aureon-os-upstream/docs/research/misc/bhoys_eyes_part_1_v1.1.2.docx")
DST = Path("aureon_fusion/knowledge/bhoys_eyes_part_1.md")

def para_text(p: ET.Element) -> str:
    parts: list[str] = []
    for node in p.iter():
        tag = node.tag
        if tag == W + "t":
            parts.append(node.text or "")
        elif tag == W + "tab":
            parts.append("\t")
        elif tag == W + "br":
            parts.append("\n")
    return "".join(parts).strip()

def para_style(p: ET.Element) -> str:
    ppr = p.find(W + "pPr")
    if ppr is None:
        return ""
    pstyle = ppr.find(W + "pStyle")
    if pstyle is None:
        return ""
    return pstyle.get(W + "val") or ""

def main() -> int:
    with zipfile.ZipFile(SRC) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    body = root.find(W + "body")
    assert body is not None

    lines: list[str] = []
    n_para = 0
    n_head = 0
    for p in body.iter(W + "p"):
        text = para_text(p)
        if not text:
            continue
        n_para += 1
        style = para_style(p).lower()
        is_heading = False
        if "heading" in style or style in ("title", "subtitle"):
            is_heading = True
        elif (text.isupper() and len(text) <= 80) or re.match(
                r"^(chapter|prologue|epilogue|interlude)\b", text, re.I):
            is_heading = True
        if is_heading:
            n_head += 1
            lines.append("\n## " + text.strip() + "\n")
        else:
            lines.append(text)

    header = (
        "# The Bhoys Eyes — Part 1\n\n"
        "> Extracted from `aureon-os-upstream/docs/research/misc/"
        "bhoys_eyes_part_1_v1.1.2.docx` (v1.1.2). Belfast, 1982 — Falls Road.\n"
        "> Source format: Word .docx; paragraphs and headings preserved.\n\n"
    )
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    out = f"paragraphs={n_para} headings={n_head} chars={sum(len(l) for l in lines)}"
    try:
        print(out)
    except UnicodeEncodeError:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
