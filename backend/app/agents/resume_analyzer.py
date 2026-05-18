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
    "AI": ("ai", "artificial intelligence"),
    "Deep Learning": ("deep learning", "dl"),
    "NLP": ("nlp", "natural language processing"),
    "Data Analysis": ("data analysis", "data analytics"),
    "Data Cleaning": ("data cleaning",),
    "Data Preprocessing": ("data preprocessing",),
    "Feature Engineering": ("feature engineering",),
    "EDA": ("exploratory data analysis", "eda"),
    "Regression": ("regression",),
    "Classification": ("classification",),
    "Predictive Modeling": ("predictive modeling",),
    "Time-Series Forecasting": ("time-series forecasting", "time series forecasting", "time-series", "time series"),
    "SQL": ("sql",),
    "PostgreSQL": ("postgresql", "postgres"),
    "SQLite": ("sqlite", "sqlite3"),
    "Pandas": ("pandas",),
    "NumPy": ("numpy", "num py"),
    "Scikit-learn": ("scikit-learn", "scikit learn", "sklearn"),
    "TensorFlow": ("tensorflow",),
    "Keras": ("keras",),
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
    "Neural Networks": ("neural networks", "neural network"),
    "Sentiment Analysis": ("sentiment analysis",),
    "Text Processing": ("text processing", "text preprocessing", "tokenization"),
}

SECTION_HEADERS = {
    "summary": ("summary", "summary of qualifications", "profile", "professional summary"),
    "education": ("education", "academic background", "academics"),
    "skills": ("skills", "technical skills", "core skills", "technologies", "technical skills"),
    "projects": ("projects", "academic projects", "personal projects", "relevant project experience", "project experience"),
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
    "diploma",
    "computer science",
    "engineering",
    "psbte",
    "cbse",
    "class x",
    "class 10",
    "currently pursuing",
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

PROJECT_TITLE_KEYWORDS = (
    "system",
    "analysis",
    "model",
    "modeling",
    "dashboard",
    "application",
    "platform",
    "tool",
    "api",
    "website",
    "prediction",
    "forecasting",
    "detection",
)

SUMMARY_PHRASES = (
    "student with",
    "solid foundation",
    "experienced in developing",
    "skilled in",
    "passionate about",
    "summary of qualifications",
)

SKILL_CATEGORY_PREFIXES = (
    "programming languages",
    "frontend development",
    "backend development",
    "data science",
    "machine learning",
    "deep learning",
    "libraries & tools",
    "tools",
)

DESCRIPTION_ACTION_VERBS = (
    "built",
    "conducted",
    "generated",
    "performed",
    "implemented",
    "developed",
    "classified",
    "deployed",
    "created",
    "designed",
    "trained",
)


def analyze_resume_text(resume_text: str) -> dict:
    """Analyze raw resume text and return a structured candidate profile."""
    cleaned_text = clean_text(resume_text)
    lines = normalize_resume_lines(cleaned_text)
    sections = detect_resume_sections(lines)
    skills = extract_skills(cleaned_text, sections)

    profile = {
        "name": extract_name(cleaned_text, lines),
        "email": extract_email(cleaned_text),
        "phone": extract_phone(cleaned_text),
        "education": extract_education(cleaned_text, lines, sections),
        "skills": skills,
        "projects": extract_projects(cleaned_text, lines, sections, skills),
        "experience": extract_experience(cleaned_text, lines, sections),
        "certifications": extract_certifications(cleaned_text, lines, sections),
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


def normalize_resume_lines(text: str) -> list:
    """Return clean resume lines while preserving useful punctuation."""
    normalized_lines = []
    seen = set()

    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip(" -•\t")
        line = re.sub(r"^[\u2022*\-]+\s*", "", line).strip()
        if not line:
            continue

        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized_lines.append(line)

    return normalized_lines


def detect_resume_sections(lines: list) -> dict:
    """Group lines under known resume section headings."""
    sections = {section_name: [] for section_name in SECTION_HEADERS}
    active_section = ""

    for line in lines:
        header = _header_for(line)
        if header:
            active_section = header
            remainder = _after_colon(line)
            if remainder:
                sections[active_section].append(remainder)
            continue

        if active_section:
            sections[active_section].append(line)

    return sections


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


def extract_education(text: str, lines: list, sections: dict | None = None) -> list:
    section_lines = (sections or {}).get("education") or _section_items(lines, "education")
    education_items = _education_items_from_section(section_lines)

    if not education_items:
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


def extract_skills(text: str, sections: dict | None = None) -> list:
    lowered_text = text.lower()
    found_skills = []

    for display_name, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            if _skill_alias_found(lowered_text, alias):
                found_skills.append(display_name)
                break

    skill_lines = (sections or {}).get("skills") or _section_items(normalize_resume_lines(text), "skills")
    for line in skill_lines:
        for part in re.split(r"[,|;/]", line):
            candidate = part.strip()
            display = _skill_display_name(candidate)
            if display:
                found_skills.append(display)

    return _unique_preserve_order(found_skills)


def extract_projects(text: str, lines: list, sections: dict | None = None, skills: list | None = None) -> list:
    skills = skills or extract_skills(text, sections)
    project_lines = (sections or {}).get("projects") or _section_items(lines, "projects")
    projects = _projects_from_section(project_lines, skills)

    if not projects:
        projects = _projects_from_phrases(text, skills)

    opening_lines = _opening_project_block(lines)
    if opening_lines and projects:
        _attach_opening_block_to_project(projects, opening_lines, skills)

    return _unique_projects(projects)


def extract_experience(text: str, lines: list, sections: dict | None = None) -> list:
    experience_items = (sections or {}).get("experience") or _section_items(lines, "experience")
    if not experience_items:
        return []

    patterns = (
        r"experience\s+includes\s+([^.\n]+)",
        r"\b([A-Z][A-Za-z ]+\s+Intern\s+at\s+[^.\n]+)",
        r"\bInternship\s+at\s+([^.\n]+)",
        r"\bWorked\s+as\s+([^.\n]+)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            experience_items.append(match.group(1).strip())

    for line in experience_items:
        if re.search(r"\b(intern|internship|worked as|work experience)\b", line, re.IGNORECASE) and not re.search(
            r"experience\s+includes|internship\s+at|worked\s+as",
            line,
            re.IGNORECASE,
        ):
            experience_items.append(line)

    return _dedupe_contained_items(_unique_preserve_order(_clean_items(experience_items)))


def extract_certifications(text: str, lines: list, sections: dict | None = None) -> list:
    certification_items = (sections or {}).get("certifications") or _section_items(lines, "certifications")

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


def _education_items_from_section(section_lines: list) -> list:
    education_items = []
    current_item = []

    for line in section_lines:
        if _is_section_header(line) or _is_date_line(line):
            continue

        if _is_primary_education_line(line):
            if current_item:
                education_items.append(" ".join(current_item))
            current_item = [line]
            continue

        if current_item and _is_education_detail_line(line):
            current_item.append(line)
            continue

        if current_item:
            education_items.append(" ".join(current_item))
            current_item = []

    if current_item:
        education_items.append(" ".join(current_item))

    return education_items


def _is_primary_education_line(line: str) -> bool:
    lowered = line.lower()
    return any(
        keyword in lowered
        for keyword in (
            "b.tech",
            "btech",
            "bachelor",
            "diploma",
            "class x",
            "class 10",
            "cbse",
            "computer science",
        )
    )


def _is_education_detail_line(line: str) -> bool:
    lowered = line.lower()
    return any(
        keyword in lowered
        for keyword in (
            "artificial intelligence",
            "data science",
            "chandigarh group",
            "cgc",
            "landran",
            "ikgptu",
            "psbte",
            "currently pursuing",
            "engineering",
            "semester",
            "year",
        )
    )


def _projects_from_section(project_lines: list, skills: list) -> list:
    projects = []
    title_indexes = []

    for index, line in enumerate(project_lines):
        if _is_project_title_line(line):
            title_indexes.append(index)
            projects.append({"name": line.strip(" -•\t."), "description": "", "technologies": []})

    if not projects:
        return []

    project_descriptions = {project["name"]: [] for project in projects}
    current_title = ""

    for index, line in enumerate(project_lines):
        if index in title_indexes:
            current_title = project_lines[index].strip(" -•\t.")
            continue
        if _should_skip_project_line(line):
            continue

        best_project = _best_project_for_description(line, projects)
        if best_project:
            project_descriptions[best_project["name"]].append(line)
        elif current_title:
            project_descriptions[current_title].append(line)

    for project in projects:
        description = " ".join(project_descriptions.get(project["name"], []))
        project["description"] = description or project["name"]
        project["technologies"] = _project_technologies(project["name"], project["description"], skills)

    return projects


def _projects_from_phrases(text: str, skills: list) -> list:
    project_chunks = []
    phrase_patterns = (
        r"projects?\s+include\s+([^.\n]+)",
        r"project\s*:\s*([^.\n]+)",
        r"another\s+project\s+is\s+([^.\n]+)",
    )
    for pattern in phrase_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            project_chunks.extend(_split_project_chunk(match.group(1)))

    projects = []
    for chunk in _clean_items(project_chunks):
        name = _extract_project_name(chunk)
        if not name or _should_skip_project_line(name):
            continue
        projects.append(
            {
                "name": name,
                "description": chunk,
                "technologies": _project_technologies(name, chunk, skills),
            }
        )

    return projects


def _is_project_title_line(line: str) -> bool:
    raw_cleaned = re.sub(r"\s+", " ", line).strip(" -•\t")
    cleaned = raw_cleaned.strip(".")
    lowered = cleaned.lower()

    if _should_skip_project_line(cleaned):
        return False
    if raw_cleaned.endswith(".") or len(cleaned) > 90:
        return False
    if lowered.split(" ", 1)[0] in DESCRIPTION_ACTION_VERBS:
        return False
    if _contains_any(cleaned, EDUCATION_KEYWORDS):
        return False

    words = cleaned.split()
    if not 2 <= len(words) <= 9:
        return False

    has_project_keyword = any(keyword in lowered for keyword in PROJECT_TITLE_KEYWORDS)
    title_like_words = sum(1 for word in words if word[:1].isupper() or word.lower() in {"using", "and", "of"})
    return has_project_keyword or title_like_words >= max(2, len(words) - 1)


def _should_skip_project_line(line: str) -> bool:
    lowered = line.lower().strip(" :-")
    if not lowered:
        return True
    if _is_section_header(line) or _is_date_line(line):
        return True
    if any(lowered == prefix or lowered.startswith(prefix + ":") for prefix in SKILL_CATEGORY_PREFIXES):
        return True
    if any(phrase in lowered for phrase in SUMMARY_PHRASES):
        return True
    if "@" in lowered or "linkedin.com" in lowered or "github.com" in lowered:
        return True
    if re.fullmatch(r"\d+", lowered):
        return True
    return False


def _opening_project_block(lines: list) -> list:
    opening_lines = []

    for line in lines[:12]:
        if _looks_like_person_name(line) or _is_section_header(line):
            break
        if _should_skip_project_line(line):
            continue
        opening_lines.append(line)

    opening_text = " ".join(opening_lines).lower()
    project_signals = (
        "phishing",
        "detection",
        "model",
        "dashboard",
        "next.js",
        "react",
        "tailwind",
        "vercel",
        "huggingface",
        "hugging face",
        "deployed",
    )
    if len(opening_lines) >= 2 and any(signal in opening_text for signal in project_signals):
        return opening_lines
    return []


def _attach_opening_block_to_project(projects: list, opening_lines: list, skills: list) -> None:
    opening_text = " ".join(opening_lines)
    best_project = _best_project_for_description(opening_text, projects)
    if not best_project:
        return

    existing_description = best_project.get("description", "")
    if opening_text.lower() not in existing_description.lower():
        best_project["description"] = f"{opening_text} {existing_description}".strip()
    best_project["technologies"] = _project_technologies(
        best_project["name"],
        best_project["description"],
        skills,
    )


def _best_project_for_description(description: str, projects: list) -> dict:
    description_tokens = _meaningful_tokens(description)
    lowered = description.lower()
    best_project = {}
    best_score = 0

    project_keyword_groups = {
        "phishing": ("phishing", "url", "email", "dashboard", "next.js", "react", "tailwind", "vercel", "hugging"),
        "demand": ("demand", "forecast", "time-series", "time series", "mape", "planning"),
        "youtube": ("youtube", "video", "views", "engagement", "metadata", "regression"),
        "sentiment": ("sentiment", "nlp", "text", "tokenization", "neural", "positive", "negative", "neutral"),
    }

    for project in projects:
        name = project["name"]
        name_tokens = _meaningful_tokens(name)
        score = len(description_tokens & name_tokens)
        for title_signal, keywords in project_keyword_groups.items():
            if title_signal in name.lower() and any(keyword in lowered for keyword in keywords):
                score += 4
        if score > best_score:
            best_score = score
            best_project = project

    return best_project if best_score > 0 else {}


def _meaningful_tokens(value: str) -> set:
    stop_words = {"using", "with", "and", "the", "for", "model", "system", "analysis"}
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2 and token not in stop_words
    }


def _project_technologies(name: str, description: str, skills: list) -> list:
    project_text = f"{name} {description}"
    technologies = _skills_in_text(project_text, skills)
    lowered = project_text.lower()

    if "python" in {skill.lower() for skill in skills} and any(
        keyword in lowered for keyword in ("machine learning", "time-series", "time series", "nlp", "data", "model")
    ):
        technologies.append("Python")

    return _unique_preserve_order(technologies)


def _is_date_line(line: str) -> bool:
    return bool(
        re.search(
            r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec)[a-z]*\s+\d{4}\s*[-–]\s*(?:present|(?:jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec)[a-z]*\s+\d{4})\b",
            line,
            flags=re.IGNORECASE,
        )
    )


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
    if _contains_any(value, EDUCATION_KEYWORDS):
        return False
    skill_names = {skill.lower() for skill in SKILL_ALIASES if len(skill) > 3}
    if lowered in skill_names:
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
        "technical skills",
        "summary of qualifications",
        "relevant project experience",
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
    matched_skills = []
    for skill in skills:
        aliases = SKILL_ALIASES.get(skill, (skill.lower(),))
        if any(_skill_alias_found(lowered, alias) for alias in aliases):
            matched_skills.append(skill)
    return _unique_preserve_order(matched_skills)


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
