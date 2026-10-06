"""
Setup script to generate sample test data in input_pdfs/.

Usage:
    python -m tests.generate_test_data
    python -m tests.generate_test_data --count 10
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.fixtures import setup_test_environment


@click.command()
@click.option("--count", "-n", default=5, help="Number of test students to generate")
@click.option("--output", "-o", default=".", help="Base directory")
def main(count: int, output: str):
    """Generate test data for the booklet engine."""
    base = Path(output).resolve()
    students = setup_test_environment(base, num_students=count)

    click.echo(f"Generated {len(students)} test student(s) in {base / 'input_pdfs'}")
    for fn, name in students:
        click.echo(f"  • {fn} → {name}")

    click.echo(f"\nFront cover:    {base / 'input_pdfs' / 'front.pdf'}")
    click.echo(f"Back cover:     {base / 'input_pdfs' / 'back.pdf'}")


if __name__ == "__main__":
    main()
