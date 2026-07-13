from __future__ import annotations

import re
from collections import Counter

from resume_matcher.domain.entities import (
    EducationLevel,
    Experience,
    JobProfile,
    MatchAnalysis,
    OptimizationChange,
    OptimizedResume,
    ResumeProfile,
)
from resume_matcher.infrastructure.ai.contracts import (
    EducationContract,
    ExperienceContract,
    JobExtractionContract,
    ResumeExtractionContract,
)
from resume_matcher.infrastructure.ai.mappers import job_from_contract, resume_from_contract

_SKILLS = (
    "Python",
    "FastAPI",
    "Pydantic",
    "Django",
    "Flask",
    "SQL",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Redis",
    "SQLAlchemy",
    "Alembic",
    "Docker",
    "Kubernetes",
    "Terraform",
    "AWS",
    "Azure",
    "GCP",
    "Git",
    "GitHub Actions",
    "CI/CD",
    "Linux",
    "pytest",
    "unit testing",
    "integration testing",
    "microservices",
    "REST API",
    "GraphQL",
    "machine learning",
    "deep learning",
    "NLP",
    "LLM",
    "RAG",
    "LangChain",
    "LlamaIndex",
    "OpenAI",
    "pandas",
    "NumPy",
    "scikit-learn",
    "PyTorch",
    "TensorFlow",
    "Spark",
    "Airflow",
    "Celery",
    "React",
    "TypeScript",
    "JavaScript",
    "Java",
    "Go",
    "C#",
    "C++",
    "Agile",
    "Scrum",
    "leadership",
    "communication",
)

_KEYWORD_STOP_WORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "but",
    "for",
    "from",
    "have",
    "into",
    "our",
    "role",
    "that",
    "the",
    "their",
    "this",
    "using",
    "with",
    "will",
    "work",
    "you",
    "your",
}


class LocalResumeIntelligence:
    """Deterministic no-network adapter for demos, development, and tests."""

    async def extract_resume(self, text: str) -> ResumeProfile:
        lines = [line.strip(" \t-•") for line in text.splitlines() if line.strip()]
        skills = self._extract_skills(text)
        email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        phone_match = re.search(r"(?:\+?\d[\d ().-]{7,}\d)", text)
        email = email_match.group(0) if email_match else None
        phone = phone_match.group(0) if phone_match else None
        name = lines[0] if lines and len(lines[0]) <= 80 and "@" not in lines[0] else None
        years = self._years(text)
        education = self._education(text)
        experiences = self._experiences(lines, skills)
        summary = self._section_text(lines, ("summary", "profile"), max_lines=4)
        contract = ResumeExtractionContract(
            name=name,
            headline=lines[1] if len(lines) > 1 and len(lines[1]) <= 120 else None,
            summary=summary,
            email=email,
            phone=phone,
            location=self._location(lines, email=email),
            skills=skills,
            experiences=experiences,
            education=education,
            total_years_experience=years,
            keywords=self._keywords(text),
        )
        return resume_from_contract(contract, text)

    async def extract_job(self, text: str) -> JobProfile:
        lines = [line.strip(" \t-•") for line in text.splitlines() if line.strip()]
        found = self._extract_skills(text)
        preferred: list[str] = []
        for line in lines:
            if re.search(r"\b(preferred|nice to have|bonus|desired)\b", line, re.I):
                preferred.extend(self._extract_skills(line))
        preferred_set = {value.casefold() for value in preferred}
        required = [value for value in found if value.casefold() not in preferred_set]
        title = lines[0][:250] if lines else "Untitled role"
        company: str | None = None
        title_match = re.match(r"(.+?)\s+(?:at|@)\s+(.+)", title, re.I)
        if title_match:
            title, company = title_match.group(1).strip(), title_match.group(2).strip()
        responsibilities = tuple(
            line
            for line in lines
            if re.match(
                r"(?i)(build|create|design|develop|deliver|implement|lead|maintain|manage|own|work)",
                line,
            )
        )[:30]
        contract = JobExtractionContract(
            title=title,
            company=company,
            summary=" ".join(lines[1:4]) or None,
            required_skills=required,
            preferred_skills=preferred,
            responsibilities=list(responsibilities),
            education_level=self._education_level(text),
            minimum_years_experience=self._years(text),
            keywords=self._keywords(text),
        )
        return job_from_contract(contract, text)

    async def optimize_resume(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        match: MatchAnalysis,
    ) -> OptimizedResume:
        target_skills = {
            skill.normalized_name for skill in (*job.required_skills, *job.preferred_skills)
        }
        ordered_skills = tuple(
            sorted(
                resume.skills,
                key=lambda skill: (
                    skill.normalized_name not in target_skills,
                    skill.name.casefold(),
                ),
            )
        )
        matched = [skill.name for skill in ordered_skills if skill.normalized_name in target_skills]
        summary = resume.summary
        changes: list[OptimizationChange] = []
        if matched:
            base = (
                summary
                or f"Professional with {resume.total_years_experience:g} years of experience"
            ).rstrip(".")
            revised = f"{base}. Relevant strengths include {', '.join(matched[:6])}."
            if revised != summary:
                changes.append(
                    OptimizationChange(
                        section="summary",
                        before=summary,
                        after=revised,
                        reason="Surfaces job-relevant skills already present in the source resume.",
                        source_evidence=tuple(matched[:6]),
                    )
                )
                summary = revised

        job_terms = {keyword.casefold() for keyword in job.keywords}
        optimized_experience: list[Experience] = []
        for item in resume.experiences:
            bullets = tuple(
                sorted(
                    item.bullets,
                    key=lambda bullet: (
                        not any(term in bullet.casefold() for term in job_terms),
                        item.bullets.index(bullet),
                    ),
                )
            )
            optimized_experience.append(
                Experience(
                    title=item.title,
                    company=item.company,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    location=item.location,
                    bullets=bullets,
                    skills=item.skills,
                )
            )
            if bullets != item.bullets:
                changes.append(
                    OptimizationChange(
                        section=f"experience:{item.company}",
                        before="\n".join(item.bullets),
                        after="\n".join(bullets),
                        reason="Moves the most job-relevant, unchanged achievements first.",
                        source_evidence=bullets,
                    )
                )
        if ordered_skills != resume.skills:
            changes.append(
                OptimizationChange(
                    section="skills",
                    before=", ".join(skill.name for skill in resume.skills),
                    after=", ".join(skill.name for skill in ordered_skills),
                    reason="Prioritizes verified skills that appear in the job description.",
                    source_evidence=tuple(skill.name for skill in ordered_skills),
                )
            )
        return OptimizedResume(
            name=resume.name,
            headline=resume.headline,
            summary=summary,
            email=resume.email,
            phone=resume.phone,
            location=resume.location,
            skills=ordered_skills,
            experiences=tuple(optimized_experience),
            education=resume.education,
            certifications=resume.certifications,
            changes=tuple(changes),
            warnings=(
                "Local mode only reorders existing evidence and adds a summary from verified "
                "skills.",
                "Review every statement before submitting the resume.",
            ),
        )

    @staticmethod
    def _extract_skills(text: str) -> list[str]:
        return [
            skill for skill in _SKILLS if re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", text, re.I)
        ]

    @staticmethod
    def _years(text: str) -> float:
        values = [
            float(match) for match in re.findall(r"\b(\d{1,2}(?:\.\d)?)\+?\s+years?\b", text, re.I)
        ]
        return max(values, default=0.0)

    @staticmethod
    def _education_level(text: str) -> EducationLevel:
        lowered = text.casefold()
        if re.search(r"\b(ph\.?d|doctorate|doctoral)\b", lowered):
            return EducationLevel.DOCTORATE
        if re.search(r"\b(master'?s?|m\.?s\.?|m\.?a\.?|mba)\b", lowered):
            return EducationLevel.MASTER
        if re.search(r"\b(bachelor'?s?|b\.?s\.?|b\.?a\.?)\b", lowered):
            return EducationLevel.BACHELOR
        if re.search(r"\bassociate'?s?\b", lowered):
            return EducationLevel.ASSOCIATE
        if "high school" in lowered:
            return EducationLevel.HIGH_SCHOOL
        return EducationLevel.NONE

    @classmethod
    def _education(cls, text: str) -> list[EducationContract]:
        level = cls._education_level(text)
        if level is EducationLevel.NONE:
            return []
        degree_line = next(
            (
                line.strip()
                for line in text.splitlines()
                if re.search(r"(?i)bachelor|master|doctor|ph\.?d|associate", line)
            ),
            level.value.replace("_", " ").title(),
        )
        institution_match = re.search(r"(?im)^(.{2,120}(?:university|college|institute).*)$", text)
        return [
            EducationContract(
                institution=(
                    institution_match.group(1).strip() if institution_match else "Not specified"
                ),
                degree=degree_line[:250],
                level=level,
            )
        ]

    @staticmethod
    def _experiences(lines: list[str], skills: list[str]) -> list[ExperienceContract]:
        experiences: list[ExperienceContract] = []
        for index, line in enumerate(lines):
            match = LocalResumeIntelligence._experience_heading(line)
            if not match:
                continue
            bullets: list[str] = []
            for following in lines[index + 1 : index + 8]:
                if LocalResumeIntelligence._experience_heading(following):
                    break
                if LocalResumeIntelligence._is_section_heading(following):
                    break
                if re.search(r"(?i)\b(bachelor|master|doctor|ph\.?d|associate)\b", following):
                    break
                if len(following) > 20:
                    bullets.append(following)
            experiences.append(
                ExperienceContract(
                    title=match.group(1).strip(),
                    company=match.group(2).strip(),
                    bullets=bullets,
                    skills=[
                        skill
                        for skill in skills
                        if any(skill.casefold() in bullet.casefold() for bullet in bullets)
                    ],
                )
            )
        return experiences

    @staticmethod
    def _experience_heading(line: str) -> re.Match[str] | None:
        if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", line):
            return None
        return re.match(
            r"^(.{2,100}?)\s+(?:at|@)\s+(.{2,100}?)(?:\s+\||$)",
            line,
            re.I,
        )

    @staticmethod
    def _location(lines: list[str], *, email: str | None) -> str | None:
        """Extract an explicit city/region token from the resume header only."""
        for line in lines[:6]:
            for value in re.split(r"\s*[|•·]\s*", line):
                candidate = value.strip()
                if not candidate or (email and email.casefold() in candidate.casefold()):
                    continue
                if re.search(r"(?:\+?\d[\d ().-]{7,}\d)", candidate):
                    continue
                if re.fullmatch(r"(?i)remote(?:\s*[-\u2013\u2014]\s*[a-z .'-]+)?", candidate):
                    return candidate
                if re.fullmatch(r"[A-Za-z .'-]{2,80},\s*[A-Za-z .'-]{2,40}", candidate):
                    return candidate
        return None

    @staticmethod
    def _is_section_heading(line: str) -> bool:
        return line.casefold().rstrip(":") in {
            "summary",
            "profile",
            "skills",
            "technical skills",
            "experience",
            "work experience",
            "education",
            "certifications",
            "projects",
        }

    @staticmethod
    def _section_text(lines: list[str], headings: tuple[str, ...], max_lines: int) -> str | None:
        for index, line in enumerate(lines):
            if line.casefold().rstrip(":") in headings:
                values: list[str] = []
                for value in lines[index + 1 : index + 1 + max_lines]:
                    if LocalResumeIntelligence._is_section_heading(value):
                        break
                    if LocalResumeIntelligence._experience_heading(value):
                        break
                    values.append(value)
                return " ".join(values) or None
        return None

    @staticmethod
    def _keywords(text: str) -> list[str]:
        tokens = re.findall(r"\b[a-z][a-z0-9+#.-]{2,}\b", text.casefold())
        counts = Counter(token for token in tokens if token not in _KEYWORD_STOP_WORDS)
        return [token for token, _ in counts.most_common(20)]
