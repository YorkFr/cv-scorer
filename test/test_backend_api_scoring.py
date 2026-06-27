from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from src.cv_scorer.backend_api import score_resume_markdown


def test_score_markdown_endpoint_returns_score_report():
    payload = asyncio.run(
        score_resume_markdown(
            markdown=(
                "# Jane Doe\n\n"
                "jane@example.com\n"
                "+33 6 11 22 33 44\n"
                "www.linkedin.com/in/jane-doe\n\n"
                "## PROFESSIONAL EXPERIENCE\n"
                "- Built 12 dashboards with Excel and Power BI.\n"
                "- Improved reporting quality by 20% in 2024.\n\n"
                "## EDUCATION\n"
                "Master Degree in Management, 2021-2024\n\n"
                "## SKILLS\n"
                "- Excel\n- Power BI\n- SQL\n- Communication\n\n"
                "## LANGUAGES\n"
                "- French native\n- English professional\n"
            )
        )
    )

    assert payload["total_score"] > 0
    assert payload["max_score"] == 100.0
    assert payload["profile"]["email"] == "jane@example.com"
    assert len(payload["sections"]) == 7


def test_score_markdown_endpoint_rejects_empty_markdown():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(score_resume_markdown(markdown="   "))

    assert exc_info.value.status_code == 400
    assert "must not be empty" in exc_info.value.detail
