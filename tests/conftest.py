"""Pytest configuration and shared fixtures."""

import pathlib
import tempfile

import pytest

from pdf2md import ConversionOptions, PDFConverter

# Path to the tests directory.
TESTS_DIR = pathlib.Path(__file__).parent

# Path to the fixtures directory.
FIXTURES_DIR = TESTS_DIR / "fixtures"


@pytest.fixture
def sample_pdf_path():
    """Return path to sample1.pdf if it exists."""
    path = FIXTURES_DIR / "sample1.pdf"
    if not path.exists():
        pytest.skip("sample1.pdf not available")
    return path


@pytest.fixture
def sample_pdf_with_images_path():
    """Return path to sample2.pdf if it exists."""
    path = FIXTURES_DIR / "sample2.pdf"
    if not path.exists():
        pytest.skip("sample2.pdf not available")
    return path


@pytest.fixture
def default_converter():
    """Return a PDFConverter with default options."""
    return PDFConverter()


@pytest.fixture
def converter_no_features():
    """Return a PDFConverter with all optional features disabled."""
    options = ConversionOptions(
        extract_images=False,
        preserve_hyperlinks=False,
        detect_headings=False,
        detect_lists=False,
        detect_bold_italic=False,
    )
    return PDFConverter(options)


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for output files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield pathlib.Path(tmpdir)


@pytest.fixture
def converter_with_image_output(temp_output_dir):
    """Return a PDFConverter configured to extract images."""
    options = ConversionOptions(
        extract_images=True,
        image_output_dir=temp_output_dir / "images",
    )
    return PDFConverter(options)
