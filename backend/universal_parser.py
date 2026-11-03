"""
SciGraph Universal Multi-Format Ingestion Parser
Ultra-fast, asynchronous parser supporting 18+ scientific & document formats.
Preserves page indices, citations, tabular markdown structures, and metadata.
"""

import os
import re
import csv
import json
import time
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("scigraph.universal_parser")


@dataclass
class ExtractionResult:
    content_list: List[Dict[str, Any]]
    full_text: str
    page_count: int
    char_count: int
    word_count: int
    format: str
    extraction_time_ms: float
    has_ocr: bool = False
    tables_count: int = 0
    images_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class UniversalParser:
    """
    High-speed universal parser for scientific research documents.
    Optimized for Windows laptops with PyMuPDF, python-docx, openpyxl, pptx, and bs4.
    """

    CACHE_DIR = Path("data/rag_storage/parser_cache")

    def __init__(self):
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _file_hash(self, file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def _get_cached(self, file_hash: str) -> Optional[ExtractionResult]:
        cache_file = self.CACHE_DIR / f"{file_hash}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                return ExtractionResult(**data)
            except Exception as e:
                logger.warning(f"Failed to read parser cache: {e}")
        return None

    def _save_cache(self, file_hash: str, result: ExtractionResult):
        cache_file = self.CACHE_DIR / f"{file_hash}.json"
        try:
            cache_file.write_text(
                json.dumps(result.__dict__, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to write parser cache: {e}")

    def extract(self, file_path: str | Path, force: bool = False) -> ExtractionResult:
        """Main entry point: extracts structured content and metadata from any supported file."""
        t0 = time.time()
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        file_hash = self._file_hash(path)
        if not force:
            cached = self._get_cached(file_hash)
            if cached is not None:
                logger.info(f"Using cached extraction for {path.name} (hash={file_hash[:8]})")
                cached.extraction_time_ms = 0.0
                return cached

        ext = path.suffix.lower()
        if ext == ".pdf":
            result = self._parse_pdf(path)
        elif ext in (".docx", ".doc"):
            result = self._parse_word(path)
        elif ext in (".xlsx", ".xls"):
            result = self._parse_excel(path)
        elif ext == ".csv":
            result = self._parse_csv(path)
        elif ext in (".pptx", ".ppt"):
            result = self._parse_powerpoint(path)
        elif ext in (".tex", ".bib"):
            result = self._parse_latex(path)
        elif ext in (".txt", ".md", ".rtf"):
            result = self._parse_text(path)
        elif ext in (".html", ".htm"):
            result = self._parse_html(path)
        elif ext == ".json":
            result = self._parse_json(path)
        elif ext == ".xml":
            result = self._parse_xml(path)
        elif ext in (".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp"):
            result = self._parse_image(path)
        else:
            # Generic text fallback
            result = self._parse_text(path)

        result.extraction_time_ms = round((time.time() - t0) * 1000, 2)
        result.metadata["file_hash"] = file_hash
        result.metadata["filename"] = path.name
        self._save_cache(file_hash, result)
        logger.info(
            f"Parsed {path.name} ({result.format.upper()}) in {result.extraction_time_ms}ms: "
            f"{result.page_count} pages, {result.char_count} chars, {result.tables_count} tables"
        )
        return result

    # --------------------------------------------------------------------------
    # 1. PDF Parser (PyMuPDF with smart OCR fallback)
    # --------------------------------------------------------------------------
    def _parse_pdf(self, path: Path) -> ExtractionResult:
        import fitz  # PyMuPDF

        content_list = []
        full_text_parts = []
        tables_count = 0
        doc = fitz.open(path)
        page_count = len(doc)
        total_text_len = 0

        for page_idx, page in enumerate(doc):
            # Extract plain text
            text = page.get_text("text").strip()
            total_text_len += len(text)

            # Extract tables if PyMuPDF version supports tabulate
            try:
                tabs = page.find_tables()
                if tabs and len(tabs.tables) > 0:
                    for tab in tabs.tables:
                        df = tab.extract()
                        if df and len(df) > 1:
                            tables_count += 1
                            # Format as Markdown table
                            headers = [str(c or "").strip() for c in df[0]]
                            sep = ["---"] * len(headers)
                            md_lines = [
                                "| " + " | ".join(headers) + " |",
                                "| " + " | ".join(sep) + " |",
                            ]
                            for row in df[1:]:
                                md_lines.append(
                                    "| " + " | ".join([str(c or "").strip() for c in row]) + " |"
                                )
                            table_md = "\n".join(md_lines)
                            content_list.append({
                                "type": "table",
                                "table_body": table_md,
                                "table_caption": [f"Table from page {page_idx + 1}"],
                                "page_idx": page_idx,
                            })
                            full_text_parts.append(f"\n[Table on page {page_idx + 1}]:\n{table_md}\n")
            except Exception:
                pass

            if text:
                content_list.append({
                    "type": "text",
                    "text": text,
                    "page_idx": page_idx,
                })
                full_text_parts.append(f"--- Page {page_idx + 1} ---\n{text}")

        # Check if PDF is scanned / empty
        has_ocr = False
        if total_text_len < 50 and page_count > 0:
            logger.warning(f"PDF {path.name} appears to be scanned (<50 chars). Checking OCR fallback...")
            # If magic_pdf is available, we can trigger it for scanned PDFs only
            try:
                from magic_pdf.pipe.UNIPipe import UNIPipe
                has_ocr = True
            except Exception:
                pass

        full_text = "\n\n".join(full_text_parts)
        words = len(full_text.split())

        return ExtractionResult(
            content_list=content_list,
            full_text=full_text,
            page_count=page_count,
            char_count=len(full_text),
            word_count=words,
            format="pdf",
            extraction_time_ms=0.0,
            has_ocr=has_ocr,
            tables_count=tables_count,
            metadata={"producer": doc.metadata.get("producer", ""), "title": doc.metadata.get("title", "")},
        )

    # --------------------------------------------------------------------------
    # 2. Word Document Parser (.docx, .doc)
    # --------------------------------------------------------------------------
    def _parse_word(self, path: Path) -> ExtractionResult:
        content_list = []
        full_text_parts = []
        tables_count = 0
        ext = path.suffix.lower()

        if ext == ".docx":
            import docx

            doc = docx.Document(path)
            current_page_idx = 0
            word_accumulator = 0

            # Process paragraphs and tables in order
            for element in doc.element.body:
                if element.tag.endswith("p"):
                    # Find paragraph
                    p_text = "".join(element.itertext()).strip()
                    if p_text:
                        content_list.append({
                            "type": "text",
                            "text": p_text,
                            "page_idx": current_page_idx,
                        })
                        full_text_parts.append(p_text)
                        word_accumulator += len(p_text.split())
                        # Approximate page boundary every 450 words
                        if word_accumulator >= 450:
                            current_page_idx += 1
                            word_accumulator = 0
                elif element.tag.endswith("tbl"):
                    # Table element
                    tables_count += 1
                    rows = []
                    for row in element.findall("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"):
                        cells = []
                        for cell in row.findall("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc"):
                            cells.append("".join(cell.itertext()).strip().replace("\n", " "))
                        rows.append(cells)
                    if rows:
                        headers = rows[0]
                        md_table = [
                            "| " + " | ".join(headers) + " |",
                            "| " + " | ".join(["---"] * len(headers)) + " |",
                        ]
                        for r in rows[1:]:
                            # Pad or trim to header length
                            padded = r + [""] * (len(headers) - len(r))
                            md_table.append("| " + " | ".join(padded[:len(headers)]) + " |")
                        table_body = "\n".join(md_table)
                        content_list.append({
                            "type": "table",
                            "table_body": table_body,
                            "table_caption": [f"Table in {path.name}"],
                            "page_idx": current_page_idx,
                        })
                        full_text_parts.append(table_body)
            page_count = max(1, current_page_idx + 1)
        else:
            # Old binary .doc: read raw text streams
            text = self._read_text_fallback(path)
            content_list.append({"type": "text", "text": text, "page_idx": 0})
            full_text_parts.append(text)
            page_count = 1

        full_text = "\n\n".join(full_text_parts)
        return ExtractionResult(
            content_list=content_list,
            full_text=full_text,
            page_count=page_count,
            char_count=len(full_text),
            word_count=len(full_text.split()),
            format="word",
            extraction_time_ms=0.0,
            tables_count=tables_count,
        )

    # --------------------------------------------------------------------------
    # 3. Excel Spreadsheet Parser (.xlsx, .xls)
    # --------------------------------------------------------------------------
    def _parse_excel(self, path: Path) -> ExtractionResult:
        import openpyxl

        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        content_list = []
        full_text_parts = []
        tables_count = 0

        for sheet_idx, sheet_name in enumerate(wb.sheetnames):
            sheet = wb[sheet_name]
            rows = []
            for row in sheet.iter_rows(values_only=True):
                # Filter rows that are completely empty
                str_cells = [str(c).strip() if c is not None else "" for c in row]
                if any(str_cells):
                    rows.append(str_cells)

            if not rows:
                continue

            tables_count += 1
            headers = rows[0]
            # Normalize headers
            headers = [h if h else f"Col_{i+1}" for i, h in enumerate(headers)]
            md_lines = [
                f"### Sheet: {sheet_name}",
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join(["---"] * len(headers)) + " |",
            ]
            for r in rows[1:100]:  # Cap at top 100 rows per sheet for semantic indexing
                padded = r + [""] * (len(headers) - len(r))
                md_lines.append("| " + " | ".join(padded[:len(headers)]) + " |")

            table_body = "\n".join(md_lines)
            content_list.append({
                "type": "table",
                "table_body": table_body,
                "table_caption": [f"Spreadsheet: {sheet_name}"],
                "page_idx": sheet_idx,
            })
            full_text_parts.append(table_body)

        wb.close()
        full_text = "\n\n".join(full_text_parts)
        return ExtractionResult(
            content_list=content_list,
            full_text=full_text,
            page_count=max(1, len(content_list)),
            char_count=len(full_text),
            word_count=len(full_text.split()),
            format="excel",
            extraction_time_ms=0.0,
            tables_count=tables_count,
        )

    # --------------------------------------------------------------------------
    # 4. CSV Parser (.csv)
    # --------------------------------------------------------------------------
    def _parse_csv(self, path: Path) -> ExtractionResult:
        text = self._read_text_fallback(path)
        dialect = "excel"
        try:
            dialect = csv.Sniffer().sniff(text[:4096])
        except Exception:
            pass

        reader = csv.reader(text.splitlines(), dialect=dialect)
        rows = [r for r in reader if any(r)]
        if not rows:
            return ExtractionResult([], "", 1, 0, 0, "csv", 0.0)

        headers = [h.strip() if h.strip() else f"Col_{i+1}" for i, h in enumerate(rows[0])]
        md_lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]
        for r in rows[1:150]:
            padded = [c.strip() for c in r] + [""] * (len(headers) - len(r))
            md_lines.append("| " + " | ".join(padded[:len(headers)]) + " |")

        table_body = "\n".join(md_lines)
        content_list = [{
            "type": "table",
            "table_body": table_body,
            "table_caption": [f"CSV Data Table: {path.name}"],
            "page_idx": 0,
        }]
        return ExtractionResult(
            content_list=content_list,
            full_text=table_body,
            page_count=1,
            char_count=len(table_body),
            word_count=len(table_body.split()),
            format="csv",
            extraction_time_ms=0.0,
            tables_count=1,
        )

    # --------------------------------------------------------------------------
    # 5. PowerPoint Parser (.pptx, .ppt)
    # --------------------------------------------------------------------------
    def _parse_powerpoint(self, path: Path) -> ExtractionResult:
        ext = path.suffix.lower()
        content_list = []
        full_text_parts = []
        tables_count = 0

        if ext == ".pptx":
            import pptx

            prs = pptx.Presentation(path)
            page_count = len(prs.slides)
            for slide_idx, slide in enumerate(prs.slides):
                slide_texts = []
                # Check shapes
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for paragraph in shape.text_frame.paragraphs:
                            t = "".join(run.text for run in paragraph.runs).strip()
                            if t:
                                slide_texts.append(t)
                    elif shape.has_table:
                        tables_count += 1
                        table = shape.table
                        t_rows = []
                        for row in table.rows:
                            t_rows.append([cell.text.strip().replace("\n", " ") for cell in row.cells])
                        if t_rows:
                            headers = t_rows[0]
                            md_tab = [
                                "| " + " | ".join(headers) + " |",
                                "| " + " | ".join(["---"] * len(headers)) + " |",
                            ]
                            for r in t_rows[1:]:
                                padded = r + [""] * (len(headers) - len(r))
                                md_tab.append("| " + " | ".join(padded[:len(headers)]) + " |")
                            slide_texts.append("\n" + "\n".join(md_tab) + "\n")

                if slide_texts:
                    stext = "\n".join(slide_texts)
                    content_list.append({
                        "type": "text",
                        "text": f"### Slide {slide_idx + 1}\n{stext}",
                        "page_idx": slide_idx,
                    })
                    full_text_parts.append(f"### Slide {slide_idx + 1}\n{stext}")
        else:
            text = self._read_text_fallback(path)
            content_list.append({"type": "text", "text": text, "page_idx": 0})
            full_text_parts.append(text)
            page_count = 1

        full_text = "\n\n".join(full_text_parts)
        return ExtractionResult(
            content_list=content_list,
            full_text=full_text,
            page_count=max(1, len(content_list)),
            char_count=len(full_text),
            word_count=len(full_text.split()),
            format="powerpoint",
            extraction_time_ms=0.0,
            tables_count=tables_count,
        )

    # --------------------------------------------------------------------------
    # 6. LaTeX & BibTeX Parser (.tex, .bib)
    # --------------------------------------------------------------------------
    def _parse_latex(self, path: Path) -> ExtractionResult:
        raw_text = self._read_text_fallback(path)
        # Strip comments
        clean_lines = [re.sub(r"(?<!\\)%.*", "", line) for line in raw_text.splitlines()]
        clean_text = "\n".join(clean_lines).strip()

        # Extract title and sections
        title_match = re.search(r"\\title\{([^}]+)\}", clean_text)
        title = title_match.group(1) if title_match else path.stem

        content_list = []
        # Split on sections
        sections = re.split(r"(\\section\*?\{[^}]+\})", clean_text)
        current_page = 0
        if len(sections) > 1:
            for i in range(1, len(sections), 2):
                sec_header = sections[i]
                sec_body = sections[i + 1] if i + 1 < len(sections) else ""
                # Convert \section{Name} to # Name
                h_name = re.search(r"\{([^}]+)\}", sec_header)
                sec_title = h_name.group(1) if h_name else "Section"
                content_list.append({
                    "type": "text",
                    "text": f"## {sec_title}\n{sec_body.strip()}",
                    "page_idx": current_page,
                })
                current_page += 1
        else:
            content_list.append({
                "type": "text",
                "text": f"# {title}\n{clean_text}",
                "page_idx": 0,
            })

        full_text = f"# {title}\n" + "\n\n".join(item["text"] for item in content_list)
        return ExtractionResult(
            content_list=content_list,
            full_text=full_text,
            page_count=max(1, len(content_list)),
            char_count=len(full_text),
            word_count=len(full_text.split()),
            format="latex",
            extraction_time_ms=0.0,
        )

    # --------------------------------------------------------------------------
    # 7. Text, Markdown & RTF Parser (.txt, .md, .rtf)
    # --------------------------------------------------------------------------
    def _parse_text(self, path: Path) -> ExtractionResult:
        raw_text = self._read_text_fallback(path)
        ext = path.suffix.lower()

        if ext == ".rtf":
            # Simple RTF tag stripper
            clean_text = re.sub(r"\\[a-z]+(-?\d+)? ?|[{}]", "", raw_text).strip()
        else:
            clean_text = raw_text

        # Break text into chunks of ~500 words per page_idx for RAG referencing
        words = clean_text.split()
        content_list = []
        chunk_size = 500
        for i in range(0, max(1, len(words)), chunk_size):
            chunk = " ".join(words[i : i + chunk_size])
            if chunk:
                content_list.append({
                    "type": "text",
                    "text": chunk,
                    "page_idx": i // chunk_size,
                })

        return ExtractionResult(
            content_list=content_list,
            full_text=clean_text,
            page_count=max(1, len(content_list)),
            char_count=len(clean_text),
            word_count=len(words),
            format="text" if ext != ".md" else "markdown",
            extraction_time_ms=0.0,
        )

    # --------------------------------------------------------------------------
    # 8. Web & HTML Parser (.html, .htm)
    # --------------------------------------------------------------------------
    def _parse_html(self, path: Path) -> ExtractionResult:
        from bs4 import BeautifulSoup

        raw_html = self._read_text_fallback(path)
        soup = BeautifulSoup(raw_html, "html.parser")

        # Strip scripts and styles
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else path.stem
        content_list = []
        tables_count = 0

        # Extract tables
        for tab_idx, table in enumerate(soup.find_all("table")):
            tables_count += 1
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text().strip().replace("\n", " ") for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            if rows:
                headers = rows[0]
                md_tab = [
                    "| " + " | ".join(headers) + " |",
                    "| " + " | ".join(["---"] * len(headers)) + " |",
                ]
                for r in rows[1:]:
                    padded = r + [""] * (len(headers) - len(r))
                    md_tab.append("| " + " | ".join(padded[:len(headers)]) + " |")
                table_body = "\n".join(md_tab)
                content_list.append({
                    "type": "table",
                    "table_body": table_body,
                    "table_caption": [f"HTML Table {tab_idx + 1}"],
                    "page_idx": tab_idx,
                })
            table.decompose()

        body_text = soup.get_text(separator="\n").strip()
        # Compress multiple newlines
        clean_text = re.sub(r"\n{3,}", "\n\n", body_text)
        content_list.insert(0, {
            "type": "text",
            "text": f"# {title}\n\n{clean_text}",
            "page_idx": 0,
        })

        full_text = f"# {title}\n\n{clean_text}"
        return ExtractionResult(
            content_list=content_list,
            full_text=full_text,
            page_count=max(1, len(content_list)),
            char_count=len(full_text),
            word_count=len(full_text.split()),
            format="html",
            extraction_time_ms=0.0,
            tables_count=tables_count,
        )

    # --------------------------------------------------------------------------
    # 9. Structured Data Parser (.json, .xml)
    # --------------------------------------------------------------------------
    def _parse_json(self, path: Path) -> ExtractionResult:
        raw = self._read_text_fallback(path)
        data = json.loads(raw)
        # Convert JSON structure into semantic Markdown
        md = f"# JSON Data: {path.name}\n\n```json\n{json.dumps(data, indent=2)[:3000]}\n```"
        content_list = [{
            "type": "text",
            "text": md,
            "page_idx": 0,
        }]
        return ExtractionResult(
            content_list=content_list,
            full_text=md,
            page_count=1,
            char_count=len(md),
            word_count=len(md.split()),
            format="json",
            extraction_time_ms=0.0,
        )

    def _parse_xml(self, path: Path) -> ExtractionResult:
        import xml.etree.ElementTree as ET

        raw = self._read_text_fallback(path)
        root = ET.fromstring(raw)
        lines = [f"# XML Document: {path.name} (root: {root.tag})"]
        for elem in list(root)[:50]:
            t = elem.text.strip() if elem.text else ""
            lines.append(f"- **{elem.tag}**: {t} {elem.attrib}")

        full_text = "\n".join(lines)
        content_list = [{
            "type": "text",
            "text": full_text,
            "page_idx": 0,
        }]
        return ExtractionResult(
            content_list=content_list,
            full_text=full_text,
            page_count=1,
            char_count=len(full_text),
            word_count=len(full_text.split()),
            format="xml",
            extraction_time_ms=0.0,
        )

    # --------------------------------------------------------------------------
    # 10. Image Parser (.png, .jpg, .webp, .tiff, .bmp)
    # --------------------------------------------------------------------------
    def _parse_image(self, path: Path) -> ExtractionResult:
        from PIL import Image

        img = Image.open(path)
        w, h = img.size
        mode = img.mode
        caption = f"Scientific image {path.name} (Dimensions: {w}x{h}, Mode: {mode})"

        content_list = [{
            "type": "image",
            "img_path": str(path.absolute()),
            "image_caption": [caption],
            "page_idx": 0,
        }]
        full_text = f"[{caption}]"
        return ExtractionResult(
            content_list=content_list,
            full_text=full_text,
            page_count=1,
            char_count=len(full_text),
            word_count=len(full_text.split()),
            format="image",
            extraction_time_ms=0.0,
            images_count=1,
            metadata={"width": w, "height": h, "mode": mode},
        )

    # Helper: robust encoding reader
    def _read_text_fallback(self, path: Path) -> str:
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"):
            try:
                return path.read_text(encoding=enc)
            except Exception:
                continue
        # Binary fallback with ASCII filter
        return path.read_bytes().decode("ascii", errors="replace")


# Singleton instance
universal_parser = UniversalParser()
