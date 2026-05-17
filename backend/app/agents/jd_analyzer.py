import re


JD_ANALYZER_PROMPT_TEMPLATE = """
You are the JD Analyzer Agent for InternAI.

Convert the internship or job description into structured JSON with these fields:
- role_title
- company_name
- required_skills
- preferred_skills
- responsibilities
- eligibility
- stipend
- duration
- location
- work_mode
- keywords

Rules:
- Return valid JSON only.
- Use empty strings for unknown single-value fields.
- Use empty arrays for unknown list fields.
- Do not invent facts that are not present in the job description.

Job description:
{jd_text}
"""


SECTION_ALIASES = {
    "required_skills": {
        "required skills",
        "requirements",
        "must have",
        "must-have skills",
        "technical requirements",
    },
    "preferred_skills": {
        "preferred skills",
        "nice to have",
        "good to have",
        "bonus skills",
        "preferred qualifications",
    },
    "responsibilities": {
        "responsibilities",
        "roles and responsibilities",
        "what you will do",
        "job responsibilities",
        "key responsibilities",
    },
    "eligibility": {
        "eligibility",
        "eligibility criteria",
        "qualifications",
        "who can apply",
        "minimum qualifications",
    },
}

KNOWN_SKILLS = (
    "python",
    "java",
    "javascript",
    "typescript",
    "go",
    "golang",
    "c++",
    "c#",
    "sql",
    "html",
    "css",
    "react",
    "next.js",
    "node.js",
    "fastapi",
    "django",
    "flask",
    "tailwind",
    "sqlite",
    "postgresql",
    "mongodb",
    "docker",
    "kubernetes",
    "git",
    "github",
    "linux",
    "aws",
    "azure",
    "gcp",
    "machine learning",
    "deep learning",
    "data analysis",
    "data science",
    "pandas",
    "numpy",
    "tensorflow",
    "pytorch",
    "langchain",
    "langgraph",
    "communication",
    "problem solving",
    "teamwork",
)


def analyze_jd_text(jd_text: str) -> dict:
    """Analyze an internship or job description and return a structured profile."""
    cleaned_text = _normalize_text(jd_text)
    sections = _extract_sections(cleaned_text)

    job_profile = {
        "role_title": _extract_role_title(cleaned_text),
        "company_name": _extract_company_name(cleaned_text),
        "required_skills": _extract_required_skills(cleaned_text, sections),
        "preferred_skills": _extract_section_items(sections, "preferred_skills"),
        "responsibilities": _extract_section_items(sections, "responsibilities"),
        "eligibility": _extract_section_items(sections, "eligibility"),
        "stipend": _extract_stipend(cleaned_text),
        "duration": _extract_duration(cleaned_text),
        "location": _extract_location(cleaned_text),
        "work_mode": _extract_work_mode(cleaned_text),
        "keywords": [],
    }

    job_profile["keywords"] = _build_keywords(job_profile)

    return job_profile


def _normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _extract_role_title(text: str) -> str:
    patterns = (
        r"(?:role|position|title|job title)\s*:\s*(.+)",
        r"(.+\b(?:intern|internship|developer|engineer|analyst|designer|manager)\b.*)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_inline_value(match.group(1))
    return ""


def _extract_company_name(text: str) -> str:
    patterns = (
        r"(?:company|organization|employer)\s*:\s*(.+)",
        r"(?:at|with)\s+([A-Z][A-Za-z0-9&., ]{2,60})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_inline_value(match.group(1))
    return ""


def _extract_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    active_section = ""

    for line in text.splitlines():
        section_name = _match_section_name(line)
        if section_name:
            active_section = section_name
            sections.setdefault(active_section, [])
            continue

        if active_section:
            sections[active_section].append(line)

    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def _match_section_name(line: str) -> str:
    normalized = line.strip().lower().rstrip(":")
    for section_name, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return section_name
    return ""


def _extract_required_skills(text: str, sections: dict[str, str]) -> list[str]:
    found_skills = _extract_skills_from_text(text)
    found_skills.extend(_extract_skill_section_items(sections, "required_skills"))
    return _unique_preserve_order(found_skills)


def _extract_skills_from_text(text: str) -> list[str]:
    lowered_text = text.lower()
    skills: list[str] = []

    for skill in KNOWN_SKILLS:
        if skill in lowered_text:
            skills.append(_format_skill(skill))

    return skills


def _extract_section_items(sections: dict[str, str], section_name: str) -> list[str]:
    section_text = sections.get(section_name, "")
    if not section_text:
        return []

    items: list[str] = []
    for line in section_text.splitlines():
        for part in re.split(r";|\|", line):
            item = part.strip(" -•\t")
            if item:
                items.append(item)

    return _unique_preserve_order(items)


def _extract_skill_section_items(sections: dict[str, str], section_name: str) -> list[str]:
    section_text = sections.get(section_name, "")
    if not section_text:
        return []

    items: list[str] = []
    for part in re.split(r"[,;|/\n]", section_text):
        item = part.strip(" -•\t")
        if item:
            items.append(_format_skill(item.lower()))

    return _unique_preserve_order(items)


def _extract_stipend(text: str) -> str:
    patterns = (
        r"(?:stipend|salary|compensation|pay)\s*:\s*([^\n]+)",
        r"((?:₹|rs\.?|inr|\$)\s?[\d,]+(?:\s?-\s?(?:₹|rs\.?|inr|\$)?\s?[\d,]+)?(?:\s*(?:per month|/month|monthly|pm|per annum|pa))?)",
    )
    return _extract_first_match(text, patterns)


def _extract_duration(text: str) -> str:
    patterns = (
        r"(?:duration|term)\s*:\s*([^\n]+)",
        r"(\d+\s*(?:weeks?|months?|years?))",
    )
    return _extract_first_match(text, patterns)


def _extract_location(text: str) -> str:
    patterns = (
        r"(?:location|city)\s*:\s*([^\n]+)",
        r"(?:based in|located in)\s+([A-Z][A-Za-z, ]{2,60})",
    )
    return _extract_first_match(text, patterns)


def _extract_work_mode(text: str) -> str:
    lowered_text = text.lower()
    if "hybrid" in lowered_text:
        return "Hybrid"
    if "remote" in lowered_text or "work from home" in lowered_text:
        return "Remote"
    if "on-site" in lowered_text or "onsite" in lowered_text or "in office" in lowered_text:
        return "On-site"
    return ""


def _extract_first_match(text: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_inline_value(match.group(1))
    return ""


def _build_keywords(job_profile: dict) -> list[str]:
    keywords: list[str] = []

    keywords.extend(job_profile["required_skills"])
    keywords.extend(job_profile["preferred_skills"])

    for value in (
        job_profile["role_title"],
        job_profile["company_name"],
        job_profile["location"],
        job_profile["work_mode"],
    ):
        if value:
            keywords.append(value)

    return _unique_preserve_order(keywords)


def _clean_inline_value(value: str) -> str:
    return value.strip(" -•\t").split("\n")[0].strip()


def _format_skill(skill: str) -> str:
    special_cases = {
        "aws": "AWS",
        "css": "CSS",
        "html": "HTML",
        "sql": "SQL",
        "c#": "C#",
        "c++": "C++",
        "next.js": "Next.js",
        "node.js": "Node.js",
        "fastapi": "FastAPI",
        "sqlite": "SQLite",
        "github": "GitHub",
        "gcp": "GCP",
    }
    return special_cases.get(skill, skill.title())


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_items: list[str] = []

    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    return unique_items
