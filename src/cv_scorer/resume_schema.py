from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ResumeSection:
    title: str
    content: str


@dataclass(frozen=True, slots=True)
class ResumeProfile:
    raw_markdown: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[str] = field(default_factory=list)
    summary: str | None = None
    education: list[str] = field(default_factory=list)
    experience: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    sections: list[ResumeSection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScoreSection:
    name: str
    score: float
    max_score: float
    findings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScoreReport:
    total_score: float
    max_score: float
    grade: str
    summary: str
    sections: list[ScoreSection]
    profile: ResumeProfile

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_score": self.total_score,
            "max_score": self.max_score,
            "grade": self.grade,
            "summary": self.summary,
            "sections": [section.to_dict() for section in self.sections],
            "profile": self.profile.to_dict(),
        }
