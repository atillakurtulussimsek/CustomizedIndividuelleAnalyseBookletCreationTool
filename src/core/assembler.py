"""
Booklet assembler — merges personalized front cover, the full student
analysis PDF, blank padding pages, and the back cover into one PDF whose
page count is a multiple of 4 (saddle-stitch booklet printing).

Page order:
    [front cover] + [all student pages] + [blank × N] + [back cover]

Blank page computation:
    future_total = front_pages + student_pages + back_pages
    blank_needed = (multiple - future_total % multiple) % multiple
    Blank pages are inserted BEFORE the back cover so the back cover
    always lands on the last page.

pikepdf passes page object references between documents rather than
copying content streams, so memory stays low even for large batches.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import pikepdf

from src.models.config import EngineConfig

logger = logging.getLogger("booklet_engine.assembler")


def _create_blank_page_pdf(width: float, height: float) -> bytes:
    """Create a minimal 1-page PDF with the given dimensions (points)."""
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(width, height))
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def assemble_booklet(
    student_pdf_path: Path,
    front_template_bytes: bytes,
    config: EngineConfig,
    output_path: Path,
) -> tuple[int, int, int]:
    """Assemble the final booklet PDF for one student.

    Returns:
        Tuple of (student_page_count, blank_pages_added, final_page_count).

    Raises:
        pikepdf.PdfError: If a source PDF is corrupt.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_pdf = pikepdf.Pdf.new()
    front_pdf = pikepdf.open(io.BytesIO(front_template_bytes))
    student_pdf = pikepdf.open(str(student_pdf_path))
    back_pdf = pikepdf.open(str(config.back_cover_path))

    try:
        # --- Step 1: Front cover ---
        for page in front_pdf.pages:
            output_pdf.pages.append(page)
        logger.debug(f"Added {len(front_pdf.pages)} front cover page(s)")

        # --- Step 2: All student pages, untouched ---
        for page in student_pdf.pages:
            output_pdf.pages.append(page)
        student_count = len(student_pdf.pages)
        logger.debug(f"Added {student_count} student page(s)")

        # --- Step 3: Blank pages needed ---
        back_count = len(back_pdf.pages)
        future_total = len(output_pdf.pages) + back_count
        multiple = config.processing.booklet_page_multiple
        blank_needed = (multiple - future_total % multiple) % multiple

        logger.debug(
            f"Pages so far: {len(output_pdf.pages)}, back cover: {back_count}, "
            f"future total: {future_total}, blanks needed: {blank_needed}"
        )

        # --- Step 4: Insert blank pages (sized like the last content page) ---
        if blank_needed > 0:
            last_page = output_pdf.pages[-1]
            media_box = last_page.get("/MediaBox", pikepdf.Array([0, 0, 595, 842]))
            page_w = float(media_box[2]) - float(media_box[0])
            page_h = float(media_box[3]) - float(media_box[1])

            blank_pdf = pikepdf.open(io.BytesIO(_create_blank_page_pdf(page_w, page_h)))
            for _ in range(blank_needed):
                output_pdf.pages.append(blank_pdf.pages[0])
            logger.debug(f"Inserted {blank_needed} blank page(s)")

        # --- Step 5: Back cover ---
        for page in back_pdf.pages:
            output_pdf.pages.append(page)

        # --- Step 6: Validate and save ---
        final_count = len(output_pdf.pages)
        assert final_count % multiple == 0, (
            f"Final page count {final_count} is not divisible by {multiple}!"
        )

        output_pdf.save(
            str(output_path),
            linearize=True,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )

        logger.info(
            f"Saved booklet: {output_path.name} "
            f"({final_count} pages, {blank_needed} blanks added)"
        )
        return student_count, blank_needed, final_count

    finally:
        front_pdf.close()
        student_pdf.close()
        back_pdf.close()
