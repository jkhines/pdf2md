"""Tests for the PDF to Markdown converter module."""

import re
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pdf2md.converter import (
    ConversionOptions,
    ImageInfo,
    Link,
    PageContent,
    PDFConverter,
    TableInfo,
    TextBlock,
)
from tests.conftest import FIXTURES_DIR


class TestConversionOptions:
    """Tests for ConversionOptions dataclass."""

    def test_default_options(self):
        """Verify default option values."""
        options = ConversionOptions()

        assert options.extract_images is True
        assert options.image_output_dir is None
        assert options.image_format == "png"
        assert options.image_dpi == 150
        assert options.preserve_hyperlinks is True
        assert options.detect_headings is True
        assert options.detect_lists is True
        assert options.detect_bold_italic is True
        assert options.heading_font_size_threshold == 14.0
        assert options.page_separator == "\n\n---\n\n"
        assert options.min_heading_size_ratio == 1.2

    def test_custom_options(self):
        """Verify custom option values are set correctly."""
        options = ConversionOptions(
            extract_images=False,
            image_output_dir=Path("/tmp/images"),
            image_format="jpg",
            image_dpi=300,
            preserve_hyperlinks=False,
            detect_headings=False,
            page_separator="---",
        )

        assert options.extract_images is False
        assert options.image_output_dir == Path("/tmp/images")
        assert options.image_format == "jpg"
        assert options.image_dpi == 300
        assert options.preserve_hyperlinks is False
        assert options.detect_headings is False
        assert options.page_separator == "---"


class TestTextBlock:
    """Tests for TextBlock dataclass."""

    def test_text_block_creation(self):
        """Verify TextBlock can be created with all fields."""
        block = TextBlock(
            text="Test text",
            font_size=12.0,
            font_name="Arial",
            is_bold=True,
            is_italic=False,
            bbox=(0, 0, 100, 20),
            page_num=0,
        )

        assert block.text == "Test text"
        assert block.font_size == 12.0
        assert block.font_name == "Arial"
        assert block.is_bold is True
        assert block.is_italic is False
        assert block.bbox == (0, 0, 100, 20)
        assert block.page_num == 0


class TestLink:
    """Tests for Link dataclass."""

    def test_link_creation(self):
        """Verify Link can be created with all fields."""
        link = Link(
            text="Click here",
            url="https://example.com",
            bbox=(10, 20, 100, 40),
            page_num=1,
        )

        assert link.text == "Click here"
        assert link.url == "https://example.com"
        assert link.bbox == (10, 20, 100, 40)
        assert link.page_num == 1


class TestImageInfo:
    """Tests for ImageInfo dataclass."""

    def test_image_info_creation(self):
        """Verify ImageInfo can be created with all fields."""
        img = ImageInfo(
            xref=42,
            bbox=(0, 0, 200, 150),
            page_num=0,
            filename="test.png",
            width=200,
            height=150,
        )

        assert img.xref == 42
        assert img.bbox == (0, 0, 200, 150)
        assert img.page_num == 0
        assert img.filename == "test.png"
        assert img.width == 200
        assert img.height == 150

    def test_image_info_defaults(self):
        """Verify ImageInfo default values."""
        img = ImageInfo(xref=1, bbox=(0, 0, 0, 0), page_num=0)

        assert img.filename == ""
        assert img.width == 0
        assert img.height == 0


class TestPageContent:
    """Tests for PageContent dataclass."""

    def test_page_content_creation(self):
        """Verify PageContent can be created with all fields."""
        content = PageContent(page_num=0)

        assert content.page_num == 0
        assert content.text_blocks == []
        assert content.links == []
        assert content.images == []
        assert content.base_font_size == 12.0


class TestPDFConverter:
    """Tests for the PDFConverter class."""

    def test_converter_initialization_default_options(self):
        """Verify converter initializes with default options."""
        converter = PDFConverter()

        assert converter.options is not None
        assert converter.options.extract_images is True

    def test_converter_initialization_custom_options(self):
        """Verify converter initializes with custom options."""
        options = ConversionOptions(extract_images=False)
        converter = PDFConverter(options)

        assert converter.options.extract_images is False

    def test_convert_file_not_found(self):
        """Verify FileNotFoundError is raised for missing files."""
        converter = PDFConverter()

        with pytest.raises(FileNotFoundError, match="PDF file not found"):
            converter.convert_file("/nonexistent/path/file.pdf")

    def test_convert_sample_pdf(self):
        """Test conversion of a sample PDF file."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF not available")

        converter = PDFConverter()
        markdown = converter.convert_file(sample_pdf)

        assert isinstance(markdown, str)
        assert len(markdown) > 0

    def test_convert_with_output_file(self):
        """Test conversion with output file path."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.md"
            converter = PDFConverter()
            markdown = converter.convert_file(sample_pdf, output_path)

            assert output_path.exists()
            assert output_path.read_text(encoding="utf-8") == markdown

    def test_convert_with_image_extraction(self):
        """Test conversion with image extraction enabled."""
        sample_pdf = FIXTURES_DIR / "sample2.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF with images not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            options = ConversionOptions(
                extract_images=True,
                image_output_dir=Path(tmpdir),
            )
            converter = PDFConverter(options)
            converter.convert_file(sample_pdf)

            # Check if any images were extracted.
            images = list(Path(tmpdir).glob("*.png")) + list(Path(tmpdir).glob("*.jpg"))
            # Images may or may not be present depending on the PDF.
            assert isinstance(images, list)

    def test_calculate_median_empty(self):
        """Test median calculation with empty list."""
        result = PDFConverter._calculate_median([])
        assert result == 0.0

    def test_calculate_median_single(self):
        """Test median calculation with single value."""
        result = PDFConverter._calculate_median([5.0])
        assert result == 5.0

    def test_calculate_median_odd(self):
        """Test median calculation with odd number of values."""
        result = PDFConverter._calculate_median([1.0, 3.0, 5.0])
        assert result == 3.0

    def test_calculate_median_even(self):
        """Test median calculation with even number of values."""
        result = PDFConverter._calculate_median([1.0, 2.0, 3.0, 4.0])
        assert result == 2.5

    def test_bboxes_overlap_true(self):
        """Test that overlapping bboxes are detected."""
        converter = PDFConverter()

        # Overlapping boxes.
        result = converter._bboxes_overlap((0, 0, 100, 100), (50, 50, 150, 150))
        assert result is True

    def test_bboxes_overlap_false_horizontal(self):
        """Test that non-overlapping horizontal bboxes are detected."""
        converter = PDFConverter()

        # Non-overlapping boxes (horizontal separation).
        result = converter._bboxes_overlap((0, 0, 50, 50), (100, 0, 150, 50))
        assert result is False

    def test_bboxes_overlap_false_vertical(self):
        """Test that non-overlapping vertical bboxes are detected."""
        converter = PDFConverter()

        # Non-overlapping boxes (vertical separation).
        result = converter._bboxes_overlap((0, 0, 50, 50), (0, 100, 50, 150))
        assert result is False

    def test_bboxes_overlap_edge_touch(self):
        """Test that edge-touching bboxes are considered overlapping."""
        converter = PDFConverter()

        # Boxes that touch at edge are considered overlapping by this implementation.
        result = converter._bboxes_overlap((0, 0, 50, 50), (50, 0, 100, 50))
        assert result is True

    def test_detect_heading_level_none_small_font(self):
        """Test that small fonts are not detected as headings."""
        converter = PDFConverter()

        result = converter._detect_heading_level(10.0, 12.0)
        assert result is None

    def test_detect_heading_level_h1(self):
        """Test H1 heading detection for very large fonts."""
        converter = PDFConverter()

        result = converter._detect_heading_level(24.0, 12.0)
        assert result == 1

    def test_detect_heading_level_h2(self):
        """Test H2 heading detection."""
        converter = PDFConverter()

        result = converter._detect_heading_level(20.4, 12.0)
        assert result == 2

    def test_detect_heading_level_h3(self):
        """Test H3 heading detection."""
        converter = PDFConverter()

        result = converter._detect_heading_level(16.8, 12.0)
        assert result == 3

    def test_detect_heading_level_h4(self):
        """Test H4 heading detection."""
        converter = PDFConverter()

        result = converter._detect_heading_level(14.4, 12.0)
        assert result == 4

    def test_detect_heading_level_zero_base(self):
        """Test heading detection with zero base font size."""
        converter = PDFConverter()

        # When base_font_size is 0, ratio defaults to 1.0 which is below min_heading_size_ratio.
        result = converter._detect_heading_level(16.0, 0.0)
        assert result is None

    def test_detect_list_item_numbered(self):
        """Test numbered list detection."""
        converter = PDFConverter()

        assert converter._detect_list_item("1. First item") == "1. First item"
        assert converter._detect_list_item("2) Second item") == "2. Second item"
        assert converter._detect_list_item("10. Tenth item") == "10. Tenth item"

    def test_detect_list_item_bullet(self):
        """Test bullet list detection."""
        converter = PDFConverter()

        assert converter._detect_list_item("• Bullet item") == "- Bullet item"
        assert converter._detect_list_item("● Filled bullet") == "- Filled bullet"
        assert converter._detect_list_item("- Dash item") == "- Dash item"
        assert converter._detect_list_item("► Arrow item") == "- Arrow item"

    def test_detect_list_item_no_match(self):
        """Test that non-list text is unchanged."""
        converter = PDFConverter()

        assert converter._detect_list_item("Regular text") == "Regular text"
        assert converter._detect_list_item("No list here") == "No list here"

    def test_post_process_markdown_excessive_newlines(self):
        """Test that excessive newlines are cleaned up."""
        converter = PDFConverter()

        result = converter._post_process_markdown("Line 1\n\n\n\n\nLine 2")
        assert "\n\n\n\n\n" not in result

    def test_post_process_markdown_trailing_whitespace(self):
        """Test that trailing whitespace is removed."""
        converter = PDFConverter()

        result = converter._post_process_markdown("Line with trailing spaces   \nNext line")
        lines = result.split("\n")
        for line in lines:
            assert line == line.rstrip()

    def test_apply_links_exact_match(self):
        """Test link application with exact text match."""
        converter = PDFConverter()

        link = Link(text="Click here", url="https://example.com", bbox=(0, 0, 100, 20), page_num=0)
        link_map = {(0, 0, 100, 20): link}

        result = converter._apply_links("Click here", (0, 0, 100, 20), link_map)
        assert result == "[Click here](https://example.com)"

    def test_apply_links_partial_match(self):
        """Test link application with partial text match."""
        converter = PDFConverter()

        link = Link(text="link", url="https://example.com", bbox=(0, 0, 100, 20), page_num=0)
        link_map = {(0, 0, 100, 20): link}

        result = converter._apply_links("Click this link here", (0, 0, 100, 20), link_map)
        assert "[link](https://example.com)" in result

    def test_apply_links_no_match(self):
        """Test link application with no matching link."""
        converter = PDFConverter()

        result = converter._apply_links("No links here", (0, 0, 100, 20), {})
        assert result == "No links here"

    def test_format_text_block_heading(self):
        """Test text block formatting as heading."""
        options = ConversionOptions(detect_headings=True)
        converter = PDFConverter(options)

        block = TextBlock(
            text="Large Heading",
            font_size=24.0,
            font_name="Arial",
            is_bold=True,
            is_italic=False,
            bbox=(0, 0, 200, 30),
            page_num=0,
        )

        result = converter._format_text_block(block, 12.0, {})
        assert result.startswith("#")
        assert "Large Heading" in result

    def test_format_text_block_bold(self):
        """Test text block formatting with bold."""
        options = ConversionOptions(detect_headings=False, detect_bold_italic=True)
        converter = PDFConverter(options)

        block = TextBlock(
            text="Bold text",
            font_size=12.0,
            font_name="Arial-Bold",
            is_bold=True,
            is_italic=False,
            bbox=(0, 0, 100, 20),
            page_num=0,
        )

        result = converter._format_text_block(block, 12.0, {})
        assert result == "**Bold text**"

    def test_format_text_block_italic(self):
        """Test text block formatting with italic."""
        options = ConversionOptions(detect_headings=False, detect_bold_italic=True)
        converter = PDFConverter(options)

        block = TextBlock(
            text="Italic text",
            font_size=12.0,
            font_name="Arial-Italic",
            is_bold=False,
            is_italic=True,
            bbox=(0, 0, 100, 20),
            page_num=0,
        )

        result = converter._format_text_block(block, 12.0, {})
        assert result == "*Italic text*"

    def test_format_text_block_bold_italic(self):
        """Test text block formatting with bold and italic."""
        options = ConversionOptions(detect_headings=False, detect_bold_italic=True)
        converter = PDFConverter(options)

        block = TextBlock(
            text="Bold italic text",
            font_size=12.0,
            font_name="Arial-BoldItalic",
            is_bold=True,
            is_italic=True,
            bbox=(0, 0, 100, 20),
            page_num=0,
        )

        result = converter._format_text_block(block, 12.0, {})
        assert result == "***Bold italic text***"

    def test_format_text_block_empty(self):
        """Test text block formatting with empty text."""
        converter = PDFConverter()

        block = TextBlock(
            text="   ",
            font_size=12.0,
            font_name="Arial",
            is_bold=False,
            is_italic=False,
            bbox=(0, 0, 100, 20),
            page_num=0,
        )

        result = converter._format_text_block(block, 12.0, {})
        assert result == ""

    def test_convert_bytes(self):
        """Test conversion from bytes."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF not available")

        pdf_bytes = sample_pdf.read_bytes()
        converter = PDFConverter()
        markdown = converter.convert_bytes(pdf_bytes, "sample1")

        assert isinstance(markdown, str)
        assert len(markdown) > 0

    def test_convert_stream(self):
        """Test conversion from stream."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("Sample PDF not available")

        converter = PDFConverter()
        with open(sample_pdf, "rb") as f:
            markdown = converter.convert_stream(f, "sample1")

        assert isinstance(markdown, str)
        assert len(markdown) > 0


class TestPDFConverterIntegration:
    """Integration tests with real PDF files."""

    def test_sample1_basic_conversion(self):
        """Test basic conversion of sample1.pdf."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample1.pdf not available")

        converter = PDFConverter()
        markdown = converter.convert_file(sample_pdf)

        # Should produce some output.
        assert len(markdown) > 0

    def test_sample2_with_images(self):
        """Test conversion of sample2.pdf with image extraction."""
        sample_pdf = FIXTURES_DIR / "sample2.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample2.pdf not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            options = ConversionOptions(
                extract_images=True,
                image_output_dir=Path(tmpdir),
            )
            converter = PDFConverter(options)
            markdown = converter.convert_file(sample_pdf)

            assert len(markdown) > 0

    def test_disabled_features(self):
        """Test conversion with all optional features disabled."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample1.pdf not available")

        options = ConversionOptions(
            extract_images=False,
            preserve_hyperlinks=False,
            detect_headings=False,
            detect_lists=False,
            detect_bold_italic=False,
        )
        converter = PDFConverter(options)
        markdown = converter.convert_file(sample_pdf)

        # Should still produce output.
        assert len(markdown) > 0
        # Should not have heading markers if detect_headings is False.
        # Note: This depends on the PDF content.

    def test_custom_page_separator(self):
        """Test conversion with custom page separator."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample1.pdf not available")

        options = ConversionOptions(page_separator="\n<!-- page break -->\n")
        converter = PDFConverter(options)
        markdown = converter.convert_file(sample_pdf)

        assert len(markdown) > 0


class TestTextBlockMerging:
    """Tests for text block merging functionality.

    These tests verify that the converter properly merges:
    - Standalone bullet markers with their content
    - Standalone number markers with their content
    - Consecutive paragraph lines into single blocks
    """

    def test_merge_standalone_bullet_with_content(self):
        """Test that standalone bullet markers are merged with following content."""
        converter = PDFConverter()

        # Simulate blocks as they would come from a PDF with bullet on separate line.
        blocks = [
            TextBlock(text="•", font_size=12, font_name="Arial", is_bold=False,
                      is_italic=False, bbox=(72, 100, 80, 112), page_num=0),
            TextBlock(text="First item content", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(85, 100, 200, 112), page_num=0),
        ]

        merged = converter._merge_text_blocks(blocks)

        assert len(merged) == 1
        assert merged[0].text == "- First item content"

    def test_merge_standalone_number_with_content(self):
        """Test that standalone number markers are merged with following content."""
        converter = PDFConverter()

        # Simulate blocks with number on separate line.
        blocks = [
            TextBlock(text="1.", font_size=12, font_name="Arial", is_bold=False,
                      is_italic=False, bbox=(72, 100, 85, 112), page_num=0),
            TextBlock(text="First numbered item", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(90, 100, 250, 112), page_num=0),
        ]

        merged = converter._merge_text_blocks(blocks)

        assert len(merged) == 1
        assert merged[0].text == "1. First numbered item"

    def test_merge_consecutive_paragraph_lines(self):
        """Test that consecutive lines are merged into a single paragraph."""
        converter = PDFConverter()

        # Simulate wrapped paragraph text.
        blocks = [
            TextBlock(text="This is the first line of a paragraph that", font_size=12,
                      font_name="Arial", is_bold=False, is_italic=False,
                      bbox=(72, 100, 500, 112), page_num=0),
            TextBlock(text="continues on the second line.", font_size=12,
                      font_name="Arial", is_bold=False, is_italic=False,
                      bbox=(72, 114, 300, 126), page_num=0),
        ]

        merged = converter._merge_text_blocks(blocks)

        assert len(merged) == 1
        assert "first line of a paragraph" in merged[0].text
        assert "continues on the second line" in merged[0].text

    def test_no_merge_different_pages(self):
        """Test that blocks on different pages are not merged."""
        converter = PDFConverter()

        blocks = [
            TextBlock(text="Text on page 1", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(72, 100, 200, 112), page_num=0),
            TextBlock(text="Text on page 2", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(72, 100, 200, 112), page_num=1),
        ]

        merged = converter._merge_text_blocks(blocks)

        assert len(merged) == 2

    def test_no_merge_different_font_sizes(self):
        """Test that blocks with very different font sizes are not merged."""
        converter = PDFConverter()

        blocks = [
            TextBlock(text="Heading text", font_size=24, font_name="Arial",
                      is_bold=True, is_italic=False, bbox=(72, 100, 200, 130), page_num=0),
            TextBlock(text="Body text", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(72, 135, 200, 147), page_num=0),
        ]

        merged = converter._merge_text_blocks(blocks)

        assert len(merged) == 2

    def test_no_merge_with_large_vertical_gap(self):
        """Test that blocks with large vertical gaps are not merged."""
        converter = PDFConverter()

        blocks = [
            TextBlock(text="First paragraph", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(72, 100, 200, 112), page_num=0),
            TextBlock(text="Second paragraph after gap", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(72, 200, 300, 212), page_num=0),
        ]

        merged = converter._merge_text_blocks(blocks)

        assert len(merged) == 2

    def test_merge_hyphenated_word(self):
        """Test that hyphenated words at line breaks are properly joined."""
        converter = PDFConverter()

        blocks = [
            TextBlock(text="This is a hyph-", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(72, 100, 200, 112), page_num=0),
            TextBlock(text="enated word.", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(72, 114, 150, 126), page_num=0),
        ]

        merged = converter._merge_text_blocks(blocks)

        assert len(merged) == 1
        assert "hyphenated" in merged[0].text
        assert "hyph-" not in merged[0].text

    def test_multiple_bullets_each_merged(self):
        """Test that multiple bullet items are each properly merged."""
        converter = PDFConverter()

        blocks = [
            TextBlock(text="•", font_size=12, font_name="Arial", is_bold=False,
                      is_italic=False, bbox=(72, 100, 80, 112), page_num=0),
            TextBlock(text="First item", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(85, 100, 200, 112), page_num=0),
            TextBlock(text="•", font_size=12, font_name="Arial", is_bold=False,
                      is_italic=False, bbox=(72, 120, 80, 132), page_num=0),
            TextBlock(text="Second item", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(85, 120, 200, 132), page_num=0),
        ]

        merged = converter._merge_text_blocks(blocks)

        assert len(merged) == 2
        assert merged[0].text == "- First item"
        assert merged[1].text == "- Second item"

    def test_bullet_with_multiline_continuation(self):
        """Test that bullet items with multiple continuation lines are fully merged."""
        converter = PDFConverter()

        # Simulate a bullet item that wraps across 3 lines.
        blocks = [
            TextBlock(text="•", font_size=12, font_name="Arial", is_bold=False,
                      is_italic=False, bbox=(72, 100, 80, 112), page_num=0),
            TextBlock(text="Branch/merge discipline: protect", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(85, 100, 300, 112), page_num=0),
            TextBlock(text="main; keep branches short-lived;", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(72, 114, 300, 126), page_num=0),
            TextBlock(text="merge frequently.", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(72, 128, 200, 140), page_num=0),
        ]

        merged = converter._merge_text_blocks(blocks)

        assert len(merged) == 1
        assert "Branch/merge discipline" in merged[0].text
        assert "main" in merged[0].text
        assert "merge frequently" in merged[0].text
        assert merged[0].text.startswith("- ")

    def test_numbered_item_with_multiline_continuation(self):
        """Test that numbered items with multiple continuation lines are fully merged."""
        converter = PDFConverter()

        # Simulate a numbered item that wraps across 2 lines.
        blocks = [
            TextBlock(text="1.", font_size=12, font_name="Arial", is_bold=False,
                      is_italic=False, bbox=(72, 100, 85, 112), page_num=0),
            TextBlock(text="First item starts here and", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(90, 100, 300, 112), page_num=0),
            TextBlock(text="continues on this line.", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(72, 114, 250, 126), page_num=0),
        ]

        merged = converter._merge_text_blocks(blocks)

        assert len(merged) == 1
        assert merged[0].text == "1. First item starts here and continues on this line."

    def test_should_continue_list_item_same_page(self):
        """Test list item continuation detection for same-page content."""
        converter = PDFConverter()

        first = TextBlock(text="Start content", font_size=12, font_name="Arial",
                          is_bold=False, is_italic=False, bbox=(72, 100, 200, 112), page_num=0)
        candidate = TextBlock(text="continues here", font_size=12, font_name="Arial",
                              is_bold=False, is_italic=False, bbox=(72, 114, 180, 126), page_num=0)
        prev = first

        assert converter._should_continue_list_item(first, candidate, prev) is True

    def test_should_not_continue_list_item_new_bullet(self):
        """Test list item continuation rejects new bullet markers."""
        converter = PDFConverter()

        first = TextBlock(text="Start content", font_size=12, font_name="Arial",
                          is_bold=False, is_italic=False, bbox=(72, 100, 200, 112), page_num=0)
        candidate = TextBlock(text="•", font_size=12, font_name="Arial",
                              is_bold=False, is_italic=False, bbox=(72, 114, 80, 126), page_num=0)
        prev = first

        assert converter._should_continue_list_item(first, candidate, prev) is False

    def test_should_not_continue_list_item_different_page(self):
        """Test list item continuation rejects different pages."""
        converter = PDFConverter()

        first = TextBlock(text="Start content", font_size=12, font_name="Arial",
                          is_bold=False, is_italic=False, bbox=(72, 100, 200, 112), page_num=0)
        candidate = TextBlock(text="continues here", font_size=12, font_name="Arial",
                              is_bold=False, is_italic=False, bbox=(72, 114, 180, 126), page_num=1)
        prev = first

        assert converter._should_continue_list_item(first, candidate, prev) is False

    def test_merge_bboxes(self):
        """Test that bounding boxes are properly merged."""
        converter = PDFConverter()

        bbox1 = (10, 20, 100, 40)
        bbox2 = (15, 45, 120, 60)

        merged = converter._merge_bboxes(bbox1, bbox2)

        assert merged == (10, 20, 120, 60)

    def test_should_join_bullet_same_line(self):
        """Test bullet joining detection for same-line content."""
        converter = PDFConverter()

        bullet = TextBlock(text="•", font_size=12, font_name="Arial", is_bold=False,
                           is_italic=False, bbox=(72, 100, 80, 112), page_num=0)
        content = TextBlock(text="Content", font_size=12, font_name="Arial",
                            is_bold=False, is_italic=False, bbox=(85, 100, 200, 112), page_num=0)

        assert converter._should_join_bullet(bullet, content) is True

    def test_should_not_join_bullet_different_page(self):
        """Test bullet joining detection rejects different pages."""
        converter = PDFConverter()

        bullet = TextBlock(text="•", font_size=12, font_name="Arial", is_bold=False,
                           is_italic=False, bbox=(72, 100, 80, 112), page_num=0)
        content = TextBlock(text="Content", font_size=12, font_name="Arial",
                            is_bold=False, is_italic=False, bbox=(85, 100, 200, 112), page_num=1)

        assert converter._should_join_bullet(bullet, content) is False

    def test_empty_blocks_list(self):
        """Test that empty block list returns empty result."""
        converter = PDFConverter()

        merged = converter._merge_text_blocks([])

        assert merged == []

    def test_single_block_unchanged(self):
        """Test that a single block is returned unchanged."""
        converter = PDFConverter()

        blocks = [
            TextBlock(text="Single block", font_size=12, font_name="Arial",
                      is_bold=False, is_italic=False, bbox=(72, 100, 200, 112), page_num=0),
        ]

        merged = converter._merge_text_blocks(blocks)

        assert len(merged) == 1
        assert merged[0].text == "Single block"


class TestTextBlockMergingIntegration:
    """Integration tests verifying that the original formatting bugs are fixed."""

    def test_sample1_no_isolated_bullets(self):
        """Verify sample1.pdf conversion has no isolated bullet characters."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample1.pdf not available")

        converter = PDFConverter()
        markdown = converter.convert_file(sample_pdf)

        # Split into lines and check for isolated bullets.
        lines = markdown.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            # A line should not be just a bullet character.
            assert stripped not in ["•", "●", "○", "▪", "►"], \
                f"Found isolated bullet on line {i + 1}: '{stripped}'"

    def test_sample1_no_isolated_numbers(self):
        """Verify sample1.pdf conversion has no isolated number markers."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample1.pdf not available")

        converter = PDFConverter()
        markdown = converter.convert_file(sample_pdf)

        # Split into lines and check for isolated numbers.
        lines = markdown.split("\n")
        import re
        for i, line in enumerate(lines):
            stripped = line.strip()
            # A line should not be just a number marker like "1." or "2)".
            if re.match(r"^\d+[.):]?\s*$", stripped):
                pytest.fail(f"Found isolated number marker on line {i + 1}: '{stripped}'")

    def test_sample2_bullets_have_content(self):
        """Verify sample2.pdf bullet points include their content."""
        sample_pdf = FIXTURES_DIR / "sample2.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample2.pdf not available")

        converter = PDFConverter()
        markdown = converter.convert_file(sample_pdf)

        # Find all lines starting with "- " and verify they have content.
        lines = markdown.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("- "):
                content_after_bullet = line.strip()[2:].strip()
                assert len(content_after_bullet) > 0, \
                    f"Bullet on line {i + 1} has no content: '{line}'"

    def test_sample2_numbered_lists_have_content(self):
        """Verify sample2.pdf numbered list items include their content."""
        sample_pdf = FIXTURES_DIR / "sample2.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample2.pdf not available")

        converter = PDFConverter()
        markdown = converter.convert_file(sample_pdf)

        # Find all lines starting with a number and verify they have content.
        lines = markdown.split("\n")
        import re
        for i, line in enumerate(lines):
            match = re.match(r"^(\d+)\.\s*(.*)$", line.strip())
            if match:
                content_after_number = match.group(2).strip()
                assert len(content_after_number) > 0, \
                    f"Numbered item on line {i + 1} has no content: '{line}'"

    def test_paragraphs_not_split_across_lines(self):
        """Verify that paragraphs are not split into single-line fragments."""
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample1.pdf not available")

        converter = PDFConverter()
        markdown = converter.convert_file(sample_pdf)

        # Check that we don't have an excessive number of very short lines.
        lines = [l for l in markdown.split("\n") if l.strip()]
        short_lines = [l for l in lines if len(l.strip()) < 20 and not l.strip().startswith("#") and not l.strip().startswith("-") and l.strip() != "---"]

        # Allow some short lines but not too many relative to total.
        short_line_ratio = len(short_lines) / len(lines) if lines else 0
        assert short_line_ratio < 0.3, \
            f"Too many short lines ({len(short_lines)}/{len(lines)} = {short_line_ratio:.1%}), suggests poor paragraph merging"

    def test_practical_git_section_not_fragmented(self):
        """Verify the 'Practical Git best practices' section is not fragmented.

        This tests the specific issue where bullet items with wrapped text
        were being split across multiple lines instead of merged properly.
        """
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample1.pdf not available")

        converter = PDFConverter()
        markdown = converter.convert_file(sample_pdf)

        # Find the Git best practices section.
        if "Practical Git" not in markdown:
            pytest.skip("Practical Git section not found in sample1.pdf")

        # Extract lines after the heading.
        lines = markdown.split("\n")
        in_section = False
        section_bullets = []

        for line in lines:
            if "Practical Git" in line:
                in_section = True
                continue
            if in_section:
                if line.strip().startswith("#"):
                    break
                if line.strip().startswith("- "):
                    section_bullets.append(line.strip())

        # Each bullet should contain substantial content (not be fragmented).
        for bullet in section_bullets:
            content = bullet[2:].strip()
            # A properly merged bullet should have more than just a word or two.
            assert len(content) > 20, \
                f"Bullet appears fragmented (too short): '{bullet}'"

    def test_bullet_content_not_orphaned_on_next_line(self):
        """Verify bullet content is not orphaned on the line after the bullet marker.

        This catches the bug where a bullet line was followed by its content
        on a separate line instead of being merged.
        """
        sample_pdf = FIXTURES_DIR / "sample1.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample1.pdf not available")

        converter = PDFConverter()
        markdown = converter.convert_file(sample_pdf)

        lines = markdown.split("\n")
        for i, line in enumerate(lines):
            # Check for lines that look like orphaned bullet content:
            # A line starting with a word like "main" or similar that should have been merged.
            stripped = line.strip()

            # Skip empty lines, headings, bullets, numbers, separators.
            if not stripped:
                continue
            if stripped.startswith("#") or stripped.startswith("-") or stripped == "---":
                continue
            if stripped[0].isdigit():
                continue

            # If previous line is a bullet, this line should not be orphaned content.
            if i > 0:
                prev_line = lines[i - 1].strip()
                # A bullet followed immediately by a non-bullet, non-empty line
                # that doesn't start a new structure might indicate a merge failure.
                if prev_line.startswith("- ") and len(prev_line) < 40:
                    # If the previous bullet is short and this line is continuation,
                    # it suggests content was not merged.
                    combined_would_be = prev_line + " " + stripped
                    if len(combined_would_be) < 150 and ";" in stripped:
                        pytest.fail(
                            f"Line {i + 1} appears to be orphaned content that should have "
                            f"been merged with previous bullet.\n"
                            f"  Previous: '{prev_line}'\n"
                            f"  Current:  '{stripped}'"
                        )

    def test_multiline_list_items_fully_merged(self):
        """Verify that list items spanning multiple lines are fully merged."""
        sample_pdf = FIXTURES_DIR / "sample2.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample2.pdf not available")

        converter = PDFConverter()
        markdown = converter.convert_file(sample_pdf)

        lines = markdown.split("\n")
        import re

        # Look for patterns that suggest incomplete merging:
        # - A short bullet followed by continuation text on the next line.
        for i in range(len(lines) - 1):
            current = lines[i].strip()
            next_line = lines[i + 1].strip()

            # Skip empty lines.
            if not current or not next_line:
                continue

            # If current is a short bullet (under 50 chars) and next line
            # is plain text (not a heading, bullet, number, separator), check if they should be merged.
            if current.startswith("- ") and len(current) < 50:
                if (next_line and
                    not next_line.startswith("#") and
                    not next_line.startswith("-") and
                    not re.match(r"^\d+\.", next_line) and
                    next_line != "---" and
                    not next_line.startswith("[")):
                    # This could be orphaned continuation text.
                    # Check if it looks like it continues the previous sentence.
                    if next_line[0].islower() or next_line.startswith("main"):
                        pytest.fail(
                            f"Line {i + 2} may be orphaned list content:\n"
                            f"  Bullet: '{current}'\n"
                            f"  Orphan: '{next_line}'"
                        )


class TestFormattingPreservation:
    """Tests for preserving formatting like bold, indentation, and special characters."""

    def test_bold_text_preserved_in_list_item(self):
        """Test that bold text is preserved in list item content."""
        converter = PDFConverter()

        block = TextBlock(
            text="- Naming:",
            font_size=12,
            font_name="Arial",
            is_bold=True,
            is_italic=False,
            bbox=(94, 100, 200, 112),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )

        result = converter._format_text_block(block, 12.0, {})
        assert result == "- **Naming:**"

    def test_italic_text_preserved_in_list_item(self):
        """Test that italic text is preserved in list item content."""
        converter = PDFConverter()

        block = TextBlock(
            text="- Emphasis item",
            font_size=12,
            font_name="Arial",
            is_bold=False,
            is_italic=True,
            bbox=(94, 100, 200, 112),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )

        result = converter._format_text_block(block, 12.0, {})
        assert result == "- *Emphasis item*"

    def test_bold_italic_text_preserved_in_list_item(self):
        """Test that bold italic text is preserved in list item content."""
        converter = PDFConverter()

        block = TextBlock(
            text="- Strong emphasis",
            font_size=12,
            font_name="Arial",
            is_bold=True,
            is_italic=True,
            bbox=(94, 100, 200, 112),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )

        result = converter._format_text_block(block, 12.0, {})
        assert result == "- ***Strong emphasis***"

    def test_numbered_list_item_bold_preserved(self):
        """Test that bold text is preserved in numbered list items."""
        converter = PDFConverter()

        block = TextBlock(
            text="1. First item",
            font_size=12,
            font_name="Arial",
            is_bold=True,
            is_italic=False,
            bbox=(94, 100, 200, 112),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )

        result = converter._format_text_block(block, 12.0, {})
        assert result == "1. **First item**"

    def test_sub_bullet_indentation_level_1(self):
        """Test that sub-bullets at indent level 1 have 4-space indentation."""
        converter = PDFConverter()

        block = TextBlock(
            text="- Branches: feature/name-part-1",
            font_size=12,
            font_name="Arial",
            is_bold=False,
            is_italic=False,
            bbox=(131, 100, 300, 112),
            page_num=0,
            is_monospace=False,
            indent_level=1,
        )

        result = converter._format_text_block(block, 12.0, {})
        assert result.startswith("    - ")
        assert "Branches" in result

    def test_sub_bullet_indentation_level_2(self):
        """Test that sub-bullets at indent level 2 have 8-space indentation."""
        converter = PDFConverter()

        block = TextBlock(
            text="- Deeply nested item",
            font_size=12,
            font_name="Arial",
            is_bold=False,
            is_italic=False,
            bbox=(170, 100, 300, 112),
            page_num=0,
            is_monospace=False,
            indent_level=2,
        )

        result = converter._format_text_block(block, 12.0, {})
        assert result.startswith("        - ")

    def test_hash_escaped_at_line_start(self):
        """Test that # at line start is escaped to prevent header interpretation."""
        converter = PDFConverter()

        block = TextBlock(
            text="# Base feature",
            font_size=12,
            font_name="Arial",
            is_bold=False,
            is_italic=False,
            bbox=(72, 100, 200, 112),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )

        result = converter._format_text_block(block, 12.0, {})
        assert result.startswith("\\#")
        assert "Base feature" in result

    def test_monospace_font_detected(self):
        """Test that monospace fonts are correctly identified."""
        converter = PDFConverter()

        assert converter._is_monospace_font("Courier") is True
        assert converter._is_monospace_font("Consolas") is True
        assert converter._is_monospace_font("Monaco") is True
        assert converter._is_monospace_font("Source Code Pro") is True
        assert converter._is_monospace_font("Liberation Mono") is True
        assert converter._is_monospace_font("Arial") is False
        assert converter._is_monospace_font("Times New Roman") is False
        assert converter._is_monospace_font("Liberation-Sans") is False

    def test_monospace_text_formatted_as_code(self):
        """Test that monospace text is formatted with backticks."""
        converter = PDFConverter()

        block = TextBlock(
            text="git commit -m 'message'",
            font_size=12,
            font_name="Courier",
            is_bold=False,
            is_italic=False,
            bbox=(72, 100, 300, 112),
            page_num=0,
            is_monospace=True,
            indent_level=0,
        )

        result = converter._format_text_block(block, 12.0, {})
        assert result == "`git commit -m 'message'`"

    def test_indent_level_calculation(self):
        """Test that indent levels are calculated correctly from x-positions."""
        converter = PDFConverter()

        # Simulate x-positions from a document.
        x_positions = [72, 72, 94, 94, 131, 131, 72, 94]
        thresholds = converter._calculate_indent_thresholds(x_positions)

        # Should have at least 2 distinct levels.
        assert len(thresholds) >= 2

        # Test level assignment.
        level_72 = converter._get_indent_level(72, thresholds)
        level_94 = converter._get_indent_level(94, thresholds)
        level_131 = converter._get_indent_level(131, thresholds)

        # Each should map to increasing levels.
        assert level_72 <= level_94
        assert level_94 <= level_131

    def test_hash_lines_not_merged(self):
        """Test that lines starting with # are not merged with other lines."""
        converter = PDFConverter()

        # Simulate shell comment followed by command.
        block1 = TextBlock(
            text="# Base feature",
            font_size=12,
            font_name="Arial",
            is_bold=False,
            is_italic=False,
            bbox=(72, 100, 200, 112),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )
        block2 = TextBlock(
            text="git checkout -b feature/step1",
            font_size=12,
            font_name="Arial",
            is_bold=False,
            is_italic=False,
            bbox=(72, 114, 300, 126),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )

        # First block starts with #, should not merge.
        assert converter._should_merge_lines(block1, block2, block1) is False

    def test_hash_lines_not_merged_as_second(self):
        """Test that lines starting with # are not merged as continuation."""
        converter = PDFConverter()

        block1 = TextBlock(
            text="git checkout -b feature/step1",
            font_size=12,
            font_name="Arial",
            is_bold=False,
            is_italic=False,
            bbox=(72, 100, 300, 112),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )
        block2 = TextBlock(
            text="# ... work ...",
            font_size=12,
            font_name="Arial",
            is_bold=False,
            is_italic=False,
            bbox=(72, 114, 200, 126),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )

        # Second block starts with #, should not merge.
        assert converter._should_merge_lines(block1, block2, block1) is False

    def test_hash_lines_not_continued_in_list(self):
        """Test that lines starting with # are not merged as list continuation."""
        converter = PDFConverter()

        first_content = TextBlock(
            text="Start of list item",
            font_size=12,
            font_name="Arial",
            is_bold=False,
            is_italic=False,
            bbox=(85, 100, 200, 112),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )
        candidate = TextBlock(
            text="# This should not be merged",
            font_size=12,
            font_name="Arial",
            is_bold=False,
            is_italic=False,
            bbox=(85, 114, 300, 126),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )

        # Candidate starts with #, should not continue list.
        assert converter._should_continue_list_item(first_content, candidate, first_content) is False


class TestFormattingPreservationIntegration:
    """Integration tests for formatting preservation using sample PDFs."""

    def test_sample2_bold_list_items_preserved(self):
        """Verify sample2.pdf bold list items are formatted correctly."""
        sample_pdf = FIXTURES_DIR / "sample2.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample2.pdf not available")

        converter = PDFConverter()
        markdown = converter.convert_file(sample_pdf)

        # Check for bold list items in the Typical conventions section.
        assert "- **Naming:**" in markdown or "- **Naming**" in markdown
        assert "- **Descriptions:**" in markdown or "- **Descriptions**" in markdown

    def test_sample2_sub_bullets_indented(self):
        """Verify sample2.pdf sub-bullets have indentation."""
        sample_pdf = FIXTURES_DIR / "sample2.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample2.pdf not available")

        converter = PDFConverter()
        markdown = converter.convert_file(sample_pdf)

        # Look for indented bullet lines (4 spaces for proper markdown nesting).
        lines = markdown.split("\n")
        indented_bullets = [l for l in lines if l.startswith("    - ")]

        # Should have multiple indented bullet items.
        assert len(indented_bullets) > 0, "No indented sub-bullets found"

    def test_sample2_hash_not_rendered_as_header(self):
        """Verify sample2.pdf shell comments are escaped, not headers."""
        sample_pdf = FIXTURES_DIR / "sample2.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample2.pdf not available")

        converter = PDFConverter()
        markdown = converter.convert_file(sample_pdf)

        # Look for escaped hash at start of line.
        lines = markdown.split("\n")
        escaped_hash_lines = [l for l in lines if l.startswith("\\#")]

        # Should have at least one escaped hash line.
        assert len(escaped_hash_lines) > 0, "No escaped hash lines found"

    def test_post_process_preserves_list_indentation(self):
        """Verify post-processing preserves leading whitespace for list items."""
        converter = PDFConverter()

        # Input with indented list items (4 spaces per level).
        markdown = "- Top level\n\n    - Indented item\n\n        - Deeply indented"

        result = converter._post_process_markdown(markdown)

        assert "    - Indented item" in result
        assert "        - Deeply indented" in result

    def test_arrow_continuation_merged(self):
        """Verify lines with arrow continuations are merged."""
        converter = PDFConverter()

        block1 = TextBlock(
            text="- feature/base-refactor",
            font_size=12,
            font_name="Arial",
            is_bold=False,
            is_italic=False,
            bbox=(72, 100, 200, 112),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )
        block2 = TextBlock(
            text="→ open PR1.",
            font_size=12,
            font_name="Arial",
            is_bold=False,
            is_italic=False,
            bbox=(72, 114, 200, 126),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )

        # Should merge because second block starts with arrow.
        assert converter._should_merge_lines(block1, block2, block1) is True

    def test_arrow_only_merged(self):
        """Verify standalone arrow is merged with adjacent content."""
        converter = PDFConverter()

        block1 = TextBlock(
            text="feature/add-endpoint",
            font_size=12,
            font_name="Arial",
            is_bold=False,
            is_italic=False,
            bbox=(72, 100, 200, 112),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )
        block2 = TextBlock(
            text="→",
            font_size=12,
            font_name="Arial",
            is_bold=False,
            is_italic=False,
            bbox=(200, 100, 210, 112),
            page_num=0,
            is_monospace=False,
            indent_level=0,
        )

        # Should merge because second block is just an arrow.
        assert converter._should_merge_lines(block1, block2, block1) is True

    def test_fix_orphaned_numbered_items(self):
        """Test that orphaned numbered items are detected and fixed."""
        converter = PDFConverter()

        markdown = """1. **First item**

    - Sub item

---

**Second item missing number**

    - Another sub

3. **Third item**"""

        result = converter._fix_orphaned_numbered_items(markdown)

        assert "2. **Second item missing number**" in result
        assert "1. **First item**" in result
        assert "3. **Third item**" in result

    def test_fix_orphaned_numbered_items_no_gap(self):
        """Test that properly numbered items are not modified."""
        converter = PDFConverter()

        markdown = """1. **First item**

2. **Second item**

3. **Third item**"""

        result = converter._fix_orphaned_numbered_items(markdown)

        assert result == markdown

    def test_post_process_document_fixes_punctuation(self):
        """Test that document post-processing fixes orphaned punctuation."""
        converter = PDFConverter()

        markdown = "Some text with orphaned punctuation , ."

        result = converter._post_process_document(markdown)

        assert ", ." not in result
        assert result.endswith(".")

    def test_sample2_numbered_list_complete(self):
        """Verify sample2.pdf numbered lists are complete with no gaps."""
        sample_pdf = FIXTURES_DIR / "sample2.pdf"
        if not sample_pdf.exists():
            pytest.skip("sample2.pdf not available")

        converter = PDFConverter()
        markdown = converter.convert_file(sample_pdf)

        # Check the "Why people use it" section has items 1, 2, 3, 4.
        lines = markdown.split("\n")
        found_items = []
        in_section = False

        for line in lines:
            if "Why people use it" in line:
                in_section = True
            elif in_section:
                if line.strip().startswith("#"):
                    break
                match = re.match(r"^(\d+)\.\s+\*\*", line.strip())
                if match:
                    found_items.append(int(match.group(1)))

        # Should have 1, 2, 3, 4 (no gaps).
        assert found_items == [1, 2, 3, 4], f"Found items: {found_items}"


class TestTableInfo:
    """Tests for TableInfo dataclass."""

    def test_table_info_creation(self):
        """Verify TableInfo can be created with all fields."""
        table = TableInfo(
            data=[["Header1", "Header2"], ["Row1Col1", "Row1Col2"]],
            bbox=(10, 20, 300, 100),
            page_num=0,
            row_count=2,
            col_count=2,
        )

        assert table.data == [["Header1", "Header2"], ["Row1Col1", "Row1Col2"]]
        assert table.bbox == (10, 20, 300, 100)
        assert table.page_num == 0
        assert table.row_count == 2
        assert table.col_count == 2

    def test_table_info_default_values(self):
        """Verify TableInfo has correct default values."""
        table = TableInfo(
            data=[["A", "B"]],
            bbox=(0, 0, 100, 50),
            page_num=0,
        )

        assert table.row_count == 0
        assert table.col_count == 0


class TestTableExtraction:
    """Tests for table extraction functionality."""

    def test_detect_tables_option_default(self):
        """Verify detect_tables option defaults to True."""
        options = ConversionOptions()
        assert options.detect_tables is True

    def test_detect_tables_option_disabled(self):
        """Verify detect_tables can be disabled."""
        options = ConversionOptions(detect_tables=False)
        assert options.detect_tables is False

    def test_table_to_markdown_simple(self):
        """Verify simple table converts to markdown correctly."""
        converter = PDFConverter()
        table = TableInfo(
            data=[["Name", "Age"], ["Alice", "30"], ["Bob", "25"]],
            bbox=(0, 0, 100, 100),
            page_num=0,
            row_count=3,
            col_count=2,
        )

        result = converter._table_to_markdown(table)

        assert "| Name | Age |" in result
        assert "| --- | --- |" in result
        assert "| Alice | 30 |" in result
        assert "| Bob | 25 |" in result

    def test_table_to_markdown_empty(self):
        """Verify empty table returns empty string."""
        converter = PDFConverter()
        table = TableInfo(
            data=[],
            bbox=(0, 0, 100, 100),
            page_num=0,
        )

        result = converter._table_to_markdown(table)

        assert result == ""

    def test_table_to_markdown_single_row(self):
        """Verify single row table (header only) works."""
        converter = PDFConverter()
        table = TableInfo(
            data=[["Col1", "Col2", "Col3"]],
            bbox=(0, 0, 100, 100),
            page_num=0,
            row_count=1,
            col_count=3,
        )

        result = converter._table_to_markdown(table)

        assert "| Col1 | Col2 | Col3 |" in result
        assert "| --- | --- | --- |" in result

    def test_table_to_markdown_escapes_pipes(self):
        """Verify pipe characters in cells are escaped."""
        converter = PDFConverter()
        table = TableInfo(
            data=[["Header"], ["Value | with pipe"]],
            bbox=(0, 0, 100, 100),
            page_num=0,
        )

        result = converter._table_to_markdown(table)

        assert r"Value \| with pipe" in result

    def test_table_to_markdown_handles_newlines(self):
        """Verify newlines in cells are converted to spaces."""
        converter = PDFConverter()
        table = TableInfo(
            data=[["Header"], ["Line1\nLine2"]],
            bbox=(0, 0, 100, 100),
            page_num=0,
        )

        result = converter._table_to_markdown(table)

        assert "Line1 Line2" in result
        assert "\n" not in result.split("\n")[2]

    def test_table_to_markdown_handles_empty_cells(self):
        """Verify empty cells are handled correctly."""
        converter = PDFConverter()
        table = TableInfo(
            data=[["A", "B"], ["", "Value"]],
            bbox=(0, 0, 100, 100),
            page_num=0,
        )

        result = converter._table_to_markdown(table)

        assert "|  | Value |" in result

    def test_table_to_markdown_pads_short_rows(self):
        """Verify rows with fewer columns than header are padded."""
        converter = PDFConverter()
        table = TableInfo(
            data=[["A", "B", "C"], ["Only", "Two"]],
            bbox=(0, 0, 100, 100),
            page_num=0,
        )

        result = converter._table_to_markdown(table)

        lines = result.split("\n")
        # Data row should have 3 pipe-separated sections.
        assert lines[2].count("|") == 4

    def test_escape_table_cell_none_handling(self):
        """Verify None cells are converted to empty strings."""
        converter = PDFConverter()

        result = converter._escape_table_cell("")
        assert result == ""

        result = converter._escape_table_cell(None)
        assert result == ""

    def test_escape_table_cell_normalizes_whitespace(self):
        """Verify multiple spaces are normalized."""
        converter = PDFConverter()

        result = converter._escape_table_cell("Too   many    spaces")
        assert result == "Too many spaces"

    def test_is_inside_table_center_point(self):
        """Verify text block detection uses center point."""
        converter = PDFConverter()
        tables = [
            TableInfo(
                data=[["A"]],
                bbox=(100, 100, 300, 200),
                page_num=0,
            )
        ]

        # Text block with center inside table.
        inside_bbox = (150, 140, 250, 160)
        assert converter._is_inside_table(inside_bbox, tables) is True

        # Text block with center outside table.
        outside_bbox = (0, 0, 50, 20)
        assert converter._is_inside_table(outside_bbox, tables) is False

    def test_is_inside_table_partial_overlap(self):
        """Verify partially overlapping text uses center point."""
        converter = PDFConverter()
        tables = [
            TableInfo(
                data=[["A"]],
                bbox=(100, 100, 300, 200),
                page_num=0,
            )
        ]

        # Text block partially overlapping but center outside.
        partial_bbox = (50, 140, 110, 160)  # Center at (80, 150).
        assert converter._is_inside_table(partial_bbox, tables) is False

        # Text block partially overlapping but center inside.
        partial_inside_bbox = (90, 140, 150, 160)  # Center at (120, 150).
        assert converter._is_inside_table(partial_inside_bbox, tables) is True

    def test_is_inside_table_no_tables(self):
        """Verify empty table list returns False."""
        converter = PDFConverter()

        result = converter._is_inside_table((0, 0, 100, 50), [])
        assert result is False

    def test_page_content_includes_tables(self):
        """Verify PageContent has tables field."""
        content = PageContent(page_num=0)

        assert hasattr(content, "tables")
        assert content.tables == []

    def test_page_content_with_tables(self):
        """Verify PageContent can store tables."""
        table = TableInfo(
            data=[["A", "B"]],
            bbox=(0, 0, 100, 50),
            page_num=0,
        )
        content = PageContent(page_num=0, tables=[table])

        assert len(content.tables) == 1
        assert content.tables[0].data == [["A", "B"]]


class TestTableExtractionIntegration:
    """Integration tests for table extraction with PDF files."""

    def test_extract_tables_with_mock_page(self):
        """Verify _extract_tables handles PyMuPDF table finder."""
        converter = PDFConverter()

        # Create mock table object.
        mock_table = MagicMock()
        mock_table.extract.return_value = [["H1", "H2"], ["V1", "V2"]]
        mock_table.bbox = (10, 20, 200, 100)
        mock_table.row_count = 2
        mock_table.col_count = 2

        # Create mock table finder.
        mock_finder = MagicMock()
        mock_finder.tables = [mock_table]

        # Create mock page.
        mock_page = MagicMock()
        mock_page.find_tables.return_value = mock_finder

        result = converter._extract_tables(mock_page, 0)

        assert len(result) == 1
        assert result[0].data == [["H1", "H2"], ["V1", "V2"]]
        assert result[0].bbox == (10, 20, 200, 100)
        assert result[0].row_count == 2
        assert result[0].col_count == 2

    def test_extract_tables_handles_none_cells(self):
        """Verify None cells are converted to empty strings."""
        converter = PDFConverter()

        mock_table = MagicMock()
        mock_table.extract.return_value = [["H1", None], [None, "V2"]]
        mock_table.bbox = (0, 0, 100, 50)
        mock_table.row_count = 2
        mock_table.col_count = 2

        mock_finder = MagicMock()
        mock_finder.tables = [mock_table]

        mock_page = MagicMock()
        mock_page.find_tables.return_value = mock_finder

        result = converter._extract_tables(mock_page, 0)

        assert result[0].data == [["H1", ""], ["", "V2"]]

    def test_extract_tables_handles_exception(self):
        """Verify table extraction gracefully handles errors."""
        converter = PDFConverter()

        mock_page = MagicMock()
        mock_page.find_tables.side_effect = Exception("Table extraction failed")

        result = converter._extract_tables(mock_page, 0)

        assert result == []

    def test_extract_tables_skips_empty_tables(self):
        """Verify empty tables are not included."""
        converter = PDFConverter()

        mock_table = MagicMock()
        mock_table.extract.return_value = []
        mock_table.bbox = (0, 0, 100, 50)

        mock_finder = MagicMock()
        mock_finder.tables = [mock_table]

        mock_page = MagicMock()
        mock_page.find_tables.return_value = mock_finder

        result = converter._extract_tables(mock_page, 0)

        assert result == []

    def test_tables_disabled_skips_extraction(self):
        """Verify table extraction is skipped when disabled."""
        options = ConversionOptions(detect_tables=False)
        converter = PDFConverter(options)

        # Create a mock PDF with text only.
        mock_text_dict = {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {
                            "spans": [{"text": "Test text", "size": 12, "font": "Arial", "flags": 0}],
                            "bbox": (0, 0, 100, 20),
                        }
                    ],
                }
            ]
        }

        with patch.object(converter, "_doc") as mock_doc:
            mock_page = MagicMock()
            mock_page.get_text.return_value = mock_text_dict
            mock_page.get_links.return_value = []
            mock_page.get_images.return_value = []
            mock_page.find_tables = MagicMock()
            mock_doc.__getitem__ = MagicMock(return_value=mock_page)

            content = converter._extract_page_content(0, "test")

            # find_tables should not be called.
            mock_page.find_tables.assert_not_called()
            assert content.tables == []

