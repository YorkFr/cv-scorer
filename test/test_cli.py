from __future__ import annotations

import json

import pytest

from src.cv_scorer.cli import main


def test_cli_help_exits_successfully(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    assert "CV Scorer command line interface" in capsys.readouterr().out


def test_score_markdown_prints_json_report(tmp_path, capsys):
    markdown_path = tmp_path / "resume.md"
    markdown_path.write_text(
        "# Jane Doe\n\n"
        "jane@example.com\n"
        "+33 6 11 22 33 44\n"
        "www.linkedin.com/in/jane-doe\n\n"
        "## PROFESSIONAL EXPERIENCE\n"
        "- Built 12 dashboards with Excel and Power BI in 2024.\n\n"
        "## EDUCATION\n"
        "Master Degree in Management, 2021-2024\n\n"
        "## SKILLS\n"
        "- Excel\n- Power BI\n- SQL\n\n"
        "## LANGUAGES\n"
        "- English\n",
        encoding="utf-8",
    )

    assert main(["score-markdown", str(markdown_path)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["max_score"] == 100.0
    assert payload["profile"]["email"] == "jane@example.com"


def test_score_markdown_writes_json_report(tmp_path, capsys):
    markdown_path = tmp_path / "resume.md"
    output_path = tmp_path / "score.json"
    markdown_path.write_text("# Jane Doe\n\njane@example.com\n", encoding="utf-8")

    assert main(["score-markdown", str(markdown_path), "-o", str(output_path), "--pretty"]) == 0

    assert "Score report written to" in capsys.readouterr().out
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["profile"]["email"] == "jane@example.com"
