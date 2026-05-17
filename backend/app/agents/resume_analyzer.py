import re


RESUME_ANALYZER_PROMPT_TEMPLATE = """
You are the Resume Analyzer Agent for InternAI.

Convert the resume text into structured JSON with these fields:
- name
- email
- phone
- education
- skills
- projects
- experience
- certifications
- strengths
- improvement_areas

Rules:
- Return valid JSON only.
- Use empty strings for unknown single-value fields.
- Use empty arrays for unknown list fields.
- Do not invent facts that are not present in the resume.

Resume text:
{resume_text}
"""


SECTION_ALIASES = {
    "education": {"education", "academic background", "academics"},
    "skills": {"skills", "technical skills", "core skills", "technologies"},
    "projects": {"projects", "academic projects", "personal projects"},
    "experience": {"experience", "work experience", "internship", "internships"},
    "certifications": {"certifications", "certificates", "licenses"},
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
    "git",
    "github",
    "linux",
    "aws",
    "machine learning",
    "deep learning",
    "data analysis",
    "pandas",
    "numpy",
    "langchain",
    "langgraph",
)


def analyze_resume_text(resume_text: str) -> dict:
    """Analyze raw resume text and return a structured candidate profile."""
    cleaned_text = _normalize_text(resume_text)
    sections = _extract_sections(cleaned_text)

    profile = {
        "name": _extract_name(cleaned_text),
        "email": _extract_email(cleaned_text),
        "phone": _extract_phone(cleaned_text),
        "education": _extract_section_items(sections, "education"),
        "skills": _extract_skills(cleaned_text, sections),
        "projects": _extract_section_items(sections, "projects"),
        "experience": _extract_section_items(sections, "experience"),
        "certifications": _extract_section_items(sections, "certifications"),
        "strengths": [],
        "improvement_areas": [],
    }

    profile["strengths"] = _build_strengths(profile)
    profile["improvement_areas"] = _build_improvement_areas(profile)

    return profile


def _normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _extract_email(text: str) -> str:
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    return match.group(0) if match else ""


def _extract_phone(text: str) -> str:
    match = re.search(
        r"(?:(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3,5}\)?[-.\s]?)?\d{3,5}[-.\s]?\d{4})",
        text,
    )
    return match.group(0).strip() if match else ""


def _extract_name(text: str) -> str:
    for line in text.splitlines()[:8]:
        lowered = line.lower()
        if "@" in line or any(char.isdigit() for char in line):
            continue
        if _match_section_name(line) or lowered in {"resume", "curriculum vitae", "cv"}:
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and all(word[:1].isupper() for word in words):
            return line
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


def _extract_section_items(sections: dict[str, str], section_name: str) -> list[str]:
    section_text = sections.get(section_name, "")
    if not section_text:
        return []

    items: list[str] = []
    for line in section_text.splitlines():
        item = line.strip(" -•\t")
        if item:
            items.append(item)

    return _unique_preserve_order(items)


def _extract_skills(text: str, sections: dict[str, str]) -> list[str]:
    found_skills: list[str] = []
    lowered_text = text.lower()

    for skill in KNOWN_SKILLS:
        if skill in lowered_text:
            found_skills.append(_format_skill(skill))

    skills_section = sections.get("skills", "")
    for part in re.split(r"[,|/;\n]", skills_section):
        skill = part.strip(" -•\t")
        if 1 < len(skill) <= 40:
            found_skills.append(skill)

    return _unique_preserve_order(found_skills)


def _build_strengths(profile: dict) -> list[str]:
    strengths: list[str] = []

    if profile["skills"]:
        strengths.append("Includes a clear skills section.")
    if profile["projects"]:
        strengths.append("Highlights project experience.")
    if profile["experience"]:
        strengths.append("Includes practical work or internship experience.")
    if profile["education"]:
        strengths.append("Includes education details.")
    if profile["certifications"]:
        strengths.append("Includes certifications or credentials.")

    return strengths


def _build_improvement_areas(profile: dict) -> list[str]:
    improvement_areas: list[str] = []

    if not profile["email"]:
        improvement_areas.append("Add a professional email address.")
    if not profile["phone"]:
        improvement_areas.append("Add a phone number for recruiter contact.")
    if not profile["skills"]:
        improvement_areas.append("Add a dedicated skills section.")
    if not profile["projects"]:
        improvement_areas.append("Add projects with measurable outcomes.")
    if not profile["experience"]:
        improvement_areas.append("Add internship, work, volunteer, or leadership experience.")

    return improvement_areas


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
