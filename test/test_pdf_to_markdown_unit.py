from __future__ import annotations

from src.cv_scorer import pdf_to_markdown
from src.cv_scorer.pdf_to_markdown import PDFMarkdownExtractor, PDFToMarkdownConfig


class FakeRenderer:
    created_configs = []

    def __init__(self, config):
        self.created_configs.append(config)

    def render_pdf(self, pdf_path):
        return [
            (1, b"first page"),
            (2, b"second page"),
        ]


class FakeOCRClient:
    created_configs = []

    def __init__(self, config):
        self.created_configs.append(config)
        self.calls = []

    def image_to_markdown(self, image_bytes: bytes, page_number: int = 1) -> str:
        self.calls.append((page_number, image_bytes))
        return f"markdown for page {page_number}: {image_bytes.decode('ascii')}"


def test_pdf_markdown_extractor_orchestrates_rendering_and_ocr(monkeypatch, tmp_path):
    FakeRenderer.created_configs.clear()
    FakeOCRClient.created_configs.clear()
    monkeypatch.setattr(pdf_to_markdown, "PDFToPNGRenderer", FakeRenderer)
    monkeypatch.setattr(pdf_to_markdown, "OCRServiceClient", FakeOCRClient)

    extractor = PDFMarkdownExtractor(
        PDFToMarkdownConfig(
            api_key="secret",
            base_url="http://ocr.test",
            model="test-model",
            prompt="extract",
            dpi=150,
            image_format="png",
            timeout_seconds=12,
        )
    )

    output = extractor.extract_pdf(tmp_path / "resume.pdf")

    assert output == (
        "## Page 1\n\nmarkdown for page 1: first page\n\n"
        "## Page 2\n\nmarkdown for page 2: second page\n"
    )
    assert FakeRenderer.created_configs[0].dpi == 150
    assert FakeRenderer.created_configs[0].image_format == "png"
    assert FakeOCRClient.created_configs[0].api_key == "secret"
    assert FakeOCRClient.created_configs[0].base_url == "http://ocr.test"
    assert FakeOCRClient.created_configs[0].model == "test-model"
