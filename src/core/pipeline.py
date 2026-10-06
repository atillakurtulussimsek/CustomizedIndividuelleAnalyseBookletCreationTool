"""
Pipeline orchestrator — processes a single student PDF end-to-end.

This is the unit of parallelism: each student is processed by one call
to ``process_student()``, which may run in a separate process.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pymupdf as fitz

from src.core.assembler import assemble_booklet
from src.core.template_processor import prepare_front_template
from src.models.config import EngineConfig
from src.models.records import ProcessingResult, ProcessingStatus, StudentRecord

logger = logging.getLogger("booklet_engine.pipeline")


def validate_pdf(pdf_path: Path) -> tuple[bool, str]:
    """Quick corruption check by opening the file and reading page count."""
    try:
        doc = fitz.open(str(pdf_path))
        page_count = doc.page_count
        doc.close()
        if page_count == 0:
            return False, "PDF has 0 pages"
        return True, f"Valid PDF with {page_count} pages"
    except Exception as e:
        return False, f"Corrupt or unreadable PDF: {e}"


def _unique_output_path(directory: Path, filename: str) -> Path:
    """Avoid overwriting when two students share the same name."""
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, suffix = Path(filename).stem, Path(filename).suffix
    n = 2
    while True:
        candidate = directory / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def process_student(student: StudentRecord, config: EngineConfig) -> ProcessingResult:
    """Full processing pipeline for one student.

    Steps:
        1. Validate the input PDF.
        2. Personalize the front cover with the student name.
        3. Assemble front + content + blanks + back into a booklet.
        4. Optionally delete the source PDF.

    All exceptions are captured into the result — one failing student
    never crashes the batch.
    """
    start_time = time.perf_counter()
    result = ProcessingResult(student=student, status=ProcessingStatus.ERROR)

    try:
        pdf_path = config.input_path / student.safe_filename
        if not pdf_path.exists():
            result.status = ProcessingStatus.SKIPPED
            result.error_message = f"Input PDF not found: {pdf_path}"
            result.details.append(result.error_message)
            logger.warning(result.error_message)
            return result

        is_valid, msg = validate_pdf(pdf_path)
        if not is_valid:
            result.error_message = f"Invalid PDF: {msg}"
            result.details.append(result.error_message)
            logger.error(result.error_message)
            return result

        front_bytes = prepare_front_template(
            template_path=config.front_template_path,
            student_name=student.safe_name,
            config=config.template,
            font_dir=config.font_path,
        )

        config.output_path.mkdir(parents=True, exist_ok=True)
        output_path = _unique_output_path(config.output_path, student.output_filename)

        content_count, blank_added, final_count = assemble_booklet(
            student_pdf_path=pdf_path,
            front_template_bytes=front_bytes,
            config=config,
            output_path=output_path,
        )

        result.status = ProcessingStatus.SUCCESS
        result.output_path = output_path
        result.content_page_count = content_count
        result.blank_pages_added = blank_added
        result.final_page_count = final_count

        logger.info(
            f"[OK] {student.safe_filename} → {output_path.name} ({final_count} pages)"
        )

        if config.processing.delete_source_pdf:
            try:
                pdf_path.unlink()
                result.details.append(f"Input PDF deleted: {pdf_path.name}")
            except OSError as e:
                logger.warning(f"Could not delete input PDF {pdf_path.name}: {e}")
                result.details.append(f"Warning: could not delete input PDF: {e}")

    except Exception as e:
        result.status = ProcessingStatus.ERROR
        result.error_message = f"{type(e).__name__}: {e}"
        result.details.append(result.error_message)
        logger.exception(f"[FAIL] {student.safe_filename}: {e}")

    finally:
        result.processing_time_ms = (time.perf_counter() - start_time) * 1000

    return result
