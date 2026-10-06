"""
CLI entry point using Click.

Usage:
    python -m src.cli run --config config.json
    python -m src.cli run --config config.json --workers 8 --verbose
    python -m src.cli validate --config config.json
    python -m src.cli run --config config.json --single student1.pdf
"""

from __future__ import annotations

import sys

import click

from src.core.engine import run_batch
from src.models.config import load_config
from src.utils.logging import print_report, setup_logging, write_report_csv
from src.utils.pdf_scanner import scan_student_pdfs

VERSION = "1.0.0"


@click.group()
@click.version_option(version=VERSION, prog_name="analyse-booklet-engine")
def cli():
    """Analyse Booklet Engine — personalized YKS analysis booklets."""


@cli.command()
@click.option("--config", "-c", default="config.json", type=click.Path(exists=True),
              help="Path to config.json")
@click.option("--workers", "-w", default=None, type=int,
              help="Override number of parallel workers")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging to console")
@click.option("--single", "-s", default=None, type=str,
              help="Process only this filename (for testing)")
@click.option("--dry-run", is_flag=True, help="Validate inputs without processing")
def run(config: str, workers: int | None, verbose: bool, single: str | None, dry_run: bool):
    """Run the booklet processing pipeline."""
    cfg = load_config(config)
    logger = setup_logging(cfg.log_path, verbose=verbose)

    logger.info("=" * 60)
    logger.info(f"Analyse Booklet Engine v{VERSION} — Starting")
    logger.info("=" * 60)

    errors = _validate_inputs(cfg)
    if errors:
        for e in errors:
            logger.error(e)
        click.echo(f"Validation failed with {len(errors)} error(s). Aborting.")
        sys.exit(1)

    students = scan_student_pdfs(cfg.input_path, cfg)
    if not students:
        logger.error("No valid student PDFs found in input directory")
        sys.exit(1)

    if single:
        students = [s for s in students if s.safe_filename == single]
        if not students:
            logger.error(f"Student file '{single}' not found in input directory")
            sys.exit(1)
        logger.info(f"Single mode: processing only '{single}'")

    if dry_run:
        logger.info(f"Dry run: {len(students)} students would be processed")
        for s in students[:10]:
            logger.info(f"  • {s.safe_filename} → {s.safe_name} → {s.output_filename}")
        if len(students) > 10:
            logger.info(f"  ... and {len(students) - 10} more")
        return

    report = run_batch(students, cfg, max_workers=workers)

    print_report(report)
    csv_path = write_report_csv(report, cfg.log_path)
    logger.info(f"Report CSV: {csv_path}")

    if report.errors > 0:
        sys.exit(2)


@cli.command()
@click.option("--config", "-c", default="config.json", type=click.Path(exists=True),
              help="Path to config.json")
def validate(config: str):
    """Validate configuration and input files without processing."""
    cfg = load_config(config)
    setup_logging(cfg.log_path, verbose=True)

    errors = _validate_inputs(cfg)
    if errors:
        for e in errors:
            click.echo(f"  ✗ {e}", err=True)
        click.echo(f"\n{len(errors)} validation error(s) found.")
        sys.exit(1)

    students = scan_student_pdfs(cfg.input_path, cfg)
    click.echo(f"  ✓ Found {len(students)} student PDF(s) with extracted names")

    if not students:
        click.echo("  ✗ No student PDFs with extractable names found", err=True)
    else:
        for s in students[:10]:
            click.echo(f"    {s.safe_filename} → {s.safe_name}")
        if len(students) > 10:
            click.echo(f"    ... and {len(students) - 10} more")

    click.echo("\nValidation complete.")


def _validate_inputs(cfg) -> list[str]:
    """Check that required input files and directories exist."""
    errors = []
    if not cfg.input_path.exists():
        errors.append(f"Input directory not found: {cfg.input_path}")
    if not cfg.front_template_path.exists():
        errors.append(f"Front cover not found: {cfg.front_template_path}")
    if not cfg.back_cover_path.exists():
        errors.append(f"Back cover not found: {cfg.back_cover_path}")
    return errors


def main():
    cli()


if __name__ == "__main__":
    main()
