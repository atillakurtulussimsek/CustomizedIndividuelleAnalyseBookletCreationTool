"""
Front template processing — anchor marker detection and name overlay.

Anchor Bounding Box Detection — How It Works Internally:
    1. Open front_template.pdf with PyMuPDF.
    2. Call page.search_for(marker_text) which returns a list of Rect objects.
       Internally, PyMuPDF iterates the page's text extraction structures
       (content streams → font glyph mappings → Unicode codepoints → positions).
       For each text span, it checks if the span text contains the search string.
       When found, it computes the bounding rectangle from the span's
       glyph origin, advance widths, and font ascent/descent metrics.
    3. The returned Rect gives us (x0, y0, x1, y1) in page coordinates.
    4. We use these exact coordinates to:
       a) Draw a white filled rectangle over the marker (covering it visually).
       b) Place the student name text at the same origin point.
    5. The overlay is generated as a separate single-page PDF using ReportLab,
       then merged onto the template page using pikepdf.
    6. This preserves the original template's text layer — the marker text
       remains searchable in the underlying layer while visually replaced.

    If search_for() returns empty (marker not in text layer), we fall back
    to configurable X,Y coordinates from config.

Font and Turkish Support:
    - ReportLab renders text to a PDF content stream using TrueType outlines.
    - DejaVu Sans covers all Turkish characters: ç, ğ, ı, ö, ş, ü, İ, Ş, etc.
    - The font is embedded as a subset in the overlay PDF.
    - UTF-8 encoding is maintained end-to-end (CSV → Python str → ReportLab).
"""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path
from typing import Optional

import pymupdf as fitz  # PyMuPDF (modern import name)
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from src.models.config import TemplateConfig
from src.utils.font_manager import register_font

logger = logging.getLogger("booklet_engine.template")


def _find_marker_rect(
    template_path: Path,
    marker_text: str,
) -> Optional[tuple[float, float, float, float, float, float]]:
    """Locate the marker text bounding box in the template PDF.

    Args:
        template_path: Path to front_template.pdf.
        marker_text: Exact text to search for (e.g., '{{student.name}}').

    Returns:
        Tuple of (x0, y0, x1, y1, page_width, page_height) in PyMuPDF
        coordinates, or None if marker not found.
    """
    doc = fitz.open(str(template_path))
    try:
        if doc.page_count == 0:
            logger.error("Front template has 0 pages")
            return None

        page = doc[0]
        rects = page.search_for(marker_text)

        if not rects:
            logger.warning(
                f"Marker '{marker_text}' not found in template text layer"
            )
            return None

        # Use first occurrence
        r = rects[0]
        pw = page.rect.width
        ph = page.rect.height
        logger.debug(
            f"Marker found at: ({r.x0:.1f}, {r.y0:.1f}, {r.x1:.1f}, {r.y1:.1f}) "
            f"on page {pw:.0f}x{ph:.0f}"
        )
        return (r.x0, r.y0, r.x1, r.y1, pw, ph)
    finally:
        doc.close()


def create_name_overlay(
    student_name: str,
    marker_rect: Optional[tuple[float, float, float, float, float, float]],
    config: TemplateConfig,
    font_dir: Optional[Path] = None,
) -> bytes:
    """Generate a single-page PDF overlay with the student name.

    The overlay is transparent everywhere except where the student name
    is drawn. A white rectangle covers the marker area first.

    Coordinate Conversion:
        PyMuPDF uses top-left origin (y increases downward).
        ReportLab uses bottom-left origin (y increases upward).
        Conversion: reportlab_y = page_height - pymupdf_y

    Args:
        student_name: Text to render.
        marker_rect: (x0, y0, x1, y1, page_w, page_h) from PyMuPDF, or None.
        config: Template configuration.
        font_dir: Directory to search for fonts.

    Returns:
        Raw PDF bytes of the overlay page.
    """
    font_name = register_font(config.font_name, font_dir)

    if marker_rect is not None:
        x0, y0, x1, y1, page_w, page_h = marker_rect
    else:
        # Fallback coordinates (already in ReportLab bottom-left system)
        page_w = 595.0  # A4 width in points
        page_h = 842.0  # A4 height in points
        x0 = config.fallback_x
        # Convert fallback_y to PyMuPDF system for uniform handling
        y0 = page_h - config.fallback_y
        x1 = x0 + 300  # generous width
        y1 = y0 + config.font_size + 4

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))

    # Convert PyMuPDF coords to ReportLab coords
    # PyMuPDF: y0 is distance from TOP
    # ReportLab: y is distance from BOTTOM
    rl_cover_y_bottom = page_h - y1  # bottom of cover rect
    rl_cover_y_top = page_h - y0    # top of cover rect
    cover_height = rl_cover_y_top - rl_cover_y_bottom

    # Draw white cover rectangle over marker zone
    c.setFillColorRGB(1, 1, 1)  # white
    c.setStrokeColorRGB(1, 1, 1)
    c.rect(
        x0 - 2,             # slight padding
        rl_cover_y_bottom - 2,
        (x1 - x0) + 4,
        cover_height + 4,
        fill=True,
        stroke=False,
    )

    # Draw student name
    c.setFillColorRGB(config.font_color_r, config.font_color_g, config.font_color_b)
    c.setFont(font_name, config.font_size)

    # Place text at the baseline of the original marker area
    # Baseline = bottom of cover rect + small offset for descenders
    text_y = rl_cover_y_bottom + (cover_height - config.font_size) / 2 + 1

    if config.text_align == "center":
        # Center the text horizontally on the page
        center_x = page_w / 2
        c.drawCentredString(center_x, text_y, student_name)
    else:
        c.drawString(x0, text_y, student_name)

    c.save()
    return buf.getvalue()


def prepare_front_template(
    template_path: Path,
    student_name: str,
    config: TemplateConfig,
    font_dir: Optional[Path] = None,
) -> bytes:
    """Create a personalized front template page.

    Pipeline:
        1. Detect marker bounding box in template.
        2. Generate name overlay PDF.
        3. Merge overlay onto template page using PyMuPDF.
        4. Return merged PDF as bytes.

    Args:
        template_path: Path to front_template.pdf.
        student_name: Student's full name.
        config: Template config.
        font_dir: Font directory.

    Returns:
        PDF bytes of the personalized front page(s).
    """
    marker_rect = _find_marker_rect(template_path, config.marker_text)

    if marker_rect is None:
        logger.warning(
            f"Using fallback coordinates ({config.fallback_x}, {config.fallback_y}) "
            f"for '{student_name}'"
        )

    overlay_bytes = create_name_overlay(student_name, marker_rect, config, font_dir)

    # Merge overlay onto template using PyMuPDF
    template_doc = fitz.open(str(template_path))
    overlay_doc = fitz.open(stream=overlay_bytes, filetype="pdf")

    try:
        # Apply overlay to first page of template
        template_page = template_doc[0]
        overlay_page = overlay_doc[0]

        # Insert overlay page content onto template page
        # show_pdf_page renders one PDF page onto another
        template_page.show_pdf_page(
            template_page.rect,
            overlay_doc,
            pno=0,
            overlay=True,  # render on top
        )

        # Save to bytes
        result_bytes = template_doc.tobytes(
            deflate=True,
            garbage=4,  # remove unused objects
        )
        return result_bytes

    finally:
        overlay_doc.close()
        template_doc.close()
