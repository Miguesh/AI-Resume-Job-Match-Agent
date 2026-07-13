"""Canonical skill naming used by extraction and deterministic scoring."""

from __future__ import annotations

import re

from resume_matcher.domain.entities import Skill

SKILL_ALIASES: dict[str, str] = {
    "amazon web services": "aws",
    "aws cloud": "aws",
    "google cloud platform": "gcp",
    "microsoft azure": "azure",
    "k8s": "kubernetes",
    "postgres": "postgresql",
    "postgre sql": "postgresql",
    "node js": "node.js",
    "react js": "react",
    "vue js": "vue.js",
    "next js": "next.js",
    "fast api": "fastapi",
    "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "machine learning": "machine learning",
    "natural language processing": "nlp",
    "large language models": "llm",
    "large language model": "llm",
    "continuous integration": "ci/cd",
    "continuous delivery": "ci/cd",
    "github actions": "github actions",
    "rest api": "rest apis",
    "restful api": "rest apis",
}

CANONICAL_DISPLAY: dict[str, str] = {
    "ai": "AI",
    "api": "API",
    "aws": "AWS",
    "ci/cd": "CI/CD",
    "css": "CSS",
    "fastapi": "FastAPI",
    "gcp": "GCP",
    "github actions": "GitHub Actions",
    "graphql": "GraphQL",
    "html": "HTML",
    "javascript": "JavaScript",
    "kubernetes": "Kubernetes",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "llm": "LLM",
    "ml": "ML",
    "nlp": "NLP",
    "numpy": "NumPy",
    "openai": "OpenAI",
    "postgresql": "PostgreSQL",
    "pydantic": "Pydantic",
    "pytorch": "PyTorch",
    "pytest": "pytest",
    "scikit-learn": "scikit-learn",
    "sql": "SQL",
    "sqlalchemy": "SQLAlchemy",
    "tensorflow": "TensorFlow",
    "typescript": "TypeScript",
    "rest apis": "REST APIs",
}


def normalize_skill(value: str) -> str:
    normalized = value.casefold().strip()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9+#./-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" .-/")
    return SKILL_ALIASES.get(normalized, normalized)


def display_skill(normalized: str) -> str:
    return CANONICAL_DISPLAY.get(normalized, normalized.title())


def create_skill(value: str) -> Skill:
    normalized = normalize_skill(value)
    return Skill(name=display_skill(normalized), normalized_name=normalized)


def deduplicate_skills(values: list[str] | tuple[str, ...]) -> tuple[Skill, ...]:
    skills: dict[str, Skill] = {}
    for value in values:
        skill = create_skill(value)
        if skill.normalized_name:
            skills.setdefault(skill.normalized_name, skill)
    return tuple(sorted(skills.values(), key=lambda item: item.normalized_name))
