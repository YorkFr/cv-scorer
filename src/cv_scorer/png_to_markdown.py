from __future__ import annotations

import argparse
import base64
import os
from dataclasses import dataclass
from pathlib import Path

import requests


DEFAULT_PROMPT = """You are an OCR engine for resume and PDF parsing.
Extract every visible detail from the page into clean Markdown.

Requirements:
- Preserve headings, bullet lists, tables, and ordering as faithfully as possible.
- Do not summarize.
- Do not omit small text, footnotes, dates, contact details, captions, labels, or table cells.
- If the page contains diagrams or non-text layout, describe the structure briefly in Markdown before the extracted text.
- Return Markdown only.
"""


@dataclass(slots=True)
class PNGToMarkdownConfig:
    api_key: str
    base_url: str
    model: str
    prompt: str
    image_format: str
    timeout_seconds: int


class OCRServiceClient:
    def __init__(self, config: PNGToMarkdownConfig) -> None:
        self.config = config

    def image_to_markdown(self, image_bytes: bytes, page_number: int = 1) -> str:
        encoded_image = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": self.config.model,
            "page_number": page_number,
            "prompt": self.config.prompt,
            "image_base64": encoded_image,
            "image_format": self.config.image_format,
        }
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        response = requests.post(
            f"{self.config.base_url.rstrip('/')}/v1/ocr/page",
            json=payload,
            headers=headers,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        markdown = data.get("markdown")
        if not isinstance(markdown, str) or not markdown.strip():
            raise RuntimeError(f"OCR service returned an invalid payload for page {page_number}.")
        return markdown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send one page image to the OCR service and get Markdown.")
    parser.add_argument("input_image", type=Path, help="Path to the input PNG/JPEG page image.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Path to the output Markdown file. Defaults to the image path with .md suffix.",
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
        "--timeout-seconds",
        type=int,
        default=int(os.getenv("OCR_TIMEOUT_SECONDS", "300")),
        help="HTTP timeout for the OCR request.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> tuple[Path, Path, PNGToMarkdownConfig]:
    input_image = args.input_image.expanduser().resolve()
    if not input_image.exists():
        raise FileNotFoundError(f"Input image does not exist: {input_image}")

    suffix = input_image.suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg"}:
        raise ValueError(f"Input file must be a PNG or JPEG image: {input_image}")

    image_format = "jpeg" if suffix in {".jpg", ".jpeg"} else "png"
    output_path = args.output.expanduser().resolve() if args.output else input_image.with_suffix(".md")
    config = PNGToMarkdownConfig(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        prompt=args.prompt,
        image_format=image_format,
        timeout_seconds=args.timeout_seconds,
    )
    return input_image, output_path, config


def main() -> int:
    args = parse_args()
    input_image, output_path, config = validate_args(args)
    client = OCRServiceClient(config)
    markdown = client.image_to_markdown(input_image.read_bytes())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown.strip() + "\n", encoding="utf-8")
    print(f"Markdown written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
