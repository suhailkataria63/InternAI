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
- Return projects as objects with name, description, and technologies.
- Do not invent facts that are not present in the resume.

Resume text:
{resume_text}
"""


SKILL_ALIASES = {
    "Python": ("python",),
    "JavaScript": ("javascript", "java script"),
    "TypeScript": ("typescript", "type script"),
    "React": ("react", "react.js", "reactjs"),
    "Next.js": ("next.js", "nextjs", "next js"),
    "Node.js": ("node.js", "nodejs", "node js"),
    "FastAPI": ("fastapi", "fast api"),
    "Django": ("django",),
    "Flask": ("flask",),
    "Machine Learning": ("machine learning", "ml"),
    "Deep Learning": ("deep learning", "dl"),
    "NLP": ("nlp", "natural language processing"),
    "Data Analysis": ("data analysis", "data analytics"),
    "SQL": ("sql",),
    "PostgreSQL": ("postgresql", "postgres"),
    "SQLite": ("sqlite", "sqlite3"),
    "Pandas": ("pandas",),
    "NumPy": ("numpy", "num py"),
    "Scikit-learn": ("scikit-learn", "scikit learn", "sklearn"),
    "TensorFlow": ("tensorflow",),
    "PyTorch": ("pytorch", "torch"),
    "LangChain": ("langchain",),
    "LangGraph": ("langgraph",),
    "CrewAI": ("crewai", "crew ai"),
    "RAG": ("rag", "retrieval augmented generation"),
    "AI Agents": ("ai agents", "agentic ai"),
    "Docker": ("docker",),
    "Git": ("git",),
    "GitHub": ("github", "git hub"),
    "REST API": ("rest api", "restful api", "apis"),
    "Tailwind CSS": ("tailwind css", "tailwind"),
    "HTML": ("html",),
    "CSS": ("css",),
}

SECTION_HEADERS = {
    "education": ("education", "academic background", "academics"),
    "skills": ("skills", "technical skills", "core skills", "technologies"),
    "projects": ("projects", "academic projects", "personal projects"),
    "experience": ("experience", "work experience", "internship", "internships"),
    "certifications": ("certifications", "certificates", "licenses"),
}

EDUCATION_KEYWORDS = (
    "b.tech",
    "btech",
    "bachelor",
    "artificial intelligence",
    "data science",
    "ai&ds",
    "ai and ds",
    "3rd year",
    "third year",
    "6th semester",
    "sixth semester",
    "cgc landran",
    "chandigarh group of colleges",
    "ikgptu",
)

CERTIFICATION_KEYWORDS = (
    "certification",
    "certified",
    "certificate",
    "coursera",
    "udemy",
    "google",
    "microsoft",
    "ibm",
    "aws",
    "ec-council",
)

NAME_BLOCKLIST = {
    "resume",
    "curriculum vitae",
    "cv",
    "education",
    "skills",
    "projects",
    "experience",
    "certifications",
}


def analyze_resume_text(resume_text: str) -> dict:
    """Analyze raw resume text and return a structured candidate profile."""
    cleaned_text = clean_text(resume_text)
    lines = split_lines(cleaned_text)
    skills = extract_skills(cleaned_text)

    profile = {
        "name": extract_name(cleaned_text, lines),
        "email": extract_email(cleaned_text),
        "phone": extract_phone(cleaned_text),
        "education": extract_education(cleaned_text, lines),
        "skills": skills,
        "projects": extract_projects(cleaned_text, lines, skills),
        "experience": extract_experience(cleaned_text, lines),
        "certifications": extract_certifications(cleaned_text, lines),
        "strengths": [],
        "improvement_areas": [],
    }

    profile["strengths"] = generate_strengths(
        profile["skills"],
        profile["projects"],
        profile["experience"],
    )
    profile["improvement_areas"] = generate_improvement_areas(profile)

    return profile


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_lines(text: str) -> list:
    return [line.strip(" -•\t") for line in text.splitlines() if line.strip(" -•\t")]


def extract_name(text: str, lines: list) -> str:
    label_match = re.search(
        r"\bname\s*:\s*([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,3})",
        text,
        flags=re.IGNORECASE,
    )
    if label_match:
        return label_match.group(1).strip()

    for line in lines[:8]:
        if _looks_like_person_name(line):
            return line

    patterns = (
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+is\s+pursuing\b",
        r"\bI\s+am\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b",
        r"\bMy\s+name\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match and _looks_like_person_name(match.group(1)):
            return match.group(1).strip()

    return ""


def extract_email(text: str) -> str:
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    match = re.search(
        r"(?:(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3,5}\)?[-.\s]?)?\d{3,5}[-.\s]?\d{4,5})",
        text,
    )
    return match.group(0).strip() if match else ""


def extract_education(text: str, lines: list) -> list:
    education_items = _section_items(lines, "education")

    for line in lines:
        if _contains_any(line, EDUCATION_KEYWORDS):
            education_items.append(line)

    phrase_patterns = (
        r"pursuing\s+([^.\n]*(?:b\.?tech|bachelor|artificial intelligence|data science|ai&ds|ai and ds)[^.\n]*)",
        r"student\s+of\s+([^.\n]*(?:b\.?tech|bachelor|artificial intelligence|data science|ai&ds|ai and ds)[^.\n]*)",
    )
    for pattern in phrase_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            education_items.append(match.group(1).strip())

    cleaned_items = []
    for item in education_items:
        education = _clean_education_item(item)
        if education:
            cleaned_items.append(education)

    return _unique_preserve_order(_clean_items(cleaned_items))


def extract_skills(text: str) -> list:
    lowered_text = text.lower()
    found_skills = []

    for display_name, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            if _skill_alias_found(lowered_text, alias):
                found_skills.append(display_name)
                break

    skill_lines = _section_items(split_lines(text), "skills")
    for line in skill_lines:
        for part in re.split(r"[,|;/]", line):
            candidate = part.strip()
            display = _skill_display_name(candidate)
            if display:
                found_skills.append(display)

    return _unique_preserve_order(found_skills)


def extract_projects(text: str, lines: list, skills: list) -> list:
    project_chunks = _section_items(lines, "projects")

    phrase_patterns = (
        r"projects?\s+include\s+([^.\n]+)",
        r"project\s*:\s*([^.\n]+)",
        r"another\s+project\s+is\s+([^.\n]+)",
    )
    for pattern in phrase_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            project_chunks.extend(_split_project_chunk(match.group(1)))

    for line in lines:
        lowered = line.lower()
        if (
            (" project" in lowered or lowered.startswith("project"))
            and not _is_section_header(line)
            and not re.search(
                r"projects?\s+include|another\s+project\s+is|project\s*:",
                line,
                flags=re.IGNORECASE,
            )
        ):
            project_chunks.extend(_split_project_chunk(line))

    projects = []
    for chunk in _clean_items(project_chunks):
        name = _extract_project_name(chunk)
        if not name:
            continue
        projects.append(
            {
                "name": name,
                "description": chunk,
                "technologies": _skills_in_text(chunk, skills),
            }
        )

    return _unique_projects(projects)


def extract_experience(text: str, lines: list) -> list:
    experience_items = _section_items(lines, "experience")

    patterns = (
        r"experience\s+includes\s+([^.\n]+)",
        r"\b([A-Z][A-Za-z ]+\s+Intern\s+at\s+[^.\n]+)",
        r"\bInternship\s+at\s+([^.\n]+)",
        r"\bWorked\s+as\s+([^.\n]+)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            experience_items.append(match.group(1).strip())

    for line in lines:
        if re.search(r"\b(intern|internship|worked as|work experience)\b", line, re.IGNORECASE) and not re.search(
            r"experience\s+includes|internship\s+at|worked\s+as",
            line,
            re.IGNORECASE,
        ):
            experience_items.append(line)

    return _dedupe_contained_items(_unique_preserve_order(_clean_items(experience_items)))


def extract_certifications(text: str, lines: list) -> list:
    certification_items = _section_items(lines, "certifications")

    for line in lines:
        if _contains_any(line, CERTIFICATION_KEYWORDS):
            certification_items.append(line)

    return _unique_preserve_order(_clean_items(certification_items))


def generate_strengths(skills: list, projects: list, experience: list) -> list:
    normalized_skills = {skill.lower() for skill in skills}
    strengths = []

    if "python" in normalized_skills and (
        "machine learning" in normalized_skills or "deep learning" in normalized_skills
    ):
        strengths.append("Strong AI/ML and Python foundation")
    if projects:
        strengths.append("Has practical project experience")
    if normalized_skills & {"react", "next.js", "javascript", "typescript", "tailwind css"}:
        strengths.append("Can build user-facing dashboards")
    if normalized_skills & {"fastapi", "django", "flask"}:
        strengths.append("Has backend API exposure")
    if experience:
        strengths.append("Has internship/work experience")
    if normalized_skills & {"sql", "postgresql", "sqlite"}:
        strengths.append("Has database exposure")

    return _unique_preserve_order(strengths)


def generate_improvement_areas(profile: dict) -> list:
    skills = {skill.lower() for skill in profile.get("skills", [])}
    project_text = " ".join(
        project.get("description", "") if isinstance(project, dict) else str(project)
        for project in profile.get("projects", [])
    ).lower()
    full_text = " ".join(str(value) for value in profile.values()).lower()
    improvement_areas = []

    if not profile.get("email"):
        improvement_areas.append("Add a professional email address.")
    if not profile.get("phone"):
        improvement_areas.append("Add a phone number for recruiter contact.")
    if not re.search(r"\b\d+%|\b\d+\+|\bimproved\b|\breduced\b|\bincreased\b", project_text):
        improvement_areas.append("Add measurable project outcomes.")
    if "deploy" not in project_text and "live" not in project_text:
        improvement_areas.append("Add deployment links for key projects.")
    if "github" not in full_text:
        improvement_areas.append("Add GitHub links for projects.")
    if not profile.get("certifications"):
        improvement_areas.append("Add relevant certifications if available.")
    if not skills & {"fastapi", "django", "flask", "sql", "postgresql", "sqlite"}:
        improvement_areas.append("Add backend or database skills if relevant to target roles.")

    return _unique_preserve_order(improvement_areas)


def _section_items(lines: list, section_name: str) -> list:
    aliases = SECTION_HEADERS[section_name]
    items = []
    active = False

    for line in lines:
        if _header_for(line) == section_name:
            active = True
            remainder = _after_colon(line)
            if remainder:
                items.append(remainder)
            continue
        if active and _is_section_header(line):
            break
        if active:
            items.append(line)

    return items


def _header_for(line: str) -> str:
    normalized = line.lower().strip().rstrip(":")
    for section_name, aliases in SECTION_HEADERS.items():
        if normalized in aliases:
            return section_name
        if any(normalized.startswith(alias + ":") for alias in aliases):
            return section_name
    return ""


def _is_section_header(line: str) -> bool:
    return bool(_header_for(line))


def _after_colon(line: str) -> str:
    return line.split(":", 1)[1].strip() if ":" in line else ""


def _looks_like_person_name(value: str) -> bool:
    value = value.strip()
    lowered = value.lower().strip(":")
    if lowered in NAME_BLOCKLIST or _is_section_header(value):
        return False
    if any(char.isdigit() for char in value) or "@" in value:
        return False
    if _contains_any(value, EDUCATION_KEYWORDS) or _contains_any(value, SKILL_ALIASES.keys()):
        return False
    if any(word in lowered for word in ("project", "system", "dashboard", "intern", "developer")):
        return False
    words = value.split()
    return 2 <= len(words) <= 4 and all(re.match(r"^[A-Z][A-Za-z.'-]+$", word) for word in words)


def _contains_any(value: str, keywords) -> bool:
    lowered = value.lower()
    return any(str(keyword).lower() in lowered for keyword in keywords)


def _clean_education_item(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip(" -•\t.")
    if not text or not _contains_any(text, EDUCATION_KEYWORDS):
        return ""

    stop_phrases = (
        "skills include",
        "projects include",
        "another project",
        "experience includes",
        "he has skills",
        "she has skills",
        "i have skills",
    )
    stop_positions = [
        text.lower().find(phrase)
        for phrase in stop_phrases
        if text.lower().find(phrase) != -1
    ]
    if stop_positions:
        text = text[: min(stop_positions)].strip(" -•\t.,")

    sentence_match = re.search(
        r"([^.!?\n]*(?:b\.?tech|bachelor|artificial intelligence|data science|ai&ds|ai and ds)[^.!?\n]*)",
        text,
        flags=re.IGNORECASE,
    )
    if sentence_match:
        text = sentence_match.group(1).strip(" -•\t.,")

    text = re.sub(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\s+is\s+pursuing\s+", "", text)
    text = re.sub(r"^(?:he|she|i)\s+is\s+pursuing\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^pursuing\s+", "", text, flags=re.IGNORECASE)

    if len(text) > 220:
        text = text[:220].rsplit(" ", 1)[0].strip(" -•\t.,")

    return text


def _skill_alias_found(lowered_text: str, alias: str) -> bool:
    escaped = re.escape(alias.lower())
    if alias.lower() in {"c++", "c#", "next.js", "node.js"}:
        return alias.lower() in lowered_text
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", lowered_text))


def _skill_display_name(candidate: str) -> str:
    lowered = candidate.lower()
    for display_name, aliases in SKILL_ALIASES.items():
        if lowered == display_name.lower() or lowered in aliases:
            return display_name
    return ""


def _skills_in_text(text: str, skills: list) -> list:
    lowered = text.lower()
    return [skill for skill in skills if skill.lower() in lowered]


def _split_project_chunk(chunk: str) -> list:
    chunk = re.sub(r"^projects?\s*:\s*", "", chunk.strip(), flags=re.IGNORECASE)
    chunk = re.sub(r"^projects?\s+include\s+", "", chunk, flags=re.IGNORECASE)
    chunk = re.sub(r"^another\s+project\s+is\s+", "", chunk, flags=re.IGNORECASE)
    chunk = re.sub(r"^project\s*:\s*", "", chunk, flags=re.IGNORECASE)
    return [
        part.strip(" .")
        for part in re.split(r"\s*;\s*", chunk)
        if part.strip(" .")
    ]


def _extract_project_name(chunk: str) -> str:
    cleaned = chunk.strip(" .")
    patterns = (
        r"([^,.;]+?(?:System|Modeling|Model|Dashboard|App|Application|Platform|Tool|API|Website))\b",
        r"([A-Z][A-Za-z0-9&' -]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if match:
            name = match.group(1).strip(" -")
            if len(name.split()) >= 2:
                return name
    return cleaned[:80]


def _clean_items(items: list) -> list:
    cleaned_items = []
    for item in items:
        item = re.sub(r"\s+", " ", str(item)).strip(" -•\t.")
        if item and not _is_section_header(item):
            cleaned_items.append(item)
    return cleaned_items


def _unique_preserve_order(items: list) -> list:
    seen = set()
    unique_items = []

    for item in items:
        key = str(item).lower()
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    return unique_items


def _unique_projects(projects: list) -> list:
    seen = set()
    unique_projects = []
    for project in projects:
        key = project["name"].lower()
        if key not in seen:
            seen.add(key)
            unique_projects.append(project)
    return unique_projects


def _dedupe_contained_items(items: list) -> list:
    deduped = []
    for item in sorted(items, key=len):
        lowered = item.lower()
        if any(existing.lower() in lowered for existing in deduped):
            continue
        deduped.append(item)
    return deduped
