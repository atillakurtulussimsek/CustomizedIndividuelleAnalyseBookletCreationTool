"""
Font management for Turkish UTF-8 text rendering.

Handles discovery and registration of TrueType fonts
for use by ReportLab in overlay generation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger("booklet_engine.fonts")

# Track registered fonts to avoid double-registration
_registered_fonts: set[str] = set()

# DejaVu Sans ships with most Linux distros and covers full Turkish charset.
# On Windows, we fall back to common system font paths.
_SEARCH_PATHS = [
    # Project-local
    Path("fonts"),
    # Linux
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/TTF"),
    Path("/usr/share/fonts/truetype"),
    # Windows
    Path("C:/Windows/Fonts"),
    # macOS
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
    # macOS ships Arial (full Turkish coverage) here, not in the dirs above
    Path("/System/Library/Fonts/Supplemental"),
    Path.home() / "Library/Fonts",
]

_FONT_CANDIDATES = {
    "DejaVuSans": [
        "DejaVuSans.ttf",
        "dejavu-sans/DejaVuSans.ttf",
        "dejavu/DejaVuSans.ttf",
        "arial.ttf",        # Windows fallback
        "Arial.ttf",
    ],
    "DejaVuSans-Bold": [
        "DejaVuSans-Bold.ttf",
        "dejavu-sans/DejaVuSans-Bold.ttf",
        "dejavu/DejaVuSans-Bold.ttf",
        "arialbd.ttf",      # Windows fallback
        "Arial Bold.ttf",
    ],
}


def find_font_file(font_name: str, extra_dir: Optional[Path] = None) -> Optional[Path]:
    """Locate a TTF file by scanning known paths.

    Args:
        font_name: Logical font name (e.g., 'DejaVuSans').
        extra_dir: Additional directory to search first.

    Returns:
        Path to TTF file, or None if not found.
    """
    candidates = _FONT_CANDIDATES.get(font_name, [f"{font_name}.ttf"])
    search_dirs = list(_SEARCH_PATHS)
    if extra_dir:
        search_dirs.insert(0, extra_dir)

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for candidate in candidates:
            font_path = search_dir / candidate
            if font_path.exists():
                logger.debug(f"Found font '{font_name}' at: {font_path}")
                return font_path

    return None


def register_font(font_name: str, font_dir: Optional[Path] = None) -> str:
    """Register a TrueType font with ReportLab's global registry.

    Args:
        font_name: Logical name to register under.
        font_dir: Project font directory to search first.

    Returns:
        The registered font name (for use in drawing calls).

    Raises:
        RuntimeError: If font file cannot be located.
    """
    if font_name in _registered_fonts:
        return font_name

    ttf_path = find_font_file(font_name, font_dir)
    if ttf_path is None:
        raise RuntimeError(
            f"Font '{font_name}' not found. "
            f"Place a TTF file in the 'fonts/' directory or install DejaVu Sans. "
            f"Searched: {[str(p) for p in _SEARCH_PATHS]}"
        )

    pdfmetrics.registerFont(TTFont(font_name, str(ttf_path)))
    _registered_fonts.add(font_name)
    logger.info(f"Registered font '{font_name}' from: {ttf_path}")
    return font_name
