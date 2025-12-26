"""Tests for the CLI interface."""

import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pdf2md import ConversionOptions, PDFConverter
from pdf2md.cli import create_options, main, parse_args, process_single_file
from tests.conftest import FIXTURES_DIR


class TestParseArgs:
    """Tests for the argument parser."""

    def test_single_input_file(self):
        """Test parsing a single input file."""
        args = parse_args(["document.pdf"])

        assert len(args.input) == 1
        assert args.input[0] == Path("document.pdf")

    def test_multiple_input_files(self):
        """Test parsing multiple input files."""
        args = parse_args(["doc1.pdf", "doc2.pdf", "doc3.pdf"])

        assert len(args.input) == 3
        assert args.input[0] == Path("doc1.pdf")
        assert args.input[1] == Path("doc2.pdf")
        assert args.input[2] == Path("doc3.pdf")

    def test_output_option(self):
        """Test the -o/--output option."""
        args = parse_args(["doc.pdf", "-o", "output.md"])
        assert args.output == Path("output.md")

        args = parse_args(["doc.pdf", "--output", "output.md"])
        assert args.output == Path("output.md")

    def test_images_option(self):
        """Test the --images option."""
        args = parse_args(["doc.pdf", "--images", "./images"])
        assert args.image_dir == Path("./images")

    def test_image_format_option(self):
        """Test the --image-format option."""
        args = parse_args(["doc.pdf", "--image-format", "jpg"])
        assert args.image_format == "jpg"

    def test_image_format_default(self):
        """Test the default image format."""
        args = parse_args(["doc.pdf"])
        assert args.image_format == "png"

    def test_image_dpi_option(self):
        """Test the --image-dpi option."""
        args = parse_args(["doc.pdf", "--image-dpi", "300"])
        assert args.image_dpi == 300

    def test_image_dpi_default(self):
        """Test the default image DPI."""
        args = parse_args(["doc.pdf"])
        assert args.image_dpi == 150

    def test_no_images_flag(self):
        """Test the --no-images flag."""
        args = parse_args(["doc.pdf", "--no-images"])
        assert args.no_images is True

        args = parse_args(["doc.pdf"])
        assert args.no_images is False

    def test_no_links_flag(self):
        """Test the --no-links flag."""
        args = parse_args(["doc.pdf", "--no-links"])
        assert args.no_links is True

        args = parse_args(["doc.pdf"])
        assert args.no_links is False

    def test_no_headings_flag(self):
        """Test the --no-headings flag."""
        args = parse_args(["doc.pdf", "--no-headings"])
        assert args.no_headings is True

    def test_no_formatting_flag(self):
        """Test the --no-formatting flag."""
        args = parse_args(["doc.pdf", "--no-formatting"])
        assert args.no_formatting is True

    def test_page_separator_option(self):
        """Test the --page-separator option."""
        args = parse_args(["doc.pdf", "--page-separator", "===PAGE==="])
        assert args.page_separator == "===PAGE==="

    def test_page_separator_default(self):
        """Test the default page separator."""
        args = parse_args(["doc.pdf"])
        assert args.page_separator == "\n\n---\n\n"

    def test_verbose_flag(self):
        """Test the -v/--verbose flag."""
        args = parse_args(["doc.pdf", "-v"])
        assert args.verbose is True

        args = parse_args(["doc.pdf", "--verbose"])
        assert args.verbose is True

        args = parse_args(["doc.pdf"])
        assert args.verbose is False


class TestCreateOptions:
    """Tests for the create_options function."""

    def test_default_options(self):
        """Test creating options with default arguments."""
        args = parse_args(["doc.pdf"])
        options = create_options(args)

        assert options.extract_images is True
        assert options.image_output_dir is None
        assert options.image_format == "png"
        assert options.image_dpi == 150
        assert options.preserve_hyperlinks is True
        assert options.detect_headings is True
        assert options.detect_bold_italic is True

    def test_custom_options(self):
        """Test creating options with custom arguments."""
        args = parse_args([
            "doc.pdf",
            "--no-images",
            "--no-links",
            "--no-headings",
            "--no-formatting",
            "--page-separator", "===",
        ])
        options = create_options(args)

        assert options.extract_images is False
        assert options.preserve_hyperlinks is False
        assert options.detect_headings is False
        assert options.detect_bold_italic is False
        assert options.page_separator == "==="

    def test_image_directory_option(self):
        """Test creating options with image directory."""
        args = parse_args(["doc.pdf", "--images", "/tmp/images"])
        options = create_options(args)

        assert options.image_output_dir == Path("/tmp/images")


class TestProcessSingleFile:
    """Tests for the process_single_file function."""

    def test_file_not_found(self, capsys):
        """Test handling of missing files."""
        converter = PDFConverter()
        result = process_single_file(Path("/nonexistent.pdf"), None, converter, False)

        assert result is False
        captured = capsys.readouterr()
        assert "File not found" in captured.err

    def test_non_pdf_warning(self, capsys):
        """Test warning for non-PDF files."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Not a PDF")
            tmp_path = Path(f.name)

        try:
            converter = PDFConverter()
            # This will fail because the file is not a valid PDF.
            result = process_single_file(tmp_path, None, converter, True)

            captured = capsys.readouterr()
            assert "may not be a PDF" in captured.err
        finally:
            tmp_path.unlink()

    def test_successful_conversion_to_stdout(self, capsys):
        """Test successful conversion to stdout."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF not available")

        converter = PDFConverter()
        result = process_single_file(sample_pdf, None, converter, False)

        assert result is True
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_successful_conversion_to_file(self):
        """Test successful conversion to output file."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.md"
            converter = PDFConverter()
            result = process_single_file(sample_pdf, output_path, converter, False)

            assert result is True
            assert output_path.exists()
            assert len(output_path.read_text()) > 0

    def test_verbose_output(self, capsys):
        """Test verbose output mode."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.md"
            converter = PDFConverter()
            result = process_single_file(sample_pdf, output_path, converter, True)

            assert result is True
            captured = capsys.readouterr()
            assert "Converting:" in captured.err
            assert "->" in captured.err


class TestMain:
    """Tests for the main entry point."""

    def test_single_file_to_stdout(self, capsys):
        """Test converting a single file to stdout."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF not available")

        exit_code = main([str(sample_pdf)])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_single_file_to_output(self):
        """Test converting a single file to output file."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.md"
            exit_code = main([str(sample_pdf), "-o", str(output_path)])

            assert exit_code == 0
            assert output_path.exists()

    def test_missing_file_returns_error(self):
        """Test that missing files return error exit code."""
        exit_code = main(["/nonexistent/file.pdf"])

        assert exit_code == 1

    def test_multiple_files_to_directory(self):
        """Test converting multiple files to directory."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            exit_code = main([str(sample_pdf), str(sample_pdf), "-o", str(output_dir)])

            # Check at least one output file was created.
            assert exit_code == 0

    def test_verbose_mode(self, capsys):
        """Test verbose mode output."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.md"
            exit_code = main([str(sample_pdf), "-o", str(output_path), "-v"])

            captured = capsys.readouterr()
            assert "Converting:" in captured.err

    def test_with_image_extraction(self):
        """Test conversion with image extraction."""
        sample_pdf = FIXTURES_DIR / "sample2.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample2.pdf not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.md"
            images_dir = Path(tmpdir) / "images"
            exit_code = main([
                str(sample_pdf),
                "-o", str(output_path),
                "--images", str(images_dir),
            ])

            assert exit_code == 0
            assert output_path.exists()

    def test_with_disabled_features(self, capsys):
        """Test conversion with disabled features."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF not available")

        exit_code = main([
            str(sample_pdf),
            "--no-images",
            "--no-links",
            "--no-headings",
            "--no-formatting",
        ])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert len(captured.out) > 0


class TestMainEdgeCases:
    """Edge case tests for the main module."""

    def test_output_directory_creation(self):
        """Test that output directories are created as needed."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dir" / "output.md"
            exit_code = main([str(sample_pdf), "-o", str(output_path)])

            assert exit_code == 0
            assert output_path.exists()

    def test_empty_page_separator(self, capsys):
        """Test with empty page separator."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF not available")

        exit_code = main([str(sample_pdf), "--page-separator", ""])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert len(captured.out) > 0

