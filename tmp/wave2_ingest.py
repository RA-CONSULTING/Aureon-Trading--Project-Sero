"""Knowledge Wave 2 — one-off ingest setup.

1. Extract every whitepaper .docx from aureon-os-upstream/docs/research/
   whitepapers/ to aureon_fusion/knowledge/whitepapers/<name>.md
   (stdlib zipfile + ElementTree, same pattern as the Bhoys Eyes book).
2. Hardlink (fallback: copy) the workspace prose corpus into
   aureon_fusion/knowledge/workspace/<category>/ so the knowledge
   ResearchCorpusIndex can serve it. Upstream repo stays read-only.

Writes only under aureon_fusion/knowledge/. Prints a JSON summary.
"""
from __future__ import annotations

import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WS = Path(".kimi_openclaw/workspace") if not Path("aureon-os-upstream").is_dir() else Path(".")
os.chdir(WS)

UP = Path("aureon-os-upstream")
KNOW = Path("aureon_fusion/knowledge")
WP_DIR = KNOW / "whitepapers"
WS_DIR = KNOW / "workspace"


def docx_to_md(src: Path, dst: Path) -> tuple[int, int]:
    with zipfile.ZipFile(src) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    body = root.find(W + "body")
    lines: list[str] = []
    n_para = n_head = 0
    for p in (body.iter(W + "p") if body is not None else []):
        parts = []
        for node in p.iter():
            if node.tag == W + "t":
                parts.append(node.text or "")
            elif node.tag == W + "tab":
                parts.append("\t")
            elif node.tag == W + "br":
                parts.append("\n")
        text = "".join(parts).strip()
        if not text:
            continue
        n_para += 1
        ppr = p.find(W + "pPr")
        style = ""
        if ppr is not None and ppr.find(W + "pStyle") is not None:
            style = (ppr.find(W + "pStyle").get(W + "val") or "").lower()
        if "heading" in style or style in ("title", "subtitle"):
            n_head += 1
            lines.append("\n## " + text + "\n")
        else:
            lines.append(text)
    header = (f"# {src.stem}\n\n> Extracted from upstream "
              f"`docs/research/whitepapers/{src.name}` (read-only source).\n\n")
    dst.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return n_para, n_head


def link_or_copy(src: Path, dst_dir: Path) -> bool:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if dst.exists():
        return False
    try:
        os.link(src, dst)
    except OSError:
        try:
            dst.write_bytes(src.read_bytes())
        except OSError:
            return False
    return True


def main() -> int:
    summary: dict = {"whitepapers": {}, "workspace": {}}

    # 1 ── whitepaper docx extraction
    WP_DIR.mkdir(parents=True, exist_ok=True)
    for docx in sorted((UP / "docs/research/whitepapers").glob("*.docx")):
        dst = WP_DIR / (docx.stem + ".md")
        try:
            n_para, n_head = docx_to_md(docx, dst)
            summary["whitepapers"][docx.name] = {
                "md": str(dst), "paragraphs": n_para, "headings": n_head,
                "chars": dst.stat().st_size}
        except Exception as exc:
            summary["whitepapers"][docx.name] = {"error": str(exc)}

    # 2 ── workspace prose hardlinks
    groups = {
        "papers": sorted(Path("research/papers").glob("*.txt")),
        "zenodo": sorted(Path("zenodo_papers").glob("*.txt")),
        "substack": sorted(Path("substack_output").glob("*.md")),
        "extracts": sorted(Path(".").glob("*_extracted.txt")),
        "diary": sorted(Path("memorized_diary").glob("*.md")),
        "owner": [p for p in (Path("USER.md"), Path("MEMORY.md")) if p.exists()],
    }
    for cat, files in groups.items():
        linked = skipped = 0
        for f in files:
            if link_or_copy(f, WS_DIR / cat):
                linked += 1
            else:
                skipped += 1
        summary["workspace"][cat] = {"linked": linked, "skipped": skipped}

    try:
        print(json.dumps(summary, ensure_ascii=False, indent=1))
    except UnicodeEncodeError:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
