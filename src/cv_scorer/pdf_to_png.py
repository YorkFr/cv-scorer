from __future__ import annotations

import argparse
import io
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PDFToPNGConfig:
    dpi: int
    image_format: str = "png"


class PDFToPNGRenderer:
    def __init__(self, config: PDFToPNGConfig) -> None:
        self.config = config

    def render_pdf(self, pdf_path: Path) -> list[tuple[int, bytes]]:
        try:
            return self._render_with_pymupdf(pdf_path)
        except Exception:
            try:
                return self._render_with_pypdfium2(pdf_path)
            except Exception:
                return self._render_with_pdftoppm(pdf_path)

    def write_pages(self, pdf_path: Path, output_dir: Path) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        written_paths: list[Path] = []
        for page_number, image_bytes in self.render_pdf(pdf_path):
            image_path = output_dir / f"{pdf_path.stem}_page_{page_number:03d}.{self.config.image_format}"
            image_path.write_bytes(image_bytes)
            written_paths.append(image_path)
        return written_paths

    def _render_with_pymupdf(self, pdf_path: Path) -> list[tuple[int, bytes]]:
        import fitz

        document = fitz.open(pdf_path)
        rendered_pages: list[tuple[int, bytes]] = []
        try:
            zoom = self.config.dpi / 72
            matrix = fitz.Matrix(zoom, zoom)
            for page_index in range(document.page_count):
                page = document.load_page(page_index)
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                rendered_pages.append((page_index + 1, pixmap.tobytes(self.config.image_format)))
        finally:
            document.close()
        return rendered_pages

    def _render_with_pypdfium2(self, pdf_path: Path) -> list[tuple[int, bytes]]:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(pdf_path))
        rendered_pages: list[tuple[int, bytes]] = []
        scale = self.config.dpi / 72
        for page_index in range(len(pdf)):
            page = pdf.get_page(page_index)
            try:
                bitmap = page.render(scale=scale)
                pil_image = bitmap.to_pil()
                image_buffer = io.BytesIO()
                pil_format = "PNG" if self.config.image_format == "png" else "JPEG"
                pil_image.save(image_buffer, format=pil_format)
                rendered_pages.append((page_index + 1, image_buffer.getvalue()))
            finally:
                page.close()
        pdf.close()
        return rendered_pages

    def _render_with_pdftoppm(self, pdf_path: Path) -> list[tuple[int, bytes]]:
        image_ext = "png" if self.config.image_format == "png" else "jpg"
        with tempfile.TemporaryDirectory(prefix="cv_scorer_pdftoppm_") as tmp_dir:
            output_prefix = Path(tmp_dir) / "page"
            command = [
                "pdftoppm",
                "-r",
                str(self.config.dpi),
                f"-{image_ext}",
                str(pdf_path),
                str(output_prefix),
            ]
            result = subprocess.run(command, capture_output=True, check=False)
            if result.returncode != 0:
                stderr_text = result.stderr.decode("utf-8", errors="replace").strip()
                stdout_text = result.stdout.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"pdftoppm failed: {stderr_text or stdout_text}")

            page_paths = sorted(Path(tmp_dir).glob(f"page-*.{image_ext}"))
            if not page_paths:
                raise RuntimeError("pdftoppm produced no page images.")

            rendered_pages: list[tuple[int, bytes]] = []
            for page_path in page_paths:
                page_number = int(page_path.stem.split("-")[-1])
                rendered_pages.append((page_number, page_path.read_bytes()))
            return rendered_pages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a PDF into page images.")
    parser.add_argument("input_pdf", type=Path, help="Path to the input PDF file.")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Directory to store rendered page images. Defaults to <pdf_stem>_pages beside the PDF.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Rendering DPI for the output page images.",
    )
    parser.add_argument(
        "--image-format",
        choices=("png", "jpeg"),
        default="png",
        help="Output image format for rendered pages.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> tuple[Path, Path, PDFToPNGConfig]:
    input_pdf = args.input_pdf.expanduser().resolve()
    if not input_pdf.exists():
        raise FileNotFoundError(f"Input PDF does not exist: {input_pdf}")
    if input_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"Input file must be a PDF: {input_pdf}")

    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else input_pdf.parent / f"{input_pdf.stem}_pages"
    )
    config = PDFToPNGConfig(dpi=args.dpi, image_format=args.image_format)
    return input_pdf, output_dir, config


def main() -> int:
    args = parse_args()
    input_pdf, output_dir, config = validate_args(args)
    renderer = PDFToPNGRenderer(config)
    page_paths = renderer.write_pages(input_pdf, output_dir)
    print(f"Rendered {len(page_paths)} pages to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
