from __future__ import annotations

from pathlib import Path

from src.cv_scorer.markdown_to_resume import parse_resume_markdown


TEST_DATA_DIR = Path(__file__).resolve().parent / "cv_pdf"


def test_parse_resume_markdown_extracts_core_contact_fields():
    markdown = (TEST_DATA_DIR / "word_type_en.md").read_text(encoding="utf-8")

    profile = parse_resume_markdown(markdown)

    assert profile.name == "Julie SONNET 宋珊丽"
    assert profile.email == "sonnetjulie1@gmail.com"
    assert profile.phone is not None
    assert "linkedin.com/in/julie-sonnet" in " ".join(profile.links)
    assert profile.location is not None


def test_parse_resume_markdown_extracts_resume_sections_from_french_sample():
    markdown = (TEST_DATA_DIR / "canvas type_fr.md").read_text(encoding="utf-8")

    profile = parse_resume_markdown(markdown)

    assert profile.name == "JULIE SONNET"
    assert profile.email == "sonnetjulie1@gmail.com"
    assert profile.education
    assert profile.experience
    assert profile.projects
    assert profile.skills
    assert profile.languages
