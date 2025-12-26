# pdf2md

A Python tool to convert Adobe PDF documents into Markdown format, preserving formatting, images, and hyperlinks.

## Features

- **Text Extraction**: Extracts text content while maintaining document structure
- **Heading Detection**: Automatically detects headings based on font size ratios
- **Bold/Italic Detection**: Preserves bold and italic formatting from PDF fonts
- **Hyperlink Preservation**: Extracts and converts hyperlinks to Markdown format
- **Image Extraction**: Extracts embedded images and saves them to disk
- **List Detection**: Recognizes numbered and bulleted lists with proper nesting
- **Nested List Support**: Detects indentation levels and preserves list hierarchy
- **Cross-Page Handling**: Merges list items and paragraphs split across page boundaries
- **Code/Monospace Detection**: Detects monospace fonts and formats as code blocks
- **Multi-page Support**: Handles multi-page documents with configurable page separators

## Installation

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Clone the repository
git clone https://github.com/jkhines/pdf2md.git
cd pdf2md

# Install dependencies
uv sync
```

## Usage

### Command Line Interface

```bash
# Convert a PDF to stdout
uv run pdf2md document.pdf

# Convert to a specific output file
uv run pdf2md document.pdf -o output.md

# Extract images to a directory
uv run pdf2md document.pdf -o output.md --images ./images

# Batch convert multiple files
uv run pdf2md *.pdf -o ./output/

# Convert with verbose output
uv run pdf2md document.pdf -v
```

### CLI Options

| Option | Description |
|--------|-------------|
| `-o, --output` | Output file or directory |
| `--images` | Directory to save extracted images |
| `--image-format` | Image format: `png`, `jpg`, `jpeg` (default: `png`) |
| `--image-dpi` | DPI for extracted images (default: `150`) |
| `--no-images` | Do not extract or reference images |
| `--no-links` | Do not preserve hyperlinks |
| `--no-headings` | Do not detect headings based on font size |
| `--no-formatting` | Do not detect bold/italic formatting |
| `--page-separator` | String to insert between pages (default: horizontal rule) |
| `-v, --verbose` | Print progress information |
| `--version` | Show version information |

### Python API

```python
from pdf2md import PDFConverter, ConversionOptions
from pathlib import Path

# Basic conversion
converter = PDFConverter()
markdown = converter.convert_file("document.pdf")
print(markdown)

# Conversion with custom options
options = ConversionOptions(
    extract_images=True,
    image_output_dir=Path("./images"),
    image_format="png",
    preserve_hyperlinks=True,
    detect_headings=True,
    detect_bold_italic=True,
    page_separator="\n\n---\n\n",
)
converter = PDFConverter(options)
markdown = converter.convert_file("document.pdf", "output.md")

# Convert from bytes
with open("document.pdf", "rb") as f:
    pdf_bytes = f.read()
markdown = converter.convert_bytes(pdf_bytes, source_name="document")

# Convert from stream
with open("document.pdf", "rb") as f:
    markdown = converter.convert_stream(f, source_name="document")
```

### ConversionOptions

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `extract_images` | `bool` | `True` | Extract and reference images |
| `image_output_dir` | `Path \| None` | `None` | Directory to save images |
| `image_format` | `str` | `"png"` | Output format for images |
| `image_dpi` | `int` | `150` | DPI for image extraction |
| `preserve_hyperlinks` | `bool` | `True` | Convert hyperlinks to Markdown |
| `detect_headings` | `bool` | `True` | Detect headings by font size |
| `detect_lists` | `bool` | `True` | Detect numbered/bulleted lists |
| `detect_bold_italic` | `bool` | `True` | Detect bold/italic text |
| `heading_font_size_threshold` | `float` | `14.0` | Minimum font size for headings |
| `min_heading_size_ratio` | `float` | `1.2` | Minimum font size ratio vs base |
| `line_merge_threshold` | `float` | `5.0` | Max vertical gap to merge lines |
| `list_indent_spaces` | `int` | `4` | Spaces per indentation level for nested lists |
| `page_separator` | `str` | `"\n\n---\n\n"` | String between pages |

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=pdf2md --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_converter.py
```

### Project Structure

```
pdf2md/
├── pdf2md/
│   ├── __init__.py      # Package exports
│   ├── __main__.py      # Enables: python -m pdf2md
│   ├── cli.py           # CLI entry point
│   └── converter.py     # Core conversion logic
├── tests/
│   ├── conftest.py      # Test fixtures
│   ├── test_converter.py # Converter tests
│   ├── test_cli.py      # CLI tests
│   └── fixtures/        # Sample PDFs for testing
├── pyproject.toml       # Project configuration
└── README.md
```

## Dependencies

- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF parsing and extraction
- [Pillow](https://pillow.readthedocs.io/) - Image processing

## Limitations

- Complex table structures may not be perfectly preserved
- Some advanced PDF features (forms, annotations) are not extracted
- Text in images/scanned PDFs requires OCR (not included)
- Right-to-left text may not render correctly
- Very long lines split across the PDF may occasionally fragment

## License

MIT License - see [LICENSE](LICENSE) for details.

