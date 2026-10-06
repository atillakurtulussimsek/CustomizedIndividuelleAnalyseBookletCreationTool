"""
Structured logging with Rich console + rotating file handler.

Provides per-student contextual logging and a final processing report.
"""

from __future__ import annotations

import csv
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from src.models.records import BatchReport, ProcessingResult, ProcessingStatus

_console = Console(stderr=True)


def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    """Configure dual-output logging: Rich console + rotating file.

    Args:
        log_dir: Directory for log files.
        verbose: If True, set console level to DEBUG.

    Returns:
        Root logger configured for the engine.
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"booklet_engine_{timestamp}.log"

    logger = logging.getLogger("booklet_engine")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # File handler — always DEBUG, full detail
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    # Console handler — Rich
    console_level = logging.DEBUG if verbose else logging.INFO
    rich_handler = RichHandler(
        console=_console,
        show_time=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
    )
    rich_handler.setLevel(console_level)
    logger.addHandler(rich_handler)

    logger.info(f"Log file: {log_file}")
    return logger


def print_report(report: BatchReport) -> None:
    """Print a summary table to console using Rich."""
    table = Table(title="Analyse Booklet Engine — Processing Report", show_lines=True)
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", justify="right")

    table.add_row("Total Students", str(report.total))
    table.add_row("Success", f"[green]{report.success}[/green]")
    table.add_row("Skipped", f"[yellow]{report.skipped}[/yellow]")
    table.add_row("Errors", f"[red]{report.errors}[/red]")
    table.add_row("Total Time", f"{report.total_time_seconds:.2f}s")

    if report.total > 0:
        avg = (report.total_time_seconds / report.total) * 1000
        table.add_row("Avg per PDF", f"{avg:.0f}ms")

    _console.print(table)

    # Error detail
    errors = [r for r in report.results if r.status == ProcessingStatus.ERROR]
    if errors:
        _console.print("\n[bold red]Error Details:[/bold red]")
        for r in errors:
            _console.print(
                f"  • {r.student.safe_filename} ({r.student.safe_name}): "
                f"{r.error_message}"
            )


def write_report_csv(report: BatchReport, output_path: Path) -> Path:
    """Write detailed processing report as CSV.

    Args:
        report: Completed batch report.
        output_path: Directory for the report file.

    Returns:
        Path to written CSV file.
    """
    output_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_path / f"report_{timestamp}.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "filename", "student_name", "status", "content_page_count",
            "blank_pages_added", "final_page_count", "processing_time_ms",
            "error_message",
        ])
        for r in report.results:
            writer.writerow([
                r.student.safe_filename,
                r.student.safe_name,
                r.status.value,
                r.content_page_count,
                r.blank_pages_added,
                r.final_page_count,
                f"{r.processing_time_ms:.1f}",
                r.error_message or "",
            ])

    return csv_path
