"""
Configuration management with Pydantic validation.

Loads config.json and provides typed, validated configuration objects
used across all engine components.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class NameExtractionConfig(BaseModel):
    """Controls how the student name is read from the analysis PDF.

    The analysis report has a header table on the first page:

        Ad Soyad | Numara | Sınıf | Alan | Dip. Not
        SİMAY DALGIÇ | 173 | 12-TM1 | EA | 84,01

    We locate the label (``label_text``) and read the words on the row
    directly beneath it, restricted to the label's column.

    page_index:        0-based page that holds the table.
    label_text:        Column header above the student name.
    row_gap_ratio:     Max vertical distance (in label heights) between the
                       label's bottom edge and the value row's top edge.
    column_margin:     Extra points added on both sides of the column span
                       when the neighbouring headers are not found.
    """
    page_index: int = Field(default=0, ge=0)
    label_text: str = "Ad Soyad"
    row_gap_ratio: float = Field(default=1.5, gt=0.0)
    column_margin: float = Field(default=12.0, ge=0.0)


class TemplateConfig(BaseModel):
    """Controls front template marker replacement.

    marker_text: the exact string in the template PDF to locate.
    fallback_x / fallback_y: used when marker is not found in text layer.
    text_align: 'center' to center on page, 'left' for left-aligned.
    """
    marker_text: str = "{{student.name}}"
    fallback_x: float = 297.75
    fallback_y: float = 340.0
    font_name: str = "DejaVuSans-Bold"
    font_size: float = 26.0
    font_color_r: float = Field(default=0.10, ge=0.0, le=1.0)
    font_color_g: float = Field(default=0.36, ge=0.0, le=1.0)
    font_color_b: float = Field(default=0.60, ge=0.0, le=1.0)
    text_align: str = Field(default="center", pattern=r"^(center|left)$")


class ProcessingConfig(BaseModel):
    """Controls parallelism and booklet constraints."""
    max_workers: int = Field(default=4, ge=1, le=32)
    booklet_page_multiple: int = Field(default=4, ge=1)
    stream_buffer_size_mb: int = Field(default=64, ge=8)
    delete_source_pdf: bool = False


class EngineConfig(BaseModel):
    """Root configuration model."""
    input_dir: str = "input_pdfs"
    output_dir: str = "output_pdfs"
    log_dir: str = "logs"
    font_dir: str = "fonts"
    front_template_filename: str = "front.pdf"
    back_cover_filename: str = "back.pdf"

    name_extraction: NameExtractionConfig = NameExtractionConfig()
    template: TemplateConfig = TemplateConfig()
    processing: ProcessingConfig = ProcessingConfig()

    # Resolved absolute paths — populated after load
    base_path: Optional[Path] = None

    @property
    def input_path(self) -> Path:
        return (self.base_path or Path(".")) / self.input_dir

    @property
    def output_path(self) -> Path:
        return (self.base_path or Path(".")) / self.output_dir

    @property
    def log_path(self) -> Path:
        return (self.base_path or Path(".")) / self.log_dir

    @property
    def font_path(self) -> Path:
        return (self.base_path or Path(".")) / self.font_dir

    @property
    def front_template_path(self) -> Path:
        return self.input_path / self.front_template_filename

    @property
    def back_cover_path(self) -> Path:
        return self.input_path / self.back_cover_filename


def load_config(config_path: str | Path) -> EngineConfig:
    """Load and validate configuration from JSON file.

    Raises:
        FileNotFoundError: If config file does not exist.
        pydantic.ValidationError: If config values are invalid.
    """
    config_path = Path(config_path).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    cfg = EngineConfig(**raw)
    cfg.base_path = config_path.parent
    return cfg
