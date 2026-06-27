from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

from .pdf_to_png import PDFToPNGConfig, PDFToPNGRenderer
from .png_to_markdown import DEFAULT_PROMPT, OCRServiceClient, PNGToMarkdownConfig


@dataclass(slots=True)
class PDFToMarkdownConfig:
    api_key: str
    base_url: str
    model: str
    prompt: str
    dpi: int
    image_format: str
    timeout_seconds: int


class PDFMarkdownExtractor:
    def __init__(self, config: PDFToMarkdownConfig) -> None:
        self.renderer = PDFToPNGRenderer(
            PDFToPNGConfig(dpi=config.dpi, image_format=config.image_format)
        )
        self.client = OCRServiceClient(
            PNGToMarkdownConfig(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.model,
                prompt=config.prompt,
                image_format=config.image_format,
                timeout_seconds=config.timeout_seconds,
            )
        )

    def extract_pdf(self, pdf_path: Path) -> str:
        markdown_pages: list[str] = []
        for page_number, image_bytes in self.renderer.render_pdf(pdf_path):
            page_markdown = self.client.image_to_markdown(image_bytes, page_number)
            markdown_pages.append(f"## Page {page_number}\n\n{page_markdown.strip()}")
        return "\n\n".join(markdown_pages).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Orchestrate PDF -> PNG -> Markdown using the OCR model service."
    )
    parser.add_argument("input_pdf", type=Path, help="Path to the input PDF file.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Path to the output Markdown file. Defaults to the PDF path with .md suffix.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("OCR_API_KEY", ""),
        help="OCR service API key. Optional for local services.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("OCR_BASE_URL", "http://127.0.0.1:8000"),
        help="Base URL of the OCR model service.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OCR_MODEL", "lightonai/LightOnOCR-2-1B"),
        help="Model identifier passed through to the OCR service.",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Prompt used for OCR extraction.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Rendering DPI used in the PDF -> PNG stage.",
    )
    parser.add_argument(
        "--image-format",
        choices=("png", "jpeg"),
        default="png",
        help="Intermediate page image format between the two modules.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=int(os.getenv("OCR_TIMEOUT_SECONDS", "300")),
        help="HTTP timeout for each OCR request.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> tuple[Path, Path, PDFToMarkdownConfig]:
    input_pdf = args.input_pdf.expanduser().resolve()
    if not input_pdf.exists():
        raise FileNotFoundError(f"Input PDF does not exist: {input_pdf}")
    if input_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"Input file must be a PDF: {input_pdf}")

    output_path = args.output.expanduser().resolve() if args.output else input_pdf.with_suffix(".md")
    config = PDFToMarkdownConfig(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        prompt=args.prompt,
        dpi=args.dpi,
        image_format=args.image_format,
        timeout_seconds=args.timeout_seconds,
    )
    return input_pdf, output_path, config


def main() -> int:
    args = parse_args()
    input_pdf, output_path, config = validate_args(args)
    extractor = PDFMarkdownExtractor(config)
    markdown = extractor.extract_pdf(input_pdf)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"Markdown written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
