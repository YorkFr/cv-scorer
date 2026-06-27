from __future__ import annotations

import re

from .markdown_to_resume import parse_resume_markdown
from .resume_schema import ResumeProfile, ScoreReport, ScoreSection


def score_markdown(markdown: str) -> ScoreReport:
    return ResumeScorer().score(parse_resume_markdown(markdown))


class ResumeScorer:
    max_score = 100.0

    def score(self, profile: ResumeProfile) -> ScoreReport:
        sections = [
            self.score_contact_info(profile),
            self.score_structure(profile),
            self.score_experience(profile),
            self.score_education(profile),
            self.score_skills(profile),
            self.score_language_and_links(profile),
            self.score_readability(profile),
        ]
        total = round(sum(section.score for section in sections), 1)
        grade = grade_for_score(total)
        return ScoreReport(
            total_score=total,
            max_score=self.max_score,
            grade=grade,
            summary=summary_for_score(total, grade),
            sections=sections,
            profile=profile,
        )

    def score_contact_info(self, profile: ResumeProfile) -> ScoreSection:
        score = 0.0
        findings: list[str] = []
        suggestions: list[str] = []
        if profile.email:
            score += 5
            findings.append("Email detected.")
        else:
            suggestions.append("Add a professional email address.")
        if profile.phone:
            score += 4
            findings.append("Phone number detected.")
        else:
            suggestions.append("Add a phone number.")
        if profile.links:
            score += min(4, 2 * len(profile.links))
            findings.append("Professional link detected.")
        else:
            suggestions.append("Add LinkedIn, GitHub, or portfolio links where relevant.")
        if profile.location:
            score += 2
            findings.append("Location detected.")
        else:
            suggestions.append("Add city/country or mobility information.")
        return ScoreSection("contact_info", score, 15, findings, suggestions)

    def score_structure(self, profile: ResumeProfile) -> ScoreSection:
        titles = {section.title.lower() for section in profile.sections}
        score = 0.0
        findings: list[str] = []
        suggestions: list[str] = []
        if len(profile.sections) >= 4:
            score += 5
            findings.append("Multiple resume sections detected.")
        else:
            suggestions.append("Use clear section headings for profile, experience, education, and skills.")
        if profile.experience or profile.projects:
            score += 4
            findings.append("Experience or project section detected.")
        else:
            suggestions.append("Add work experience or project details.")
        if profile.education:
            score += 3
            findings.append("Education section detected.")
        else:
            suggestions.append("Add education details.")
        if profile.skills:
            score += 3
            findings.append("Skills content detected.")
        else:
            suggestions.append("Add a dedicated skills section.")
        if "page 1" in titles:
            findings.append("Page marker detected and ignored for content scoring.")
        return ScoreSection("structure", score, 15, findings, suggestions)

    def score_experience(self, profile: ResumeProfile) -> ScoreSection:
        text = "\n".join(profile.experience + profile.projects)
        score = 0.0
        findings: list[str] = []
        suggestions: list[str] = []
        if profile.experience:
            score += min(8, len(profile.experience) * 1.5)
            findings.append("Experience entries detected.")
        else:
            suggestions.append("Add professional experience entries.")
        if has_date_range(text):
            score += 5
            findings.append("Dates or date ranges detected in experience.")
        else:
            suggestions.append("Add dates for each experience.")
        if bullet_count(text) >= 3 or len(profile.experience) >= 3:
            score += 5
            findings.append("Experience includes bullet-style achievements.")
        else:
            suggestions.append("Use bullet points to describe responsibilities and achievements.")
        if contains_metric(text):
            score += 4
            findings.append("Quantified impact detected.")
        else:
            suggestions.append("Add metrics such as revenue, volume, accuracy, time saved, or portfolio size.")
        if len(text.split()) >= 80:
            score += 3
            findings.append("Experience section has meaningful detail.")
        else:
            suggestions.append("Add more detail to explain scope, tools, and outcomes.")
        return ScoreSection("experience", min(score, 25), 25, findings, suggestions)

    def score_education(self, profile: ResumeProfile) -> ScoreSection:
        text = "\n".join(profile.education)
        score = 0.0
        findings: list[str] = []
        suggestions: list[str] = []
        if profile.education:
            score += 6
            findings.append("Education details detected.")
        else:
            suggestions.append("Add degree, school, and dates.")
        if re.search(r"\b(master|bachelor|licence|degree|university|école|iae|management)\b", text, re.IGNORECASE):
            score += 4
            findings.append("Degree or institution signal detected.")
        else:
            suggestions.append("Clarify degree and institution names.")
        if has_date_range(text):
            score += 3
            findings.append("Education dates detected.")
        else:
            suggestions.append("Add education dates.")
        if len(text.split()) >= 15:
            score += 2
            findings.append("Education section contains supporting detail.")
        return ScoreSection("education", min(score, 15), 15, findings, suggestions)

    def score_skills(self, profile: ResumeProfile) -> ScoreSection:
        score = 0.0
        findings: list[str] = []
        suggestions: list[str] = []
        skill_count = len(profile.skills)
        if skill_count >= 6:
            score += 7
            findings.append("Several skills detected.")
        elif skill_count:
            score += 4
            suggestions.append("Add more role-relevant tools and methods.")
        else:
            suggestions.append("Add a skills section with concrete tools and methods.")
        if has_tool_signal(profile.skills):
            score += 4
            findings.append("Technical or tool skills detected.")
        else:
            suggestions.append("List concrete tools such as Excel, Power BI, SQL, Python, SAP, or domain systems.")
        if has_soft_skill_signal(profile.skills):
            score += 2
            findings.append("Soft skills detected.")
        if skill_count <= 18 and skill_count > 0:
            score += 2
            findings.append("Skills list length is readable.")
        elif skill_count > 18:
            suggestions.append("Group skills by category to improve readability.")
        return ScoreSection("skills", min(score, 15), 15, findings, suggestions)

    def score_language_and_links(self, profile: ResumeProfile) -> ScoreSection:
        score = 0.0
        findings: list[str] = []
        suggestions: list[str] = []
        if profile.languages:
            score += min(5, len(profile.languages) * 1.5)
            findings.append("Language information detected.")
        else:
            suggestions.append("Add language proficiency when relevant.")
        if any("linkedin" in link.lower() for link in profile.links):
            score += 3
            findings.append("LinkedIn profile detected.")
        elif profile.links:
            score += 2
            findings.append("External profile link detected.")
        else:
            suggestions.append("Add a professional online profile link.")
        if any("github" in link.lower() for link in profile.links):
            score += 2
            findings.append("GitHub link detected.")
        return ScoreSection("language_and_links", min(score, 10), 10, findings, suggestions)

    def score_readability(self, profile: ResumeProfile) -> ScoreSection:
        markdown = profile.raw_markdown
        words = markdown.split()
        score = 0.0
        findings: list[str] = []
        suggestions: list[str] = []
        if 120 <= len(words) <= 900:
            score += 2
            findings.append("Resume length is within a practical range.")
        else:
            suggestions.append("Keep the resume concise while retaining key achievements.")
        if bullet_count(markdown) >= 6:
            score += 2
            findings.append("Bullet points improve scanability.")
        else:
            suggestions.append("Use bullet points for responsibilities and achievements.")
        if len(profile.sections) >= 5:
            score += 1
            findings.append("Sectioning supports readability.")
        return ScoreSection("readability", min(score, 5), 5, findings, suggestions)


def has_date_range(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|avril|août|septembre|janvier|\d{4})\b",
            text,
            re.IGNORECASE,
        )
    )


def bullet_count(text: str) -> int:
    return len(re.findall(r"(?m)^\s*[-*+]\s+", text))


def contains_metric(text: str) -> bool:
    return bool(re.search(r"\b\d+(?:[.,]\d+)?\s*(?:%|k|m|pages?|clients?|years?|ans|mois|eur|€)?\b", text, re.IGNORECASE))


def has_tool_signal(skills: list[str]) -> bool:
    text = " ".join(skills)
    return bool(re.search(r"\b(excel|power bi|sql|python|sap|r-studio|spss|tableau|vba|power query)\b", text, re.IGNORECASE))


def has_soft_skill_signal(skills: list[str]) -> bool:
    text = " ".join(skills)
    return bool(re.search(r"\b(adaptable|rigoureuse|team|communication|synth[eé]tique|organized)\b", text, re.IGNORECASE))


def grade_for_score(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def summary_for_score(score: float, grade: str) -> str:
    if grade == "A":
        return f"Strong resume with clear structure and evidence. Score: {score:.1f}/100."
    if grade == "B":
        return f"Solid resume with room to strengthen impact and completeness. Score: {score:.1f}/100."
    if grade == "C":
        return f"Usable resume, but several important details should be improved. Score: {score:.1f}/100."
    return f"Resume needs substantial improvement before screening use. Score: {score:.1f}/100."
