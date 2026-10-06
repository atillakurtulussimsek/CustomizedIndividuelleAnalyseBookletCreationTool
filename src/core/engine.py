"""
Batch engine — orchestrates parallel processing of all students.

Uses ProcessPoolExecutor for CPU-bound PDF operations.
Each student is an independent unit of work — no shared mutable state.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from src.core.pipeline import process_student
from src.models.config import EngineConfig
from src.models.records import (
    BatchReport,
    ProcessingStatus,
    StudentRecord,
)

logger = logging.getLogger("booklet_engine.engine")


def _process_wrapper(args: tuple) -> dict:
    """Wrapper for process pool — unpacks args and returns serializable dict.

    ProcessPoolExecutor requires picklable arguments and returns.
    We serialize StudentRecord and EngineConfig, process, then
    return a dict that the main process converts back to ProcessingResult.

    Note: Logging within child processes writes to file handler only
    (Rich console handler is not fork-safe, but file handler is).
    """
    student, config = args
    result = process_student(student, config)

    # Convert to dict for cross-process serialization
    return {
        "student_filename": result.student.safe_filename,
        "student_name": result.student.safe_name,
        "student_row": result.student.row_index,
        "status": result.status.value,
        "output_path": str(result.output_path) if result.output_path else None,
        "content_page_count": result.content_page_count,
        "blank_pages_added": result.blank_pages_added,
        "final_page_count": result.final_page_count,
        "error_message": result.error_message,
        "processing_time_ms": result.processing_time_ms,
        "details": result.details,
    }


def _dict_to_result(d: dict) -> "ProcessingResult":
    """Convert serialized dict back to ProcessingResult."""
    from pathlib import Path
    from src.models.records import ProcessingResult

    student = StudentRecord(
        filename=d["student_filename"],
        student_name=d["student_name"],
        row_index=d["student_row"],
    )
    return ProcessingResult(
        student=student,
        status=ProcessingStatus(d["status"]),
        output_path=Path(d["output_path"]) if d["output_path"] else None,
        content_page_count=d["content_page_count"],
        blank_pages_added=d["blank_pages_added"],
        final_page_count=d["final_page_count"],
        error_message=d["error_message"],
        processing_time_ms=d["processing_time_ms"],
        details=d["details"],
    )


def run_batch(
    students: list[StudentRecord],
    config: EngineConfig,
    max_workers: Optional[int] = None,
) -> BatchReport:
    """Process all students with parallel execution and progress tracking.

    Architecture:
        - Main process: progress bar, result collection, reporting.
        - Worker processes: independent PDF processing per student.
        - No shared state between workers.
        - Each worker opens/closes PDFs independently.

    Scaling Strategy (500 → 5000+ PDFs):
        - ProcessPoolExecutor scales linearly with CPU cores.
        - Each worker uses ~50-100MB peak (PyMuPDF + pikepdf + overlay).
        - 4 workers × 100MB = 400MB — well within server limits.
        - For 5000+ PDFs:
            a) Increase max_workers to CPU core count.
            b) Use chunked directory scanning instead of full listing.
            c) Optionally distribute across machines with task queue
               (Redis/Celery) — each machine runs this engine.
            d) Monitor with Prometheus metrics from the report CSV.

    Args:
        students: List of student records to process.
        config: Engine configuration.
        max_workers: Override for parallel workers (default: from config).

    Returns:
        BatchReport with aggregate metrics and per-student results.
    """
    workers = max_workers or config.processing.max_workers
    report = BatchReport()
    start_time = time.perf_counter()

    logger.info(
        f"Starting batch: {len(students)} students, {workers} workers"
    )

    # Ensure output directory exists
    config.output_path.mkdir(parents=True, exist_ok=True)

    # Build work items
    work_items = [(student, config) for student in students]

    # Progress bar
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )

    with progress:
        task = progress.add_task("Processing booklets", total=len(students))

        if workers == 1:
            # Sequential mode — easier to debug
            for student, cfg in work_items:
                result_dict = _process_wrapper((student, cfg))
                result = _dict_to_result(result_dict)
                report.add(result)
                progress.advance(task)

                if result.status == ProcessingStatus.ERROR:
                    progress.console.print(
                        f"  [red]✗[/red] {student.safe_filename}: "
                        f"{result.error_message}"
                    )
        else:
            # Parallel mode
            with ProcessPoolExecutor(max_workers=workers) as executor:
                future_map = {
                    executor.submit(_process_wrapper, item): item[0]
                    for item in work_items
                }

                for future in as_completed(future_map):
                    student = future_map[future]
                    try:
                        result_dict = future.result()
                        result = _dict_to_result(result_dict)
                    except Exception as e:
                        result = ProcessingResult(
                            student=student,
                            status=ProcessingStatus.ERROR,
                            error_message=f"Worker crashed: {e}",
                        )
                        logger.exception(
                            f"Worker crash for {student.safe_filename}"
                        )

                    report.add(result)
                    progress.advance(task)

                    if result.status == ProcessingStatus.ERROR:
                        progress.console.print(
                            f"  [red]✗[/red] {student.safe_filename}: "
                            f"{result.error_message}"
                        )

    report.total_time_seconds = time.perf_counter() - start_time

    logger.info(
        f"Batch complete: {report.success}/{report.total} succeeded, "
        f"{report.errors} errors, {report.skipped} skipped "
        f"in {report.total_time_seconds:.2f}s"
    )

    return report
