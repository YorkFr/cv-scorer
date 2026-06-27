from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .pdf_to_markdown import PDFMarkdownExtractor, PDFToMarkdownConfig
from .pdf_to_png import PDFToPNGConfig, PDFToPNGRenderer
from .png_to_markdown import DEFAULT_PROMPT, OCRServiceClient, PNGToMarkdownConfig
from .scoring import score_markdown


DEFAULT_MODEL = os.getenv("OCR_MODEL", "lightonai/LightOnOCR-2-1B")
DEFAULT_BASE_URL = os.getenv("OCR_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("OCR_TIMEOUT_SECONDS", "300"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cv-scorer", description="CV Scorer command line interface.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pdf_to_png = subparsers.add_parser("pdf-to-png", help="Render a PDF into page images.")
    pdf_to_png.add_argument("input_pdf", type=Path)
    pdf_to_png.add_argument("-o", "--output-dir", type=Path)
    pdf_to_png.add_argument("--dpi", type=int, default=200)
    pdf_to_png.add_argument("--image-format", choices=("png", "jpeg"), default="png")
    pdf_to_png.set_defaults(func=run_pdf_to_png)

    png_to_markdown = subparsers.add_parser("png-to-markdown", help="OCR one page image into Markdown.")
    png_to_markdown.add_argument("input_image", type=Path)
    png_to_markdown.add_argument("-o", "--output", type=Path)
    add_ocr_options(png_to_markdown)
    png_to_markdown.set_defaults(func=run_png_to_markdown)

    pdf_to_markdown = subparsers.add_parser("pdf-to-markdown", help="Extract a PDF into Markdown using OCR.")
    pdf_to_markdown.add_argument("input_pdf", type=Path)
    pdf_to_markdown.add_argument("-o", "--output", type=Path)
    pdf_to_markdown.add_argument("--dpi", type=int, default=200)
    pdf_to_markdown.add_argument("--image-format", choices=("png", "jpeg"), default="png")
    add_ocr_options(pdf_to_markdown)
    pdf_to_markdown.set_defaults(func=run_pdf_to_markdown)

    score = subparsers.add_parser("score-markdown", help="Score a Markdown resume.")
    score.add_argument("input_markdown", type=Path)
    score.add_argument("-o", "--output", type=Path, help="Optional JSON output path.")
    score.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    score.set_defaults(func=run_score_markdown)

    serve = subparsers.add_parser("serve", help="Start the FastAPI backend.")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=9000)
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(func=run_serve)

    return parser


def add_ocr_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--api-key", default=os.getenv("OCR_API_KEY", ""))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)


def run_pdf_to_png(args: argparse.Namespace) -> int:
    input_pdf = resolve_existing_file(args.input_pdf, ".pdf", "Input PDF")
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else input_pdf.parent / f"{input_pdf.stem}_pages"
    renderer = PDFToPNGRenderer(PDFToPNGConfig(dpi=args.dpi, image_format=args.image_format))
    page_paths = renderer.write_pages(input_pdf, output_dir)
    print(f"Rendered {len(page_paths)} pages to {output_dir}")
    return 0


def run_png_to_markdown(args: argparse.Namespace) -> int:
    input_image = resolve_image_file(args.input_image)
    output_path = args.output.expanduser().resolve() if args.output else input_image.with_suffix(".md")
    image_format = "jpeg" if input_image.suffix.lower() in {".jpg", ".jpeg"} else "png"
    client = OCRServiceClient(
        PNGToMarkdownConfig(
            api_key=args.api_key,
            base_url=args.base_url,
            model=args.model,
            prompt=args.prompt,
            image_format=image_format,
            timeout_seconds=args.timeout_seconds,
        )
    )
    markdown = client.image_to_markdown(input_image.read_bytes())
    write_text(output_path, markdown.strip() + "\n")
    print(f"Markdown written to {output_path}")
    return 0


def run_pdf_to_markdown(args: argparse.Namespace) -> int:
    input_pdf = resolve_existing_file(args.input_pdf, ".pdf", "Input PDF")
    output_path = args.output.expanduser().resolve() if args.output else input_pdf.with_suffix(".md")
    extractor = PDFMarkdownExtractor(
        PDFToMarkdownConfig(
            api_key=args.api_key,
            base_url=args.base_url,
            model=args.model,
            prompt=args.prompt,
            dpi=args.dpi,
            image_format=args.image_format,
            timeout_seconds=args.timeout_seconds,
        )
    )
    markdown = extractor.extract_pdf(input_pdf)
    write_text(output_path, markdown)
    print(f"Markdown written to {output_path}")
    return 0


def run_score_markdown(args: argparse.Namespace) -> int:
    input_markdown = resolve_existing_file(args.input_markdown, ".md", "Input Markdown")
    indent = 2 if args.pretty else None
    payload = score_markdown(input_markdown.read_text(encoding="utf-8")).to_dict()
    text = json.dumps(payload, ensure_ascii=False, indent=indent)
    if args.output:
        output_path = args.output.expanduser().resolve()
        write_text(output_path, text + "\n")
        print(f"Score report written to {output_path}")
    else:
        print(text)
    return 0


def run_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("src.cv_scorer.backend_api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def resolve_existing_file(path: Path, suffix: str, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label} does not exist: {resolved}")
    if resolved.suffix.lower() != suffix:
        raise ValueError(f"{label} must be a {suffix} file: {resolved}")
    return resolved


def resolve_image_file(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Input image does not exist: {resolved}")
    if resolved.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise ValueError(f"Input image must be a PNG or JPEG file: {resolved}")
    return resolved


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
