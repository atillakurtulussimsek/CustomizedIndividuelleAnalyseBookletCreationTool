"""
Test fixtures and sample data generators.

Creates minimal but valid PDFs that mimic the YKS analysis report layout
(header table with "Ad Soyad | Numara | Sınıf | Alan | Dip. Not") so the
full pipeline can be tested without real student data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pymupdf as fitz  # PyMuPDF (modern import name)

# Locate a TrueType font that supports Turkish characters (ı, ğ, ş, İ, ...)
_TURKISH_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _find_turkish_font() -> Optional[str]:
    for p in _TURKISH_FONT_PATHS:
        if Path(p).exists():
            return p
    return None


_TURKISH_FONT = _find_turkish_font()


def _font_kwargs(fontsize: float) -> dict:
    kwargs = {"fontsize": fontsize}
    if _TURKISH_FONT:
        kwargs["fontfile"] = _TURKISH_FONT
        kwargs["fontname"] = "trfont"
    return kwargs


# Header table geometry (approximates the real report: labels row at
# y≈93–103, values row at y≈105–115, columns centred at these x values)
_COLUMNS = [
    ("Ad Soyad", 245),
    ("Numara", 335),
    ("Sınıf", 400),
    ("Alan", 452),
    ("Dip. Not", 507),
]
_LABEL_Y = 92
_VALUE_Y = 105
_ROW_H = 12


def _insert_centered(page: fitz.Page, cx: float, y: float, text: str, fontsize: float = 8) -> None:
    rect = fitz.Rect(cx - 60, y, cx + 60, y + _ROW_H)
    page.insert_textbox(rect, text, align=fitz.TEXT_ALIGN_CENTER, **_font_kwargs(fontsize))


def create_sample_student_pdf(
    output_path: Path,
    student_name: str,
    num_pages: int = 10,
    number: str = "173",
    class_name: str = "12-TM1",
    area: str = "EA",
    grade: str = "84,01",
    include_header_table: bool = True,
) -> None:
    """Generate a test analysis PDF with the header table on page 1."""
    doc = fitz.open()

    for page_idx in range(num_pages):
        page = doc.new_page(width=595, height=842)  # A4

        page.insert_textbox(
            fitz.Rect(50, 40, 545, 60),
            "YENİ NESİL EĞİTİM KURUMLARI",
            align=fitz.TEXT_ALIGN_CENTER,
            **_font_kwargs(12),
        )

        if page_idx == 0 and include_header_table:
            page.insert_textbox(
                fitz.Rect(50, 62, 545, 80),
                "YKS ANALİZİ - 01.09.2026",
                align=fitz.TEXT_ALIGN_CENTER,
                **_font_kwargs(10),
            )
            values = [student_name, number, class_name, area, grade]
            for (label, cx), value in zip(_COLUMNS, values):
                _insert_centered(page, cx, _LABEL_Y, label)
                _insert_centered(page, cx, _VALUE_Y, value)

        page.insert_textbox(
            fitz.Rect(50, 140, 545, 700),
            f"Analysis content for page {page_idx + 1}.\n" * 10,
            **_font_kwargs(10),
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()


def create_front_template(output_path: Path, with_marker: bool = True) -> None:
    """Generate a front cover PDF with the {{student.name}} marker."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    page.insert_textbox(
        fitz.Rect(50, 100, 545, 200),
        "YKS Analiz Kitapçığı",
        align=fitz.TEXT_ALIGN_CENTER,
        **_font_kwargs(28),
    )
    page.insert_textbox(
        fitz.Rect(50, 220, 545, 280),
        "2025-2026",
        align=fitz.TEXT_ALIGN_CENTER,
        **_font_kwargs(16),
    )

    if with_marker:
        page.insert_textbox(
            fitz.Rect(150, 350, 450, 390),
            "{{student.name}}",
            align=fitz.TEXT_ALIGN_CENTER,
            **_font_kwargs(14),
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()


def create_back_cover(output_path: Path) -> None:
    """Generate a simple back cover PDF (1 page)."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_textbox(
        fitz.Rect(50, 350, 545, 450),
        "Arka Kapak\n© 2026",
        align=fitz.TEXT_ALIGN_CENTER,
        **_font_kwargs(14),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()


def setup_test_environment(base_dir: Path, num_students: int = 3) -> list[tuple[str, str]]:
    """Create a complete test environment with all required files.

    Returns:
        List of (filename, student_name) tuples created.
    """
    input_dir = base_dir / "input_pdfs"
    input_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "output_pdfs").mkdir(parents=True, exist_ok=True)
    (base_dir / "logs").mkdir(parents=True, exist_ok=True)

    test_students = [
        ("student_001.pdf", "AHMET YILMAZ"),
        ("student_002.pdf", "ELİF ÖZTÜRK"),
        ("student_003.pdf", "MEHMET ÇELİK"),
        ("student_004.pdf", "AYŞE ŞAHİN"),
        ("student_005.pdf", "İBRAHİM GÜNEŞ"),
    ][:num_students]

    for idx, (filename, name) in enumerate(test_students):
        # Vary page counts so mod-4 padding paths are exercised
        create_sample_student_pdf(input_dir / filename, name, num_pages=8 + idx)

    create_front_template(input_dir / "front.pdf")
    create_back_cover(input_dir / "back.pdf")

    return test_students
