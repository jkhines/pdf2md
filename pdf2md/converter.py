"""Core PDF to Markdown conversion logic."""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

import fitz  # PyMuPDF


@dataclass
class ConversionOptions:
    """Configuration options for PDF to Markdown conversion."""

    extract_images: bool = True
    image_output_dir: Path | None = None
    image_format: str = "png"
    image_dpi: int = 150
    preserve_hyperlinks: bool = True
    detect_headings: bool = True
    detect_lists: bool = True
    detect_bold_italic: bool = True
    heading_font_size_threshold: float = 14.0
    page_separator: str = "\n\n---\n\n"
    min_heading_size_ratio: float = 1.2
    line_merge_threshold: float = 5.0  # Max vertical gap to merge lines into paragraph.


@dataclass
class TextBlock:
    """Represents a block of text with formatting metadata."""

    text: str
    font_size: float
    font_name: str
    is_bold: bool
    is_italic: bool
    bbox: tuple[float, float, float, float]
    page_num: int
    is_monospace: bool = False
    indent_level: int = 0  # 0 = top-level, 1 = first indent, etc.


@dataclass
class Link:
    """Represents a hyperlink in the PDF."""

    text: str
    url: str
    bbox: tuple[float, float, float, float]
    page_num: int


@dataclass
class ImageInfo:
    """Represents an extracted image."""

    xref: int
    bbox: tuple[float, float, float, float]
    page_num: int
    filename: str = ""
    width: int = 0
    height: int = 0


@dataclass
class PageContent:
    """Holds all extracted content from a single page."""

    page_num: int
    text_blocks: list[TextBlock] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    images: list[ImageInfo] = field(default_factory=list)
    base_font_size: float = 12.0


class PDFConverter:
    """Converts PDF documents to Markdown format."""

    # Patterns for standalone list markers.
    BULLET_PATTERN = re.compile(r"^[•●○◦▪▸►\-–—]$")
    NUMBER_PATTERN = re.compile(r"^(\d+)[.):]\s*$")

    def __init__(self, options: ConversionOptions | None = None):
        """Initialize the converter with optional configuration.

        Args:
            options: Conversion options. Uses defaults if not provided.
        """
        self.options = options or ConversionOptions()
        self._doc: fitz.Document | None = None
        self._image_counter = 0

    def convert_file(self, pdf_path: str | Path, output_path: str | Path | None = None) -> str:
        """Convert a PDF file to Markdown.

        Args:
            pdf_path: Path to the input PDF file.
            output_path: Optional path to write the Markdown output.

        Returns:
            The generated Markdown content as a string.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        with open(pdf_path, "rb") as f:
            markdown = self.convert_stream(f, source_name=pdf_path.stem)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown, encoding="utf-8")

        return markdown

    def convert_stream(self, stream: BinaryIO, source_name: str = "document") -> str:
        """Convert a PDF from a binary stream to Markdown.

        Args:
            stream: Binary stream containing PDF data.
            source_name: Name to use for image filenames.

        Returns:
            The generated Markdown content as a string.
        """
        pdf_data = stream.read()
        return self.convert_bytes(pdf_data, source_name)

    def convert_bytes(self, pdf_data: bytes, source_name: str = "document") -> str:
        """Convert PDF bytes to Markdown.

        Args:
            pdf_data: Raw PDF bytes.
            source_name: Name to use for image filenames.

        Returns:
            The generated Markdown content as a string.
        """
        self._doc = fitz.open(stream=pdf_data, filetype="pdf")
        self._image_counter = 0

        try:
            pages_content = []
            for page_num in range(len(self._doc)):
                page_content = self._extract_page_content(page_num, source_name)
                pages_content.append(page_content)

            markdown_pages = []
            for page_content in pages_content:
                page_md = self._render_page_markdown(page_content)
                if page_md.strip():
                    markdown_pages.append(page_md)

            # Join pages and apply document-level post-processing.
            full_markdown = self.options.page_separator.join(markdown_pages)
            return self._post_process_document(full_markdown)
        finally:
            self._doc.close()
            self._doc = None

    def _extract_page_content(self, page_num: int, source_name: str) -> PageContent:
        """Extract all content from a single page.

        Args:
            page_num: Zero-based page index.
            source_name: Base name for extracted images.

        Returns:
            PageContent object with all extracted elements.
        """
        page = self._doc[page_num]
        content = PageContent(page_num=page_num)

        # Extract text blocks with formatting.
        raw_blocks = self._extract_text_blocks(page, page_num)

        # Merge consecutive lines into paragraphs.
        content.text_blocks = self._merge_text_blocks(raw_blocks)

        # Calculate base font size for heading detection.
        if content.text_blocks:
            sizes = [b.font_size for b in content.text_blocks if b.text.strip()]
            if sizes:
                content.base_font_size = self._calculate_median(sizes)

        # Extract hyperlinks.
        if self.options.preserve_hyperlinks:
            content.links = self._extract_links(page, page_num)

        # Extract images.
        if self.options.extract_images:
            content.images = self._extract_images(page, page_num, source_name)

        return content

    def _extract_text_blocks(self, page: fitz.Page, page_num: int) -> list[TextBlock]:
        """Extract text blocks with formatting information.

        Args:
            page: PyMuPDF page object.
            page_num: Page number for reference.

        Returns:
            List of TextBlock objects.
        """
        blocks = []
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        # Collect all x-positions to determine indentation levels.
        all_x_positions = []
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                bbox = line.get("bbox", (0, 0, 0, 0))
                all_x_positions.append(bbox[0])

        # Determine indentation thresholds.
        indent_thresholds = self._calculate_indent_thresholds(all_x_positions)

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # Skip non-text blocks.
                continue

            for line in block.get("lines", []):
                line_text_parts = []
                line_font_size = 0
                line_font_name = ""
                is_bold = False
                is_italic = False
                is_monospace = False

                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text:
                        continue

                    font_size = span.get("size", 12)
                    font_name = span.get("font", "")
                    flags = span.get("flags", 0)

                    # Detect bold and italic from font flags.
                    span_bold = bool(flags & 2 ** 4) or "bold" in font_name.lower()
                    span_italic = bool(flags & 2 ** 1) or "italic" in font_name.lower() or "oblique" in font_name.lower()

                    # Detect monospace fonts.
                    span_monospace = self._is_monospace_font(font_name)

                    line_text_parts.append(text)
                    line_font_size = max(line_font_size, font_size)
                    line_font_name = font_name
                    is_bold = is_bold or span_bold
                    is_italic = is_italic or span_italic
                    is_monospace = is_monospace or span_monospace

                line_text = "".join(line_text_parts)
                if line_text.strip():
                    bbox = line.get("bbox", (0, 0, 0, 0))
                    indent_level = self._get_indent_level(bbox[0], indent_thresholds)
                    blocks.append(
                        TextBlock(
                            text=line_text,
                            font_size=line_font_size,
                            font_name=line_font_name,
                            is_bold=is_bold,
                            is_italic=is_italic,
                            bbox=tuple(bbox),
                            page_num=page_num,
                            is_monospace=is_monospace,
                            indent_level=indent_level,
                        )
                    )

        return blocks

    def _is_monospace_font(self, font_name: str) -> bool:
        """Detect if a font is monospace.

        Args:
            font_name: Font name string.

        Returns:
            True if the font appears to be monospace.
        """
        font_lower = font_name.lower()
        monospace_indicators = [
            "mono", "courier", "consolas", "menlo", "monaco", "inconsolata",
            "source code", "fira code", "jetbrains", "hack", "ubuntu mono",
            "dejavu sans mono", "liberation mono", "fixed", "terminal",
            "lucida console", "sf mono", "andale mono", "cascadia",
        ]
        return any(indicator in font_lower for indicator in monospace_indicators)


    def _calculate_indent_thresholds(self, x_positions: list[float]) -> list[float]:
        """Calculate indentation level thresholds from x-positions.

        Args:
            x_positions: List of x-positions of text blocks.

        Returns:
            Sorted list of threshold x-positions for each indent level.
        """
        if not x_positions:
            return []

        # Find clusters of x-positions by detecting significant gaps.
        sorted_positions = sorted(set(x_positions))
        if len(sorted_positions) <= 1:
            return sorted_positions

        # Use a gap-based approach: any gap > 20 units starts a new cluster.
        clusters = []
        current_cluster = [sorted_positions[0]]

        for pos in sorted_positions[1:]:
            # Check gap from the cluster's average, not just the last item.
            cluster_avg = sum(current_cluster) / len(current_cluster)
            if pos - cluster_avg > 25:  # Significant gap indicates new indent level.
                clusters.append(cluster_avg)
                current_cluster = [pos]
            else:
                current_cluster.append(pos)

        if current_cluster:
            clusters.append(sum(current_cluster) / len(current_cluster))

        return sorted(clusters)

    def _get_indent_level(self, x_pos: float, thresholds: list[float]) -> int:
        """Determine the indentation level based on x-position.

        Args:
            x_pos: X-position of the text block.
            thresholds: List of threshold x-positions.

        Returns:
            Indentation level (0, 1, 2, etc.).
        """
        if not thresholds:
            return 0

        # Find which threshold cluster this position is closest to.
        min_dist = float("inf")
        best_level = 0
        for i, threshold in enumerate(thresholds):
            dist = abs(x_pos - threshold)
            if dist < min_dist:
                min_dist = dist
                best_level = i

        return best_level

    def _merge_text_blocks(self, blocks: list[TextBlock]) -> list[TextBlock]:
        """Merge consecutive text blocks into paragraphs.

        This handles:
        - Wrapped lines that should be joined
        - Bullet points separated from their content
        - Numbered list items separated from their content

        Args:
            blocks: List of raw text blocks.

        Returns:
            List of merged text blocks.
        """
        if not blocks:
            return []

        # Sort blocks by vertical position, then horizontal.
        sorted_blocks = sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))

        merged = []
        i = 0

        while i < len(sorted_blocks):
            current = sorted_blocks[i]
            current_text = current.text.strip()

            # Check if current is a standalone bullet marker.
            if self.BULLET_PATTERN.match(current_text):
                # Look for content to join with.
                if i + 1 < len(sorted_blocks):
                    next_block = sorted_blocks[i + 1]
                    if self._should_join_bullet(current, next_block):
                        # Merge bullet with next block, then continue merging continuations.
                        merged_text = f"- {next_block.text.strip()}"
                        merged_bbox = self._merge_bboxes(current.bbox, next_block.bbox)
                        blocks_consumed = 2
                        merged_is_bold = next_block.is_bold
                        merged_is_italic = next_block.is_italic
                        merged_is_monospace = next_block.is_monospace

                        # Continue merging subsequent continuation lines.
                        for j in range(i + 2, len(sorted_blocks)):
                            candidate = sorted_blocks[j]
                            if self._should_continue_list_item(next_block, candidate, sorted_blocks[j - 1]):
                                if merged_text.endswith("-"):
                                    merged_text = merged_text[:-1] + candidate.text.strip()
                                else:
                                    merged_text = merged_text + " " + candidate.text.strip()
                                merged_bbox = self._merge_bboxes(merged_bbox, candidate.bbox)
                                blocks_consumed += 1
                            else:
                                break

                        merged_block = TextBlock(
                            text=merged_text,
                            font_size=next_block.font_size,
                            font_name=next_block.font_name,
                            is_bold=merged_is_bold,
                            is_italic=merged_is_italic,
                            bbox=merged_bbox,
                            page_num=current.page_num,
                            is_monospace=merged_is_monospace,
                            indent_level=current.indent_level,  # Use bullet's indent level.
                        )
                        merged.append(merged_block)
                        i += blocks_consumed
                        continue
                # Standalone bullet with no content - skip it.
                i += 1
                continue

            # Check if current is a standalone number marker.
            number_match = self.NUMBER_PATTERN.match(current_text)
            if number_match:
                # Look for content to join with.
                if i + 1 < len(sorted_blocks):
                    next_block = sorted_blocks[i + 1]
                    if self._should_join_number(current, next_block):
                        # Merge number with next block, then continue merging continuations.
                        num = number_match.group(1)
                        merged_text = f"{num}. {next_block.text.strip()}"
                        merged_bbox = self._merge_bboxes(current.bbox, next_block.bbox)
                        blocks_consumed = 2
                        merged_is_bold = next_block.is_bold
                        merged_is_italic = next_block.is_italic
                        merged_is_monospace = next_block.is_monospace

                        # Continue merging subsequent continuation lines.
                        for j in range(i + 2, len(sorted_blocks)):
                            candidate = sorted_blocks[j]
                            if self._should_continue_list_item(next_block, candidate, sorted_blocks[j - 1]):
                                if merged_text.endswith("-"):
                                    merged_text = merged_text[:-1] + candidate.text.strip()
                                else:
                                    merged_text = merged_text + " " + candidate.text.strip()
                                merged_bbox = self._merge_bboxes(merged_bbox, candidate.bbox)
                                blocks_consumed += 1
                            else:
                                break

                        merged_block = TextBlock(
                            text=merged_text,
                            font_size=next_block.font_size,
                            font_name=next_block.font_name,
                            is_bold=merged_is_bold,
                            is_italic=merged_is_italic,
                            bbox=merged_bbox,
                            page_num=current.page_num,
                            is_monospace=merged_is_monospace,
                            indent_level=current.indent_level,  # Use number's indent level.
                        )
                        merged.append(merged_block)
                        i += blocks_consumed
                        continue
                # Standalone number with no content - skip it.
                i += 1
                continue

            # Try to merge with subsequent lines (paragraph continuation).
            merged_block = self._merge_paragraph_lines(sorted_blocks, i)
            merged.append(merged_block)

            # Skip all the blocks that were merged.
            blocks_merged = self._count_merged_blocks(sorted_blocks, i, merged_block)
            i += blocks_merged

        return merged

    def _should_continue_list_item(self, first_content: TextBlock, candidate: TextBlock, prev: TextBlock) -> bool:
        """Determine if a candidate block should continue a list item.

        Args:
            first_content: The first content block of the list item.
            candidate: The candidate block to potentially merge.
            prev: The previous block in the sequence.

        Returns:
            True if the candidate should be merged into the list item.
        """
        # Don't merge if on different pages.
        if first_content.page_num != candidate.page_num:
            return False

        candidate_text = candidate.text.strip()

        # Don't merge if candidate starts with # (shell comment or similar).
        if candidate_text.startswith("#"):
            return False

        # Always merge if candidate is an arrow or starts with one (continuation).
        if candidate_text == "→" or candidate_text.startswith("→ "):
            return True

        # Don't merge if candidate is a standalone bullet or number.
        if self.BULLET_PATTERN.match(candidate_text):
            return False
        if self.NUMBER_PATTERN.match(candidate_text):
            return False

        # Don't merge if candidate starts a new list item.
        if re.match(r"^[•●○◦▪▸►\-–—]\s+", candidate_text):
            return False
        if re.match(r"^\d+[.)]\s+", candidate_text):
            return False

        # Check vertical proximity - blocks should be close.
        prev_bottom = prev.bbox[3]
        candidate_top = candidate.bbox[1]
        line_height = prev.bbox[3] - prev.bbox[1]
        vertical_gap = candidate_top - prev_bottom

        # Allow gap up to line height plus threshold.
        max_gap = line_height + self.options.line_merge_threshold
        if vertical_gap > max_gap:
            return False

        # Check if font sizes are reasonably similar (within 50% for list continuations).
        size_ratio = min(first_content.font_size, candidate.font_size) / max(first_content.font_size, candidate.font_size) if max(first_content.font_size, candidate.font_size) > 0 else 1
        if size_ratio < 0.5:
            return False

        return True

    def _merge_paragraph_lines(self, blocks: list[TextBlock], start_idx: int) -> TextBlock:
        """Merge consecutive lines that form a paragraph.

        Args:
            blocks: List of all text blocks.
            start_idx: Index of the first block to consider.

        Returns:
            A merged TextBlock containing the full paragraph.
        """
        current = blocks[start_idx]
        merged_text = current.text.strip()
        merged_bbox = current.bbox
        end_idx = start_idx

        for j in range(start_idx + 1, len(blocks)):
            next_block = blocks[j]

            if not self._should_merge_lines(current, next_block, blocks[end_idx]):
                break

            # Join with space if current line doesn't end with hyphen.
            if merged_text.endswith("-"):
                # Remove hyphen and join directly (hyphenated word).
                merged_text = merged_text[:-1] + next_block.text.strip()
            else:
                merged_text = merged_text + " " + next_block.text.strip()

            merged_bbox = self._merge_bboxes(merged_bbox, next_block.bbox)
            end_idx = j

        return TextBlock(
            text=merged_text,
            font_size=current.font_size,
            font_name=current.font_name,
            is_bold=current.is_bold,
            is_italic=current.is_italic,
            bbox=merged_bbox,
            page_num=current.page_num,
            is_monospace=current.is_monospace,
            indent_level=current.indent_level,
        )

    def _count_merged_blocks(self, blocks: list[TextBlock], start_idx: int, merged: TextBlock) -> int:
        """Count how many blocks were merged into the given merged block.

        Args:
            blocks: List of all text blocks.
            start_idx: Starting index.
            merged: The merged text block.

        Returns:
            Number of original blocks that were merged.
        """
        count = 1
        current = blocks[start_idx]

        for j in range(start_idx + 1, len(blocks)):
            next_block = blocks[j]
            if not self._should_merge_lines(current, next_block, blocks[j - 1]):
                break
            count += 1

        return count

    def _should_merge_lines(self, first: TextBlock, second: TextBlock, prev: TextBlock) -> bool:
        """Determine if two text blocks should be merged as paragraph continuation.

        Args:
            first: The first (starting) block of the potential paragraph.
            second: The candidate block to merge.
            prev: The previous block (could be same as first or an intermediate block).

        Returns:
            True if the blocks should be merged.
        """
        # Don't merge if on different pages.
        if first.page_num != second.page_num:
            return False

        first_text = first.text.strip()
        second_text = second.text.strip()

        # Don't merge if either block starts with # (shell comment or similar).
        if first_text.startswith("#") or second_text.startswith("#"):
            return False

        # Always merge if second block is just a continuation arrow or starts with one.
        if second_text == "→" or second_text.startswith("→ "):
            return True

        # Always merge if first block ends with an arrow (continuation).
        if first_text.endswith("→"):
            return True

        # Don't merge if second block is a standalone bullet or number.
        if self.BULLET_PATTERN.match(second_text):
            return False
        if self.NUMBER_PATTERN.match(second_text):
            return False

        # Don't merge if second block starts a new list item.
        if re.match(r"^[•●○◦▪▸►\-–—]\s+", second_text):
            return False
        if re.match(r"^\d+[.)]\s+", second_text):
            return False

        # Check vertical proximity - blocks should be close.
        prev_bottom = prev.bbox[3]
        second_top = second.bbox[1]
        line_height = prev.bbox[3] - prev.bbox[1]
        vertical_gap = second_top - prev_bottom

        # Allow gap up to line height plus threshold.
        max_gap = line_height + self.options.line_merge_threshold
        if vertical_gap > max_gap:
            return False

        # Check if font sizes are similar (within 20%).
        size_ratio = min(first.font_size, second.font_size) / max(first.font_size, second.font_size) if max(first.font_size, second.font_size) > 0 else 1
        if size_ratio < 0.8:
            return False

        # Check horizontal alignment - second should not be significantly indented differently.
        x_diff = abs(first.bbox[0] - second.bbox[0])
        if x_diff > 50:  # Allow some tolerance for wrapped lines.
            return False

        # Don't merge headings with regular text.
        if first.is_bold != second.is_bold:
            # If first is bold and short, likely a heading - don't merge.
            if first.is_bold and len(first.text.strip()) < 100:
                return False

        return True

    def _should_join_bullet(self, bullet: TextBlock, content: TextBlock) -> bool:
        """Determine if a bullet marker should be joined with content.

        Args:
            bullet: The bullet marker block.
            content: The potential content block.

        Returns:
            True if they should be joined.
        """
        if bullet.page_num != content.page_num:
            return False

        # Check vertical proximity.
        bullet_bottom = bullet.bbox[3]
        content_top = content.bbox[1]
        vertical_gap = content_top - bullet_bottom

        # Bullet and content should be on same line or very close.
        line_height = bullet.bbox[3] - bullet.bbox[1]
        if vertical_gap > line_height + 5:
            return False

        # Content should be to the right of or below the bullet.
        return True

    def _should_join_number(self, number: TextBlock, content: TextBlock) -> bool:
        """Determine if a number marker should be joined with content.

        Args:
            number: The number marker block.
            content: The potential content block.

        Returns:
            True if they should be joined.
        """
        return self._should_join_bullet(number, content)

    def _merge_bboxes(self, bbox1: tuple, bbox2: tuple) -> tuple[float, float, float, float]:
        """Merge two bounding boxes into one encompassing both.

        Args:
            bbox1: First bounding box.
            bbox2: Second bounding box.

        Returns:
            Combined bounding box.
        """
        return (
            min(bbox1[0], bbox2[0]),
            min(bbox1[1], bbox2[1]),
            max(bbox1[2], bbox2[2]),
            max(bbox1[3], bbox2[3]),
        )

    def _extract_links(self, page: fitz.Page, page_num: int) -> list[Link]:
        """Extract hyperlinks from a page.

        Args:
            page: PyMuPDF page object.
            page_num: Page number for reference.

        Returns:
            List of Link objects.
        """
        links = []
        for link in page.get_links():
            uri = link.get("uri", "")
            if not uri:
                continue

            bbox = link.get("from", (0, 0, 0, 0))
            # Extract text at the link location.
            rect = fitz.Rect(bbox)
            text = page.get_text("text", clip=rect).strip()
            # Normalize whitespace in link text.
            text = " ".join(text.split())

            if text:
                links.append(
                    Link(
                        text=text,
                        url=uri,
                        bbox=tuple(bbox),
                        page_num=page_num,
                    )
                )

        return links

    def _extract_images(self, page: fitz.Page, page_num: int, source_name: str) -> list[ImageInfo]:
        """Extract images from a page and save them to disk.

        Args:
            page: PyMuPDF page object.
            page_num: Page number for reference.
            source_name: Base name for image files.

        Returns:
            List of ImageInfo objects.
        """
        images = []
        image_list = page.get_images(full=True)

        for img_index, img in enumerate(image_list):
            xref = img[0]

            try:
                base_image = self._doc.extract_image(xref)
                if not base_image:
                    continue

                image_bytes = base_image["image"]
                image_ext = base_image.get("ext", self.options.image_format)
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)

                # Generate unique filename.
                self._image_counter += 1
                img_hash = hashlib.md5(image_bytes).hexdigest()[:8]
                filename = f"{source_name}_p{page_num + 1}_img{self._image_counter}_{img_hash}.{image_ext}"

                # Save image if output directory is specified.
                if self.options.image_output_dir:
                    img_path = Path(self.options.image_output_dir) / filename
                    img_path.parent.mkdir(parents=True, exist_ok=True)
                    img_path.write_bytes(image_bytes)

                # Get image position on page.
                bbox = self._get_image_bbox(page, xref)

                images.append(
                    ImageInfo(
                        xref=xref,
                        bbox=bbox,
                        page_num=page_num,
                        filename=filename,
                        width=width,
                        height=height,
                    )
                )
            except Exception:
                # Skip images that can't be extracted.
                continue

        return images

    def _get_image_bbox(self, page: fitz.Page, xref: int) -> tuple[float, float, float, float]:
        """Get the bounding box of an image on the page.

        Args:
            page: PyMuPDF page object.
            xref: Image reference number.

        Returns:
            Bounding box as (x0, y0, x1, y1).
        """
        for img in page.get_images(full=True):
            if img[0] == xref:
                # Try to get the transformation matrix for precise positioning.
                try:
                    img_rects = page.get_image_rects(xref)
                    if img_rects:
                        rect = img_rects[0]
                        return (rect.x0, rect.y0, rect.x1, rect.y1)
                except Exception:
                    pass
        return (0, 0, 0, 0)

    def _render_page_markdown(self, content: PageContent) -> str:
        """Render extracted page content as Markdown.

        Args:
            content: PageContent object with all page elements.

        Returns:
            Markdown string for the page.
        """
        # Build a map of link bboxes to URLs for quick lookup.
        link_map = {}
        for link in content.links:
            link_map[link.bbox] = link

        # Collect all elements with their vertical positions for ordering.
        elements: list[tuple[float, str]] = []

        # Process text blocks.
        for block in content.text_blocks:
            y_pos = block.bbox[1]
            md_text = self._format_text_block(block, content.base_font_size, link_map)
            if md_text.strip():
                elements.append((y_pos, md_text))

        # Process images.
        for img in content.images:
            y_pos = img.bbox[1]
            if self.options.image_output_dir:
                img_path = Path(self.options.image_output_dir) / img.filename
                md_img = f"![Image]({img_path})"
            else:
                md_img = f"![Image {img.filename}]()"
            elements.append((y_pos, md_img))

        # Sort by vertical position.
        elements.sort(key=lambda x: x[0])

        # Combine into markdown.
        lines = [el[1] for el in elements]
        return self._post_process_markdown("\n\n".join(lines))

    def _format_text_block(self, block: TextBlock, base_font_size: float, link_map: dict) -> str:
        """Format a text block as Markdown.

        Args:
            block: TextBlock to format.
            base_font_size: Base font size for heading detection.
            link_map: Map of bounding boxes to Link objects.

        Returns:
            Formatted Markdown string.
        """
        text = block.text.strip()
        if not text:
            return ""

        # Check if this is monospace text (actual code font).
        if block.is_monospace:
            # Format as code block.
            return self._format_code_block(text, block.indent_level)

        # Escape leading # to prevent markdown header interpretation.
        if text.startswith("#"):
            text = "\\" + text

        # Check if this text block overlaps with a link.
        text = self._apply_links(text, block.bbox, link_map)

        # Detect headings based on font size (but not for monospace/code).
        if self.options.detect_headings and not block.is_monospace:
            heading_level = self._detect_heading_level(block.font_size, base_font_size)
            if heading_level:
                # Remove any existing markdown formatting for clean heading.
                clean_text = text
                return f"{'#' * heading_level} {clean_text}"

        # Check if this is a list item.
        is_list_item = text.startswith("-") or re.match(r"^\d+\.", text)

        # Apply bold/italic formatting.
        if self.options.detect_bold_italic:
            if is_list_item:
                # For list items, apply bold/italic to the content after the marker.
                text = self._format_list_item_with_style(text, block.is_bold, block.is_italic)
            elif not text.startswith("["):
                # Don't double-wrap if text already has markdown links.
                if block.is_bold and block.is_italic:
                    text = f"***{text}***"
                elif block.is_bold:
                    text = f"**{text}**"
                elif block.is_italic:
                    text = f"*{text}*"

        # Detect list items (for items that weren't already merged).
        if self.options.detect_lists:
            text = self._detect_list_item(text)

        # Apply indentation for nested list items.
        # Use 4 spaces per level for better compatibility with markdown parsers.
        if block.indent_level > 0 and is_list_item:
            indent = "    " * block.indent_level
            text = indent + text

        return text

    def _format_code_block(self, text: str, indent_level: int) -> str:
        """Format text as a code block or inline code.

        Args:
            text: The code text.
            indent_level: Indentation level.

        Returns:
            Formatted code markdown.
        """
        # Use inline code backticks for single-line code.
        indent = "    " * indent_level
        return f"{indent}`{text}`"

    def _format_list_item_with_style(self, text: str, is_bold: bool, is_italic: bool) -> str:
        """Apply bold/italic styling to list item content.

        Args:
            text: List item text (e.g., "- Item content" or "1. Item content").
            is_bold: Whether the content is bold.
            is_italic: Whether the content is italic.

        Returns:
            List item with styled content.
        """
        # Extract the list marker and content.
        bullet_match = re.match(r"^(-\s*)(.*)$", text)
        number_match = re.match(r"^(\d+\.\s*)(.*)$", text)

        if bullet_match:
            marker = bullet_match.group(1)
            content = bullet_match.group(2)
        elif number_match:
            marker = number_match.group(1)
            content = number_match.group(2)
        else:
            return text  # Not a recognized list item.

        # Apply formatting to content.
        if is_bold and is_italic:
            content = f"***{content}***"
        elif is_bold:
            content = f"**{content}**"
        elif is_italic:
            content = f"*{content}*"

        return f"{marker}{content}"

    def _apply_links(self, text: str, text_bbox: tuple, link_map: dict) -> str:
        """Apply hyperlink formatting if the text overlaps with a link.

        Args:
            text: Original text.
            text_bbox: Bounding box of the text.
            link_map: Map of bounding boxes to Link objects.

        Returns:
            Text with link formatting applied if applicable.
        """
        for link_bbox, link in link_map.items():
            if self._bboxes_overlap(text_bbox, link_bbox):
                link_text_normalized = " ".join(link.text.split())
                text_normalized = " ".join(text.split())

                # If the normalized text matches the link text, format as link.
                if text_normalized == link_text_normalized:
                    return f"[{text}]({link.url})"

                # If link text is contained in the text, replace that portion.
                if link.text in text:
                    return text.replace(link.text, f"[{link.text}]({link.url})")

                # Try normalized matching for partial overlaps.
                if link_text_normalized in text_normalized:
                    return f"[{text}]({link.url})"

        return text

    def _bboxes_overlap(self, bbox1: tuple, bbox2: tuple) -> bool:
        """Check if two bounding boxes overlap.

        Args:
            bbox1: First bounding box (x0, y0, x1, y1).
            bbox2: Second bounding box (x0, y0, x1, y1).

        Returns:
            True if the boxes overlap.
        """
        x0_1, y0_1, x1_1, y1_1 = bbox1
        x0_2, y0_2, x1_2, y1_2 = bbox2

        return not (x1_1 < x0_2 or x1_2 < x0_1 or y1_1 < y0_2 or y1_2 < y0_1)

    def _detect_heading_level(self, font_size: float, base_font_size: float) -> int | None:
        """Detect heading level based on font size.

        Args:
            font_size: Font size of the text.
            base_font_size: Base font size of the document.

        Returns:
            Heading level (1-6) or None if not a heading.
        """
        if font_size < self.options.heading_font_size_threshold:
            return None

        ratio = font_size / base_font_size if base_font_size > 0 else 1.0

        if ratio < self.options.min_heading_size_ratio:
            return None

        if ratio >= 2.0:
            return 1
        elif ratio >= 1.7:
            return 2
        elif ratio >= 1.4:
            return 3
        elif ratio >= 1.2:
            return 4
        else:
            return None

    def _detect_list_item(self, text: str) -> str:
        """Detect and format list items.

        Args:
            text: Text to check for list patterns.

        Returns:
            Formatted text with list markers if applicable.
        """
        # Already formatted as list item.
        if text.startswith("- ") or re.match(r"^\d+\. ", text):
            return text

        # Numbered lists.
        numbered_match = re.match(r"^(\d+)[.)]\s+(.+)$", text, re.DOTALL)
        if numbered_match:
            number = numbered_match.group(1)
            content = numbered_match.group(2)
            return f"{number}. {content}"

        # Bullet points.
        bullet_match = re.match(r"^[•●○◦▪▸►\-–—]\s+(.+)$", text, re.DOTALL)
        if bullet_match:
            content = bullet_match.group(1)
            return f"- {content}"

        return text

    def _post_process_markdown(self, markdown: str) -> str:
        """Clean up and normalize the generated Markdown.

        Args:
            markdown: Raw Markdown content.

        Returns:
            Cleaned Markdown content.
        """
        # Remove excessive blank lines.
        markdown = re.sub(r"\n{4,}", "\n\n\n", markdown)

        # Fix spacing around headings.
        markdown = re.sub(r"(^#{1,6} .+)(\n)([^#\n])", r"\1\n\n\3", markdown, flags=re.MULTILINE)

        # Normalize whitespace in lines.
        lines = markdown.split("\n")
        cleaned_lines = []
        for line in lines:
            # Collapse multiple spaces within lines (but preserve markdown structure).
            # Preserve leading whitespace for indented list items.
            if not line.startswith("```") and not line.startswith("    "):
                # Capture leading whitespace before normalizing.
                leading_ws = ""
                stripped = line.lstrip()
                if stripped.startswith("-") or re.match(r"^\d+\.", stripped):
                    leading_ws = line[: len(line) - len(stripped)]
                line = leading_ws + " ".join(stripped.split())
            cleaned_lines.append(line.rstrip())
        markdown = "\n".join(cleaned_lines)

        return markdown.strip()

    def _post_process_document(self, markdown: str) -> str:
        """Apply document-level post-processing after pages are joined.

        Args:
            markdown: Complete markdown document.

        Returns:
            Post-processed markdown.
        """
        # Fix orphaned punctuation.
        markdown = re.sub(r"\s*,\s*\.\s*$", ".", markdown, flags=re.MULTILINE)
        markdown = re.sub(r"\s*,\s*,\s*,\s*\.", ".", markdown, flags=re.MULTILINE)

        # Fix cross-page orphaned numbered list items.
        markdown = self._fix_orphaned_numbered_items(markdown)

        return markdown

    def _fix_orphaned_numbered_items(self, markdown: str) -> str:
        """Fix numbered list items that were split across pages.

        Detects patterns like:
        - A bold paragraph that should be a numbered list item
        - When preceded by numbered items 1, 3, 4... (missing 2)

        Args:
            markdown: Markdown content.

        Returns:
            Fixed markdown content.
        """
        lines = markdown.split("\n")
        result_lines = []
        i = 0

        # Track the last seen numbered item to detect gaps.
        last_number = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Check if this is a numbered item.
            num_match = re.match(r"^(\d+)\.\s+", stripped)
            if num_match:
                current_num = int(num_match.group(1))
                last_number = current_num
                result_lines.append(line)
                i += 1
                continue

            # Check if this is a bold paragraph that might be a missing numbered item.
            # Pattern: **Bold text** with no number, but follows a gap in numbering.
            if stripped.startswith("**") and stripped.endswith("**") and last_number > 0:
                # Look ahead to see if next numbered item suggests this should be numbered.
                expected_next = last_number + 1
                handled = False

                # Check if a later line has a number that suggests we skipped one.
                for j in range(i + 1, min(i + 15, len(lines))):
                    future_match = re.match(r"^(\d+)\.\s+", lines[j].strip())
                    if future_match:
                        future_num = int(future_match.group(1))
                        if future_num > expected_next:
                            # There's a gap - this bold line should be numbered.
                            content = stripped[2:-2]  # Remove ** from both ends.
                            result_lines.append(f"{expected_next}. **{content}**")
                            last_number = expected_next
                            handled = True
                        break

                if not handled:
                    result_lines.append(line)
                i += 1
                continue

            result_lines.append(line)
            i += 1

        return "\n".join(result_lines)

    @staticmethod
    def _calculate_median(values: list[float]) -> float:
        """Calculate the median of a list of values.

        Args:
            values: List of numeric values.

        Returns:
            Median value.
        """
        if not values:
            return 0.0
        sorted_values = sorted(values)
        n = len(sorted_values)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_values[mid - 1] + sorted_values[mid]) / 2
        return sorted_values[mid]
