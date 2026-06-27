from __future__ import annotations

import re

from .resume_schema import ResumeProfile, ResumeSection


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com|[\w-]+\.[a-z]{2,})(?:/[^\s<>)]+)?", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s.-]*)?(?:\(?\d{1,4}\)?[\s.-]*){3,}\d{2,}")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

SUMMARY_TITLES = {"profile", "summary", "profil"}
EDUCATION_TITLES = {"education", "éducation", "formation", "academic background"}
EXPERIENCE_TITLES = {
    "professional experience",
    "experience",
    "expérience",
    "experiences professionnelles",
    "expériences professionnelles",
    "work experience",
}
PROJECT_TITLES = {"projects", "project", "projets", "projets de groupe"}
SKILL_TITLES = {
    "skills",
    "competences",
    "compétences",
    "technical skills",
    "management & data tools",
    "informatiques",
    "soft skills",
}
LANGUAGE_TITLES = {"languages", "language", "linguistiques", "langues"}
CERTIFICATION_TITLES = {"certifications", "certification", "certificats"}


def parse_resume_markdown(markdown: str) -> ResumeProfile:
    cleaned_markdown = markdown.strip()
    sections = split_sections(cleaned_markdown)
    section_map = group_sections_by_kind(sections)

    first_heading = next((section.title for section in sections if section.title.lower() != "page 1"), None)
    name = clean_heading(first_heading) if first_heading else None
    email = first_match(EMAIL_RE, cleaned_markdown)
    links = unique_preserve_order(match.group(0).rstrip(".,") for match in URL_RE.finditer(cleaned_markdown))
    phone = first_phone(cleaned_markdown)
    location = infer_location(cleaned_markdown)
    summary = join_content(section_map["summary"]) or None

    return ResumeProfile(
        raw_markdown=cleaned_markdown,
        name=name,
        email=email,
        phone=phone,
        location=location,
        links=links,
        summary=summary,
        education=section_lines(section_map["education"]),
        experience=section_lines(section_map["experience"]),
        projects=section_lines(section_map["projects"]),
        skills=extract_skills(section_map["skills"], cleaned_markdown),
        languages=extract_languages(section_map["languages"], cleaned_markdown),
        certifications=section_lines(section_map["certifications"]),
        sections=sections,
    )


def split_sections(markdown: str) -> list[ResumeSection]:
    sections: list[ResumeSection] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in markdown.replace("\r\n", "\n").splitlines():
        match = HEADING_RE.match(line.strip())
        if match:
            if current_title is not None:
                sections.append(ResumeSection(current_title, "\n".join(current_lines).strip()))
            current_title = clean_heading(match.group(2))
            current_lines = []
        else:
            current_lines.append(line)

    if current_title is not None:
        sections.append(ResumeSection(current_title, "\n".join(current_lines).strip()))
    elif markdown.strip():
        sections.append(ResumeSection("Document", markdown.strip()))
    return sections


def group_sections_by_kind(sections: list[ResumeSection]) -> dict[str, list[ResumeSection]]:
    grouped: dict[str, list[ResumeSection]] = {
        "summary": [],
        "education": [],
        "experience": [],
        "projects": [],
        "skills": [],
        "languages": [],
        "certifications": [],
    }
    current_kind: str | None = None
    for section in sections:
        normalized_title = normalize_title(section.title)
        if normalized_title in SUMMARY_TITLES:
            current_kind = "summary"
            grouped["summary"].append(section)
        elif normalized_title in EDUCATION_TITLES:
            current_kind = "education"
            grouped["education"].append(section)
        elif normalized_title in EXPERIENCE_TITLES:
            current_kind = "experience"
            grouped["experience"].append(section)
        elif normalized_title in PROJECT_TITLES:
            current_kind = "projects"
            grouped["projects"].append(section)
        elif normalized_title in SKILL_TITLES:
            current_kind = "skills"
            grouped["skills"].append(section)
        elif normalized_title in LANGUAGE_TITLES:
            current_kind = "languages"
            grouped["languages"].append(section)
        elif normalized_title in CERTIFICATION_TITLES:
            current_kind = "certifications"
            grouped["certifications"].append(section)
        elif current_kind is not None:
            grouped[current_kind].append(section)
    return grouped


def extract_skills(skill_sections: list[ResumeSection], markdown: str) -> list[str]:
    candidates = section_lines(skill_sections)
    inline_match = re.search(r"Languages?:\s*(.+)", markdown, flags=re.IGNORECASE)
    if inline_match:
        candidates.extend(split_inline_items(inline_match.group(1)))

    tool_match = re.search(r"(?:Tools|Outils|Informatiques|Management & Data Tools):\s*(.+)", markdown, flags=re.IGNORECASE)
    if tool_match:
        candidates.extend(split_inline_items(tool_match.group(1)))

    return unique_preserve_order(clean_list_item(item) for item in candidates if clean_list_item(item))


def extract_languages(language_sections: list[ResumeSection], markdown: str) -> list[str]:
    candidates = section_lines(language_sections)
    inline_match = re.search(r"Languages?:\s*(.+)", markdown, flags=re.IGNORECASE)
    if inline_match:
        candidates.extend(split_inline_items(inline_match.group(1)))
    return unique_preserve_order(clean_list_item(item) for item in candidates if clean_list_item(item))


def section_lines(sections: list[ResumeSection]) -> list[str]:
    lines: list[str] = []
    for section in sections:
        lines.extend(extract_content_lines(section.content))
    return unique_preserve_order(line for line in lines if line)


def extract_content_lines(content: str) -> list[str]:
    lines: list[str] = []
    for raw_line in content.splitlines():
        line = clean_list_item(raw_line)
        if line and not line.startswith("![image]"):
            lines.append(line)
    return lines


def split_inline_items(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"[;,|]", text) if item.strip()]


def join_content(sections: list[ResumeSection]) -> str:
    return "\n".join(section.content.strip() for section in sections if section.content.strip()).strip()


def first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(0) if match else None


def first_phone(text: str) -> str | None:
    for match in PHONE_RE.finditer(text):
        value = match.group(0).strip()
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 8 and "202" not in digits[:4]:
            return value
    return None


def infer_location(text: str) -> str | None:
    for line in text.splitlines():
        stripped = clean_list_item(line)
        if re.search(r"\b(france|paris|toulouse|courbevoie|boulogne|beijing|london)\b", stripped, flags=re.IGNORECASE):
            return stripped
    return None


def clean_heading(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = re.sub(r"\s+", " ", text.replace("*", "")).strip(" -")
    return cleaned or None


def clean_list_item(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^[-*+]\s+", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("*", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_title(title: str) -> str:
    normalized = (
        title.lower()
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("É", "e")
        .replace("È", "e")
        .replace("Ê", "e")
    )
    return re.sub(r"\s+", " ", normalized).strip()


def unique_preserve_order(values) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            unique.append(cleaned)
    return unique
