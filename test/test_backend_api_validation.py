from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.cv_scorer.backend_api import (
    MAX_PROMPT_LENGTH,
    _ensure_image,
    _ensure_pdf,
    _validate_dpi,
    _validate_prompt,
)


def test_ensure_pdf_accepts_pdf_filename():
    _ensure_pdf(SimpleNamespace(filename="resume.PDF"))


def test_ensure_pdf_rejects_non_pdf_filename():
    with pytest.raises(HTTPException) as exc_info:
        _ensure_pdf(SimpleNamespace(filename="resume.png"))

    assert exc_info.value.status_code == 400
    assert "Only PDF" in exc_info.value.detail


@pytest.mark.parametrize(
    ("filename", "expected_format"),
    [
        ("page.png", "png"),
        ("page.jpg", "jpeg"),
        ("page.jpeg", "jpeg"),
    ],
)
def test_ensure_image_accepts_supported_formats(filename, expected_format):
    assert _ensure_image(SimpleNamespace(filename=filename)) == expected_format


def test_ensure_image_rejects_unsupported_format():
    with pytest.raises(HTTPException) as exc_info:
        _ensure_image(SimpleNamespace(filename="resume.pdf"))

    assert exc_info.value.status_code == 400
    assert "Only PNG or JPEG" in exc_info.value.detail


@pytest.mark.parametrize("dpi", [72, 200, 300])
def test_validate_dpi_accepts_supported_range(dpi):
    _validate_dpi(dpi)


@pytest.mark.parametrize("dpi", [71, 301])
def test_validate_dpi_rejects_out_of_range_values(dpi):
    with pytest.raises(HTTPException) as exc_info:
        _validate_dpi(dpi)

    assert exc_info.value.status_code == 400
    assert "dpi must be between 72 and 300" in exc_info.value.detail


def test_validate_prompt_accepts_max_length_prompt():
    _validate_prompt("x" * MAX_PROMPT_LENGTH)


def test_validate_prompt_rejects_too_long_prompt():
    with pytest.raises(HTTPException) as exc_info:
        _validate_prompt("x" * (MAX_PROMPT_LENGTH + 1))

    assert exc_info.value.status_code == 400
    assert "prompt must be at most" in exc_info.value.detail
