from __future__ import annotations

import base64

import pytest

from src.cv_scorer.png_to_markdown import OCRServiceClient, PNGToMarkdownConfig


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def make_config(api_key: str = "") -> PNGToMarkdownConfig:
    return PNGToMarkdownConfig(
        api_key=api_key,
        base_url="http://127.0.0.1:8000/",
        model="lightonai/LightOnOCR-2-1B",
        prompt="Extract markdown",
        image_format="png",
        timeout_seconds=30,
    )


def test_image_to_markdown_sends_expected_payload(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse({"markdown": "# Resume"})

    monkeypatch.setattr("src.cv_scorer.png_to_markdown.requests.post", fake_post)

    markdown = OCRServiceClient(make_config(api_key="token")).image_to_markdown(
        b"image-bytes",
        page_number=3,
    )

    assert markdown == "# Resume"
    assert captured["url"] == "http://127.0.0.1:8000/v1/ocr/page"
    assert captured["headers"] == {"Authorization": "Bearer token"}
    assert captured["timeout"] == 30
    assert captured["json"]["model"] == "lightonai/LightOnOCR-2-1B"
    assert captured["json"]["page_number"] == 3
    assert captured["json"]["prompt"] == "Extract markdown"
    assert captured["json"]["image_format"] == "png"
    assert base64.b64decode(captured["json"]["image_base64"]) == b"image-bytes"


def test_image_to_markdown_rejects_empty_markdown(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return FakeResponse({"markdown": "   "})

    monkeypatch.setattr("src.cv_scorer.png_to_markdown.requests.post", fake_post)

    with pytest.raises(RuntimeError, match="invalid payload"):
        OCRServiceClient(make_config()).image_to_markdown(b"image-bytes", page_number=1)
