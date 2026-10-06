"""
Data models for processing results and student records.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class ProcessingStatus(Enum):
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


@dataclass
class StudentRecord:
    """One discovered student PDF with its extracted name."""
    filename: str
    student_name: str
    row_index: int  # 1-based discovery order for reporting

    @property
    def safe_filename(self) -> str:
        return self.filename.strip()

    @property
    def safe_name(self) -> str:
        return self.student_name.strip()

    @property
    def output_filename(self) -> str:
        """Output booklet filename derived from the student name.

        Keeps Turkish characters; strips characters that are illegal in
        filenames on Windows/macOS/Linux and collapses whitespace.
        """
        name = _UNSAFE_FILENAME_CHARS.sub("", self.safe_name)
        name = re.sub(r"\s+", " ", name).strip().rstrip(".")
        if not name:
            name = Path(self.safe_filename).stem
        return f"{name}.pdf"


@dataclass
class ProcessingResult:
    """Result of processing a single student PDF."""
    student: StudentRecord
    status: ProcessingStatus
    output_path: Optional[Path] = None
    content_page_count: int = 0
    blank_pages_added: int = 0
    final_page_count: int = 0
    error_message: Optional[str] = None
    processing_time_ms: float = 0.0
    details: list[str] = field(default_factory=list)


@dataclass
class BatchReport:
    """Aggregate report for entire processing run."""
    total: int = 0
    success: int = 0
    skipped: int = 0
    errors: int = 0
    results: list[ProcessingResult] = field(default_factory=list)
    total_time_seconds: float = 0.0

    def add(self, result: ProcessingResult) -> None:
        self.results.append(result)
        self.total += 1
        if result.status == ProcessingStatus.SUCCESS:
            self.success += 1
        elif result.status == ProcessingStatus.SKIPPED:
            self.skipped += 1
        else:
            self.errors += 1
