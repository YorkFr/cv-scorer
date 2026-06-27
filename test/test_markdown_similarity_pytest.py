from __future__ import annotations

import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import pytest
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cv_scorer.pdf_to_markdown import PDFMarkdownExtractor, PDFToMarkdownConfig


TEST_DATA_DIR = PROJECT_ROOT / "test" / "cv_pdf"
OCR_BASE_URL = os.getenv("OCR_BASE_URL", "http://127.0.0.1:8000")
OCR_MODEL = os.getenv("OCR_MODEL", "lightonai/LightOnOCR-2-1B")
SIMILARITY_THRESHOLD = 0.95


@dataclass(frozen=True, slots=True)
class MarkdownFixture:
    pdf_path: Path
    expected_markdown_path: Path


FIXTURES = [
    MarkdownFixture(
        pdf_path=TEST_DATA_DIR / "word_type_en.pdf",
        expected_markdown_path=TEST_DATA_DIR / "word_type_en.md",
    ),
    MarkdownFixture(
        pdf_path=TEST_DATA_DIR / "canvas type_fr.pdf",
        expected_markdown_path=TEST_DATA_DIR / "canvas type_fr.md",
    ),
]


def normalize_paragraph(text: str) -> str:
    lines = [line.strip() for line in text.replace("\r\n", "\n").splitlines()]
    compact = "\n".join(line for line in lines if line)
    compact = re.sub(r"^#{1,6}\s*", "", compact, flags=re.MULTILINE)
    compact = compact.replace("**", "").replace("*", "")
    compact = re.sub(r"!\[image\]\(image_\d+\.(png|jpg|jpeg)\)", "[image]", compact, flags=re.IGNORECASE)
    compact = "".join(
        ch for ch in compact if unicodedata.category(ch) not in {"So", "Sk", "Cs", "Co", "Cn"}
    )
    return " ".join(compact.split()).strip()


def split_paragraphs(markdown: str) -> list[str]:
    normalized_markdown = markdown.replace("\r\n", "\n")
    normalized_markdown = re.sub(
        r"(!\[image\]\(image_\d+\.(png|jpg|jpeg)\))",
        r"\n\n\1\n\n",
        normalized_markdown,
        flags=re.IGNORECASE,
    )
    raw_blocks = normalized_markdown.split("\n\n")
    paragraphs = [normalize_paragraph(block) for block in raw_blocks]
    return [paragraph for paragraph in paragraphs if paragraph]


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(a=left, b=right).ratio()


@pytest.fixture(scope="session")
def extractor() -> PDFMarkdownExtractor:
    try:
        response = requests.get(f"{OCR_BASE_URL.rstrip('/')}/healthz", timeout=10)
        response.raise_for_status()
    except Exception as exc:
        pytest.skip(
            f"OCR service is not reachable at {OCR_BASE_URL}. Start the Docker OCR service before running tests. {exc}"
        )

    return PDFMarkdownExtractor(
        PDFToMarkdownConfig(
            api_key="",
            base_url=OCR_BASE_URL,
            model=OCR_MODEL,
            prompt=(
                "You are an OCR engine for resume and PDF parsing. "
                "Extract every visible detail from the page into clean Markdown. "
                "Preserve headings, bullet lists, tables, and ordering as faithfully as possible. "
                "Return Markdown only."
            ),
            dpi=200,
            image_format="png",
            timeout_seconds=300,
        )
    )


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda fixture: fixture.pdf_path.name)
def test_reference_markdown_similarity(extractor: PDFMarkdownExtractor, fixture: MarkdownFixture) -> None:
    generated_markdown = extractor.extract_pdf(fixture.pdf_path)
    expected_markdown = fixture.expected_markdown_path.read_text(encoding="utf-8")

    generated_paragraphs = split_paragraphs(generated_markdown)
    expected_paragraphs = split_paragraphs(expected_markdown)

    indexed_generated = list(enumerate(generated_paragraphs, start=1))

    for index, expected in enumerate(expected_paragraphs, start=1):
        best_position = None
        best_actual = None
        best_score = -1.0

        for generated_index, actual in indexed_generated:
            score = similarity(expected, actual)
            if score > best_score:
                best_position = generated_index
                best_actual = actual
                best_score = score

        assert best_position is not None, f"No generated paragraph available for expected paragraph {index}."
        assert best_score >= SIMILARITY_THRESHOLD, (
            f"Paragraph {index} in {fixture.pdf_path.name} is below threshold: "
            f"{best_score:.4f} < {SIMILARITY_THRESHOLD:.2f}\n"
            f"Matched generated paragraph: {best_position}\n"
            f"Expected: {expected}\n"
            f"Actual:   {best_actual}"
        )
