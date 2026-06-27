from __future__ import annotations

from pathlib import Path

from src.cv_scorer.scoring import score_markdown


TEST_DATA_DIR = Path(__file__).resolve().parent / "cv_pdf"


def test_score_markdown_returns_explainable_report():
    markdown = (TEST_DATA_DIR / "word_type_en.md").read_text(encoding="utf-8")

    report = score_markdown(markdown)
    payload = report.to_dict()

    assert payload["max_score"] == 100.0
    assert payload["total_score"] >= 70
    assert payload["grade"] in {"A", "B"}
    assert len(payload["sections"]) == 7
    assert payload["profile"]["email"] == "sonnetjulie1@gmail.com"
    assert any(section["suggestions"] or section["findings"] for section in payload["sections"])


def test_score_markdown_penalizes_sparse_resume():
    report = score_markdown("# Jane Doe\n\nNo details yet.")

    assert report.total_score < 40
    assert report.grade == "D"
    assert any(section.suggestions for section in report.sections)
