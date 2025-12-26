"""Command-line interface for PDF to Markdown conversion."""

import argparse
import sys
from pathlib import Path

from pdf2md.converter import ConversionOptions, PDFConverter


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments. Uses sys.argv if None.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="pdf2md",
        description="Convert PDF documents to Markdown format, preserving formatting, images, and hyperlinks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pdf2md document.pdf                    Convert to stdout
  pdf2md document.pdf -o output.md       Convert to file
  pdf2md document.pdf --images ./images  Extract images to directory
  pdf2md *.pdf -o ./output/              Batch convert multiple files
        """,
    )

    parser.add_argument(
        "input",
        nargs="+",
        type=Path,
        help="Input PDF file(s) to convert",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output file or directory. If directory, creates .md files with same names as inputs.",
    )

    parser.add_argument(
        "--images",
        type=Path,
        dest="image_dir",
        help="Directory to save extracted images. If not specified, images are not saved.",
    )

    parser.add_argument(
        "--image-format",
        choices=["png", "jpg", "jpeg"],
        default="png",
        help="Format for extracted images (default: png)",
    )

    parser.add_argument(
        "--image-dpi",
        type=int,
        default=150,
        help="DPI for extracted images (default: 150)",
    )

    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Do not extract or reference images",
    )

    parser.add_argument(
        "--no-links",
        action="store_true",
        help="Do not preserve hyperlinks",
    )

    parser.add_argument(
        "--no-headings",
        action="store_true",
        help="Do not detect headings based on font size",
    )

    parser.add_argument(
        "--no-formatting",
        action="store_true",
        help="Do not detect bold/italic formatting",
    )

    parser.add_argument(
        "--page-separator",
        default="\n\n---\n\n",
        help="String to insert between pages (default: horizontal rule)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print progress information to stderr",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    return parser.parse_args(args)


def create_options(args: argparse.Namespace) -> ConversionOptions:
    """Create ConversionOptions from parsed arguments.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Configured ConversionOptions object.
    """
    return ConversionOptions(
        extract_images=not args.no_images,
        image_output_dir=args.image_dir,
        image_format=args.image_format,
        image_dpi=args.image_dpi,
        preserve_hyperlinks=not args.no_links,
        detect_headings=not args.no_headings,
        detect_bold_italic=not args.no_formatting,
        page_separator=args.page_separator,
    )


def process_single_file(input_path: Path, output_path: Path | None, converter: PDFConverter, verbose: bool) -> bool:
    """Process a single PDF file.

    Args:
        input_path: Path to the input PDF.
        output_path: Path to write output, or None for stdout.
        converter: Configured PDFConverter instance.
        verbose: Whether to print progress messages.

    Returns:
        True if conversion succeeded, False otherwise.
    """
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        return False

    if not input_path.suffix.lower() == ".pdf":
        print(f"Warning: {input_path} may not be a PDF file", file=sys.stderr)

    if verbose:
        print(f"Converting: {input_path}", file=sys.stderr)

    try:
        markdown = converter.convert_file(input_path)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown, encoding="utf-8")
            if verbose:
                print(f"  -> {output_path}", file=sys.stderr)
        else:
            print(markdown)

        return True

    except Exception as e:
        print(f"Error converting {input_path}: {e}", file=sys.stderr)
        return False


def main(args: list[str] | None = None) -> int:
    """Main entry point for the CLI.

    Args:
        args: Command-line arguments. Uses sys.argv if None.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    parsed_args = parse_args(args)
    options = create_options(parsed_args)
    converter = PDFConverter(options)

    input_files = parsed_args.input
    output = parsed_args.output
    verbose = parsed_args.verbose

    success_count = 0
    error_count = 0

    # Determine output mode.
    if output and output.suffix == "" and len(input_files) > 1:
        # Output is a directory for multiple files.
        output.mkdir(parents=True, exist_ok=True)
        for input_path in input_files:
            output_path = output / (input_path.stem + ".md")
            if process_single_file(input_path, output_path, converter, verbose):
                success_count += 1
            else:
                error_count += 1
    elif output and len(input_files) > 1:
        # Output is a directory for multiple files.
        output.mkdir(parents=True, exist_ok=True)
        for input_path in input_files:
            output_path = output / (input_path.stem + ".md")
            if process_single_file(input_path, output_path, converter, verbose):
                success_count += 1
            else:
                error_count += 1
    else:
        # Single file or stdout.
        for input_path in input_files:
            output_path = output if output else None
            if process_single_file(input_path, output_path, converter, verbose):
                success_count += 1
            else:
                error_count += 1

    if verbose and len(input_files) > 1:
        print(f"\nProcessed {success_count} files, {error_count} errors", file=sys.stderr)

    return 0 if error_count == 0 else 1

