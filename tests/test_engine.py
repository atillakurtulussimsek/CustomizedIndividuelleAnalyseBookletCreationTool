"""
Integration tests for the Analyse Booklet Engine.

Covers name extraction from the header table, front cover marker
replacement, booklet assembly, and the mod-4 page count constraint.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pikepdf
import pymupdf as fitz
import pytest

from src.core.assembler import assemble_booklet
from src.core.engine import run_batch
from src.core.pipeline import process_student, validate_pdf
from src.core.template_processor import (
    _find_marker_rect,
    create_name_overlay,
    prepare_front_template,
)
from src.models.config import EngineConfig, NameExtractionConfig, TemplateConfig, load_config
from src.models.records import ProcessingStatus, StudentRecord
from src.utils.pdf_scanner import extract_student_name, scan_student_pdfs
from tests.fixtures import (
    create_back_cover,
    create_front_template,
    create_sample_student_pdf,
    setup_test_environment,
)


PROJECT_FONTS = Path(__file__).resolve().parent.parent / "fonts"


@pytest.fixture
def tmp_dir():
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def test_env(tmp_dir):
    students = setup_test_environment(tmp_dir, num_students=3)
    config_data = {
        "input_dir": "input_pdfs",
        "output_dir": "output_pdfs",
        "log_dir": "logs",
        "font_dir": str(PROJECT_FONTS),
        "front_template_filename": "front.pdf",
        "back_cover_filename": "back.pdf",
        "processing": {"max_workers": 1, "booklet_page_multiple": 4, "delete_source_pdf": False},
    }
    config_path = tmp_dir / "config.json"
    config_path.write_text(json.dumps(config_data), encoding="utf-8")
    return {"dir": tmp_dir, "config": load_config(config_path), "students": students}


class TestNameExtraction:
    def test_extracts_name_under_label(self, tmp_dir):
        pdf = tmp_dir / "s.pdf"
        create_sample_student_pdf(pdf, "SİMAY DALGIÇ")
        assert extract_student_name(pdf, NameExtractionConfig()) == "SİMAY DALGIÇ"

    def test_multi_word_name(self, tmp_dir):
        pdf = tmp_dir / "s.pdf"
        create_sample_student_pdf(pdf, "AYŞE NUR ŞAHİN")
        assert extract_student_name(pdf, NameExtractionConfig()) == "AYŞE NUR ŞAHİN"

    def test_does_not_leak_neighbour_columns(self, tmp_dir):
        pdf = tmp_dir / "s.pdf"
        create_sample_student_pdf(pdf, "ALİ CAN", number="999", class_name="12-A")
        name = extract_student_name(pdf, NameExtractionConfig())
        assert name == "ALİ CAN"
        assert "999" not in name and "12-A" not in name

    def test_missing_label_returns_none(self, tmp_dir):
        pdf = tmp_dir / "s.pdf"
        create_sample_student_pdf(pdf, "X Y", include_header_table=False)
        assert extract_student_name(pdf, NameExtractionConfig()) is None

    def test_real_sample_if_present(self):
        sample = Path.home() / "Downloads" / "f57608e5-6b8a-4382-ad26-5d03490c9c54.pdf"
        if not sample.exists():
            pytest.skip("real sample not available")
        assert extract_student_name(sample, NameExtractionConfig()) == "SİMAY DALGIÇ"


class TestValidation:
    def test_valid_pdf(self, tmp_dir):
        pdf = tmp_dir / "s.pdf"
        create_sample_student_pdf(pdf, "A B", num_pages=3)
        ok, _ = validate_pdf(pdf)
        assert ok

    def test_corrupt_pdf(self, tmp_dir):
        pdf = tmp_dir / "bad.pdf"
        pdf.write_bytes(b"not a pdf")
        ok, _ = validate_pdf(pdf)
        assert not ok


class TestTemplate:
    def test_marker_detection(self, tmp_dir):
        front = tmp_dir / "front.pdf"
        create_front_template(front)
        rect = _find_marker_rect(front, "{{student.name}}")
        assert rect is not None
        x0, y0, x1, y1, pw, ph = rect
        assert x1 > x0 and y1 > y0 and pw > 0 and ph > 0

    def test_marker_not_found(self, tmp_dir):
        front = tmp_dir / "front.pdf"
        create_front_template(front, with_marker=False)
        assert _find_marker_rect(front, "{{student.name}}") is None

    def test_overlay_generation(self):
        data = create_name_overlay("Test Öğrenci", None, TemplateConfig(), PROJECT_FONTS)
        assert data.startswith(b"%PDF")

    def test_full_template_processing(self, tmp_dir):
        front = tmp_dir / "front.pdf"
        create_front_template(front)
        out = prepare_front_template(front, "SİMAY DALGIÇ", TemplateConfig(), PROJECT_FONTS)
        doc = fitz.open(stream=out, filetype="pdf")
        assert doc.page_count == 1
        doc.close()


class TestAssembly:
    @pytest.mark.parametrize("num_pages", [7, 8, 9, 10, 11])
    def test_page_count_multiple_of_4(self, tmp_dir, num_pages):
        inp = tmp_dir / "input_pdfs"
        inp.mkdir()
        student_pdf = inp / "s.pdf"
        create_sample_student_pdf(student_pdf, "A B", num_pages=num_pages)
        create_front_template(inp / "front.pdf")
        create_back_cover(inp / "back.pdf")

        cfg = EngineConfig(base_path=tmp_dir, font_dir=str(PROJECT_FONTS))
        front_bytes = prepare_front_template(
            cfg.front_template_path, "A B", TemplateConfig(), cfg.font_path
        )
        out = tmp_dir / "out.pdf"
        content, blanks, final = assemble_booklet(student_pdf, front_bytes, cfg, out)

        assert content == num_pages
        assert final % 4 == 0
        assert final == 1 + num_pages + blanks + 1
        assert blanks < 4

    def test_blank_pages_before_back_cover(self, tmp_dir):
        inp = tmp_dir / "input_pdfs"
        inp.mkdir()
        student_pdf = inp / "s.pdf"
        create_sample_student_pdf(student_pdf, "A B", num_pages=7)  # 1+7+1 = 9 → 3 blanks
        create_front_template(inp / "front.pdf")
        create_back_cover(inp / "back.pdf")

        cfg = EngineConfig(base_path=tmp_dir, font_dir=str(PROJECT_FONTS))
        front_bytes = prepare_front_template(
            cfg.front_template_path, "A B", TemplateConfig(), cfg.font_path
        )
        out = tmp_dir / "out.pdf"
        assemble_booklet(student_pdf, front_bytes, cfg, out)

        doc = fitz.open(str(out))
        assert doc.page_count == 12
        # Pages 9–11 (0-based 8..10) are blank; last page is the back cover
        for i in range(8, 11):
            assert doc[i].get_text("text").strip() == ""
        assert "Arka" in doc[11].get_text("text")
        doc.close()


class TestPipelineAndBatch:
    def test_full_batch(self, test_env):
        cfg = test_env["config"]
        students = scan_student_pdfs(cfg.input_path, cfg)
        assert len(students) == 3

        report = run_batch(students, cfg, max_workers=1)
        assert report.success == 3
        assert report.errors == 0

        for r in report.results:
            assert r.output_path.exists()
            assert r.output_path.name == f"{r.student.safe_name}.pdf"
            with pikepdf.open(str(r.output_path)) as pdf:
                assert len(pdf.pages) % 4 == 0

    def test_duplicate_names_do_not_overwrite(self, test_env):
        cfg = test_env["config"]
        create_sample_student_pdf(cfg.input_path / "dup.pdf", "AHMET YILMAZ", num_pages=6)
        students = [s for s in scan_student_pdfs(cfg.input_path, cfg) if s.safe_name == "AHMET YILMAZ"]
        assert len(students) == 2

        results = [process_student(s, cfg) for s in students]
        assert all(r.status == ProcessingStatus.SUCCESS for r in results)
        names = {r.output_path.name for r in results}
        assert names == {"AHMET YILMAZ.pdf", "AHMET YILMAZ (2).pdf"}

    def test_missing_file_is_skipped(self, test_env):
        cfg = test_env["config"]
        r = process_student(StudentRecord("nope.pdf", "X", 1), cfg)
        assert r.status == ProcessingStatus.SKIPPED


class TestScanner:
    def test_scan_excludes_covers(self, test_env):
        cfg = test_env["config"]
        names = {s.safe_filename for s in scan_student_pdfs(cfg.input_path, cfg)}
        assert "front.pdf" not in names and "back.pdf" not in names
        assert len(names) == 3

    def test_scan_extracts_names(self, test_env):
        cfg = test_env["config"]
        found = {s.safe_filename: s.safe_name for s in scan_student_pdfs(cfg.input_path, cfg)}
        for filename, name in test_env["students"]:
            assert found[filename] == name

    def test_scan_empty_dir(self, tmp_dir):
        empty = tmp_dir / "empty"
        empty.mkdir()
        assert scan_student_pdfs(empty, EngineConfig()) == []


class TestConfig:
    def test_defaults(self, test_env):
        cfg = test_env["config"]
        assert cfg.front_template_filename == "front.pdf"
        assert cfg.back_cover_filename == "back.pdf"
        assert cfg.template.marker_text == "{{student.name}}"
        assert cfg.name_extraction.label_text == "Ad Soyad"

    def test_output_filename_sanitized(self):
        s = StudentRecord("x.pdf", 'A/B:C*D "E"', 1)
        assert s.output_filename == "ABCD E.pdf"
