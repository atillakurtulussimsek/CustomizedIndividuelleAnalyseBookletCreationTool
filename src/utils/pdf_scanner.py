"""
PDF scanner — discovers student analysis PDFs and extracts names.

The analysis report ("YKS ANALİZİ") carries a header table on its first
page:

    Ad Soyad | Numara | Sınıf | Alan | Dip. Not
    SİMAY DALGIÇ | 173 | 12-TM1 | EA | 84,01

How name extraction works:
    1. Open the configured page with PyMuPDF.
    2. ``page.search_for(label_text)`` gives the bounding box of the
       "Ad Soyad" header cell.
    3. Determine the column's horizontal span: from the right edge of the
       header to its left (or the page edge) to the left edge of the header
       to its right (or the page edge). Both boundaries are taken as the
       midpoint between neighbouring headers so centred values are safe.
    4. Collect all words whose top edge lies just below the label (within
       ``row_gap_ratio`` × label height) and whose horizontal centre falls
       inside the column span. Sorted left-to-right, joined by a space,
       that is the student name.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pymupdf as fitz  # PyMuPDF (modern import name)

from src.models.config import EngineConfig, NameExtractionConfig
from src.models.records import StudentRecord

logger = logging.getLogger("booklet_engine.scanner")


def _words_on_same_row(words: list, label: fitz.Rect, tol: float = 2.0) -> list:
    """Words whose vertical span matches the label row (other headers)."""
    return [
        w for w in words
        if abs(w[1] - label.y0) <= tol and abs(w[3] - label.y1) <= tol
    ]


def _column_span(
    label: fitz.Rect,
    header_words: list,
    page_width: float,
    margin: float,
) -> tuple[float, float]:
    """Horizontal range that belongs to the label's column."""
    left_neighbours = [w[2] for w in header_words if w[2] <= label.x0 + 0.5]
    right_neighbours = [w[0] for w in header_words if w[0] >= label.x1 - 0.5]

    if left_neighbours:
        left = (max(left_neighbours) + label.x0) / 2
    else:
        left = max(0.0, label.x0 - margin - (label.x1 - label.x0))

    if right_neighbours:
        right = (label.x1 + min(right_neighbours)) / 2
    else:
        right = min(page_width, label.x1 + margin + (label.x1 - label.x0))

    return left, right


def extract_student_name(
    pdf_path: Path,
    config: NameExtractionConfig,
) -> Optional[str]:
    """Read the student name beneath the ``label_text`` header cell.

    Returns:
        Student name, or None if the label or value row is not found.
    """
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        logger.warning(f"{pdf_path.name}: cannot open PDF: {e}")
        return None

    try:
        if doc.page_count <= config.page_index:
            logger.warning(
                f"{pdf_path.name}: has {doc.page_count} page(s), "
                f"page index {config.page_index} not available"
            )
            return None

        page = doc[config.page_index]
        hits = page.search_for(config.label_text)
        if not hits:
            logger.warning(
                f"{pdf_path.name}: label '{config.label_text}' not found on page "
                f"{config.page_index + 1}"
            )
            return None

        label = hits[0]
        label_h = label.y1 - label.y0
        words = page.get_text("words")  # (x0, y0, x1, y1, text, block, line, word)

        # Exclude the label's own words when looking for neighbouring headers
        header_words = [
            w for w in _words_on_same_row(words, label)
            if not (w[0] >= label.x0 - 0.5 and w[2] <= label.x1 + 0.5)
        ]
        col_left, col_right = _column_span(
            label, header_words, page.rect.width, config.column_margin
        )

        row_top_min = label.y1 - 0.5
        row_top_max = label.y1 + label_h * config.row_gap_ratio

        candidates = [
            w for w in words
            if row_top_min <= w[1] <= row_top_max
            and col_left <= (w[0] + w[2]) / 2 <= col_right
        ]
        if not candidates:
            logger.warning(
                f"{pdf_path.name}: no value found beneath '{config.label_text}'"
            )
            return None

        # Keep only the first (topmost) row among candidates
        first_top = min(w[1] for w in candidates)
        row = [w for w in candidates if abs(w[1] - first_top) <= label_h * 0.5]
        row.sort(key=lambda w: w[0])

        name = " ".join(w[4] for w in row).strip()
        logger.debug(
            f"{pdf_path.name}: name '{name}' from column "
            f"[{col_left:.1f}, {col_right:.1f}] under '{config.label_text}'"
        )
        return name or None

    finally:
        doc.close()


def scan_student_pdfs(
    input_dir: Path,
    config: EngineConfig,
) -> list[StudentRecord]:
    """Discover all student PDFs in input directory and extract names.

    Excludes the front template and back cover files.
    """
    excluded = {
        config.front_template_filename.lower(),
        config.back_cover_filename.lower(),
    }

    pdf_files = sorted(
        f for f in input_dir.glob("*.pdf")
        if f.name.lower() not in excluded
    )

    if not pdf_files:
        logger.warning(f"No student PDFs found in {input_dir}")
        return []

    logger.info(f"Found {len(pdf_files)} PDF file(s) in {input_dir}")

    records: list[StudentRecord] = []
    for idx, pdf_path in enumerate(pdf_files, start=1):
        name = extract_student_name(pdf_path, config.name_extraction)
        if name:
            records.append(StudentRecord(
                filename=pdf_path.name,
                student_name=name,
                row_index=idx,
            ))
            logger.debug(f"  {pdf_path.name} → {name}")
        else:
            logger.warning(
                f"Could not extract student name from {pdf_path.name}, skipping"
            )

    logger.info(f"Extracted {len(records)} student record(s) from PDFs")
    return records
