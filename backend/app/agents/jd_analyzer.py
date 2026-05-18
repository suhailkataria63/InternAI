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
- Separate required skills from preferred skills.
- Do not invent facts that are not present in the job description.

Job description:
{jd_text}
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
    "REST API": ("rest api", "restful api", "rest apis", "restful apis"),
    "Tailwind CSS": ("tailwind css", "tailwind"),
    "HTML": ("html",),
    "CSS": ("css",),
    "Problem Solving": ("problem solving", "problem-solving"),
    "Communication": ("communication", "communication skills"),
    "APIs": ("apis", "api integration", "api integrations"),
    "Backend Development": ("backend development", "backend"),
    "Frontend Development": ("frontend development", "frontend", "front-end"),
}

REQUIRED_SECTION_KEYWORDS = [
    "required skills",
    "must have",
    "must-have",
    "mandatory",
    "requirements",
    "skills required",
    "candidate should have",
    "should know",
    "need experience in",
    "strong knowledge of",
]

PREFERRED_SECTION_KEYWORDS = [
    "preferred skills",
    "good to have",
    "nice to have",
    "bonus",
    "plus",
    "preferred qualifications",
    "additional skills",
    "familiarity with",
]

RESPONSIBILITY_KEYWORDS = [
    "responsibilities",
    "responsibilities include",
    "selected intern's day-to-day responsibilities include",
    "day-to-day responsibilities",
    "you will",
    "work on",
    "tasks include",
]

ELIGIBILITY_KEYWORDS = [
    "eligibility",
    "who can apply",
    "students",
    "candidates can apply",
    "b.tech",
    "degree",
    "year",
    "semester",
    "available for",
    "relevant skills",
    "interests",
]

STOP_SECTION_KEYWORDS = [
    "required skills",
    "preferred skills",
    "good to have",
    "nice to have",
    "responsibilities",
    "responsibilities include",
    "roles and responsibilities",
    "selected intern's day-to-day responsibilities include",
    "day-to-day responsibilities",
    "you will",
    "work on",
    "tasks include",
    "eligibility",
    "who can apply",
    "candidates can apply",
    "stipend",
    "duration",
    "location",
    "work mode",
    "about",
    "company",
]


def analyze_jd_text(jd_text: str) -> dict:
    """Analyze an internship or job description and return a structured profile."""
    cleaned_text = clean_text(jd_text)
    lines = split_lines(cleaned_text)

    job_profile = {
        "role_title": extract_role_title(cleaned_text, lines),
        "company_name": extract_company_name(cleaned_text, lines),
        "required_skills": extract_required_skills(cleaned_text, lines),
        "preferred_skills": extract_preferred_skills(cleaned_text, lines),
        "responsibilities": extract_responsibilities(cleaned_text, lines),
        "eligibility": extract_eligibility(cleaned_text, lines),
        "stipend": extract_stipend(cleaned_text),
        "duration": extract_duration(cleaned_text),
        "location": extract_location(cleaned_text),
        "work_mode": extract_work_mode(cleaned_text),
        "keywords": [],
    }

    required_normalized = {_normalize_skill(skill) for skill in job_profile["required_skills"]}
    job_profile["preferred_skills"] = [
        skill
        for skill in job_profile["preferred_skills"]
        if _normalize_skill(skill) not in required_normalized
    ]
    job_profile["keywords"] = extract_keywords(job_profile)

    return job_profile


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_lines(text: str) -> list:
    return [line.strip(" -•\t") for line in text.splitlines() if line.strip(" -•\t")]


def extract_role_title(text: str, lines: list) -> str:
    patterns = (
        r"(?:role|position|title|job title)\s*:\s*([^\n.]+)",
        r"hiring\s+(?:an?|for\s+)?([A-Za-z0-9/ .+-]+?\b(?:intern|developer|engineer|analyst|associate))\b",
        r"\b([A-Za-z0-9/ .+-]+?\b(?:intern|developer|engineer|analyst|associate))\s+for\s+\d+\s*(?:weeks?|months?|years?)\b",
        r"applying\s+for\s+the\s+([A-Za-z0-9/ .+-]+?)\s+role\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            role_title = _clean_role_title(match.group(1), text)
            if role_title:
                return role_title

    for line in lines[:6]:
        if "selected intern" in line.lower():
            continue
        if re.search(r"\b(intern|developer|engineer|analyst|associate)\b", line, re.IGNORECASE):
            role_title = _clean_role_title(line, text)
            if role_title:
                return role_title
    return _fallback_role_title(text)


def extract_company_name(text: str, lines: list) -> str:
    patterns = (
        r"(?:company|organization|employer)\s*:\s*([^\n.]+)",
        r"([A-Z][A-Za-z0-9&.' -]{2,70})\s+is\s+hiring\b",
        r"\bat\s+([A-Z][A-Za-z0-9&.' -]{2,70})(?:\s+is\b|\.|,|\n|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = _clean_inline_value(match.group(1))
            if not _looks_like_role(value):
                return value

    for line in lines[:8]:
        if line.lower().startswith("company:"):
            return _clean_inline_value(line.split(":", 1)[1])
    return ""


def extract_section_text(text: str, section_keywords: list, stop_keywords: list) -> str:
    lines = split_lines(text)
    collected = []
    active = False

    for line in lines:
        lowered = line.lower().rstrip(":")
        starts_section = _matches_section_start(lowered, section_keywords)

        if starts_section:
            active = True
            remainder = _remove_leading_section_phrase(line, section_keywords)
            if remainder:
                collected.append(remainder)
            continue

        if active and _matches_section_start(lowered, stop_keywords):
            break

        if active:
            collected.append(line)

    return "\n".join(collected).strip()


def extract_skills_from_text(text: str) -> list:
    lowered_text = text.lower()
    skills = []

    for display_name, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            if _skill_alias_found(lowered_text, alias):
                skills.append(display_name)
                break

    return deduplicate_preserve_order(skills)


def extract_required_skills(text: str, lines: list) -> list:
    required_text = extract_section_text(text, REQUIRED_SECTION_KEYWORDS, STOP_SECTION_KEYWORDS)
    required_contexts = _extract_inline_contexts(text, REQUIRED_SECTION_KEYWORDS)
    required_skills = extract_skills_from_text("\n".join([required_text] + required_contexts))

    preferred_text = extract_section_text(text, PREFERRED_SECTION_KEYWORDS, STOP_SECTION_KEYWORDS)
    preferred_contexts = _extract_inline_contexts(text, PREFERRED_SECTION_KEYWORDS)
    preferred_skills = extract_skills_from_text("\n".join([preferred_text] + preferred_contexts))

    if not required_skills:
        fallback_skills = extract_skills_from_text(text)
        preferred_normalized = {_normalize_skill(skill) for skill in preferred_skills}
        required_skills = [
            skill for skill in fallback_skills if _normalize_skill(skill) not in preferred_normalized
        ]

    return deduplicate_preserve_order(required_skills)


def extract_preferred_skills(text: str, lines: list) -> list:
    preferred_text = extract_section_text(text, PREFERRED_SECTION_KEYWORDS, STOP_SECTION_KEYWORDS)
    preferred_contexts = _extract_inline_contexts(text, PREFERRED_SECTION_KEYWORDS)
    return extract_skills_from_text("\n".join([preferred_text] + preferred_contexts))


def extract_responsibilities(text: str, lines: list) -> list:
    section_text = extract_section_text(text, RESPONSIBILITY_KEYWORDS, STOP_SECTION_KEYWORDS)
    items = _split_items(section_text)

    patterns = (
        r"responsibilities\s+include\s+([^.\n]+)",
        r"selected intern's day-to-day responsibilities include\s+([^.\n]+)",
        r"day-to-day responsibilities\s+include\s+([^.\n]+)",
        r"you\s+will\s+([^.\n]+)",
        r"work\s+on\s+([^.\n]+)",
        r"tasks\s+include\s+([^.\n]+)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            items.extend(_split_items(match.group(1)))

    return deduplicate_preserve_order(_clean_items(items))[:8]


def extract_eligibility(text: str, lines: list) -> list:
    section_text = extract_section_text(text, ELIGIBILITY_KEYWORDS, STOP_SECTION_KEYWORDS)
    eligibility_items = _split_items(section_text)

    for line in lines:
        if _contains_any(line, ELIGIBILITY_KEYWORDS):
            eligibility_items.append(line)

    patterns = (
        r"candidates\s+can\s+apply\s+who\s+([^\n]+)",
        r"students\s+(?:with|from|who)\s+([^\n]+)",
        r"available\s+for\s+([^\n]+)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            eligibility_items.append(match.group(1).strip())

    return deduplicate_preserve_order(_clean_items(eligibility_items))[:8]


def extract_stipend(text: str) -> str:
    patterns = (
        r"(?:stipend|salary|compensation|pay)\s*:\s*([^\n.]+)",
        r"\b(unpaid)\b",
        r"((?:₹|rs\.?|inr)\s?[\d,]+(?:\s?-\s?(?:₹|rs\.?|inr)?\s?[\d,]+)?(?:\s*(?:per month|/month|monthly|pm))?)",
        r"(\b\d{1,3}(?:,\d{3})+\s*(?:per month|/month|monthly|pm)\b)",
    )
    return _extract_first_match(text, patterns)


def extract_duration(text: str) -> str:
    patterns = (
        r"(?:duration|term)\s*:\s*([^\n.]+)",
        r"(?:internship\s+is\s+for|for)\s+(\d+\s*(?:weeks?|months?|years?))",
        r"\b(\d+\s*(?:weeks?|months?|years?))\b",
    )
    return _extract_first_match(text, patterns)


def extract_location(text: str) -> str:
    patterns = (
        r"(?:location|city)\s*:\s*([^\n.]+)",
        r"(?:based in|located in)\s+([A-Z][A-Za-z, ]{2,60})",
    )
    return _extract_first_match(text, patterns)


def extract_work_mode(text: str) -> str:
    lowered_text = text.lower()
    if "hybrid" in lowered_text:
        return "Hybrid"
    if "work from home" in lowered_text or "wfh" in lowered_text:
        return "Work From Home"
    if "remote" in lowered_text:
        return "Remote"
    if "on-site" in lowered_text or "onsite" in lowered_text or "in office" in lowered_text:
        return "On-site"
    return "Not specified"


def extract_keywords(profile: dict) -> list:
    keywords = []
    keywords.extend(_important_words(profile.get("role_title", "")))
    keywords.extend(profile.get("required_skills", []))
    keywords.extend(profile.get("preferred_skills", []))

    work_mode = profile.get("work_mode", "")
    if work_mode and work_mode != "Not specified":
        keywords.append(work_mode)

    for responsibility in profile.get("responsibilities", []):
        keywords.extend(_important_words(responsibility))

    return deduplicate_preserve_order(_clean_items(keywords))[:30]


def deduplicate_preserve_order(items: list) -> list:
    seen = set()
    unique_items = []

    for item in items:
        if item is None:
            continue
        value = str(item).strip()
        if not value:
            continue
        key = value.lower()
        if key not in seen:
            seen.add(key)
            unique_items.append(value)

    return unique_items


def _extract_inline_contexts(text: str, phrases: list) -> list:
    contexts = []
    joined_phrases = "|".join(re.escape(phrase) for phrase in phrases)
    pattern = rf"(?:{joined_phrases})(?:\s*(?:include|includes|:|are|is|in|of))?\s*([^.\n]+)"

    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        contexts.append(match.group(1).strip())

    return contexts


def _matches_section_start(lowered_line: str, keywords: list) -> bool:
    normalized = lowered_line.strip().rstrip(":")
    return any(
        normalized == keyword
        or normalized.startswith(keyword + ":")
        or normalized.startswith(keyword + " ")
        or normalized.startswith(keyword + " include")
        or normalized.startswith(keyword + " includes")
        for keyword in keywords
    )


def _remove_leading_section_phrase(line: str, keywords: list) -> str:
    for keyword in sorted(keywords, key=len, reverse=True):
        pattern = rf"^{re.escape(keyword)}(?:\s*(?:include|includes|:|are|is|in|of))?\s*"
        cleaned = re.sub(pattern, "", line, flags=re.IGNORECASE).strip(" -•\t:")
        if cleaned != line.strip(" -•\t:"):
            return cleaned
    return ""


def _split_items(text: str) -> list:
    if not text:
        return []

    normalized = re.sub(r"\n+", "\n", text)
    raw_items = []
    for line in normalized.splitlines():
        parts = re.split(r";|\||(?:\s+-\s+)|(?:,\s+(?=[a-zA-Z]{4,}\s))", line)
        raw_items.extend(part.strip(" -•\t") for part in parts)

    return [item for item in raw_items if item]


def _clean_items(items: list) -> list:
    cleaned_items = []
    for item in items:
        value = re.sub(r"\s+", " ", str(item)).strip(" -•\t.")
        if value:
            cleaned_items.append(value)
    return cleaned_items


def _contains_any(value: str, keywords: list) -> bool:
    lowered = value.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _skill_alias_found(lowered_text: str, alias: str) -> bool:
    alias = alias.lower()
    escaped = re.escape(alias)
    if alias in {"c++", "c#", "next.js", "node.js"}:
        return alias in lowered_text
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", lowered_text))


def _normalize_skill(skill: str) -> str:
    return re.sub(r"\s+", " ", skill.lower()).strip()


def _extract_first_match(text: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_inline_value(match.group(1))
    return ""


def _clean_inline_value(value: str) -> str:
    value = re.split(r"\n|;", value, maxsplit=1)[0]
    return value.strip(" -•\t:,.")


def _clean_role_title(value: str, full_text: str) -> str:
    cleaned = _clean_inline_value(value)
    cleaned = re.split(
        r"\b(?:for\s+\d+\s*(?:weeks?|months?|years?)|remote|with|required|preferred|responsibilities)\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    cleaned = re.sub(r"\b(?:the\s+)?internship\b.*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" -•\t:,.")

    invalid_phrases = (
        "deployment experience",
        "the internship",
        "required skills",
        "preferred skills",
        "responsibilities",
        "candidate should",
        "selected intern",
    )
    lowered = cleaned.lower()
    if not cleaned or any(phrase in lowered for phrase in invalid_phrases):
        return _fallback_role_title(full_text)
    if not re.search(r"\b(intern|developer|engineer|analyst|associate)\b", cleaned, re.IGNORECASE):
        return _fallback_role_title(full_text)
    return _title_case_role(cleaned)


def _fallback_role_title(text: str) -> str:
    fallback_patterns = (
        (r"\bAI\s*/?\s*ML\s+Intern\b", "AI/ML Intern"),
        (r"\bData Science Intern\b", "Data Science Intern"),
        (r"\bSoftware Intern\b", "Software Intern"),
    )
    for pattern, title in fallback_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return title
    if re.search(r"\bintern(?:ship)?\b", text, flags=re.IGNORECASE):
        return "Intern"
    return ""


def _title_case_role(value: str) -> str:
    special_terms = {"ai": "AI", "ml": "ML", "api": "API", "apis": "APIs", "nlp": "NLP"}
    words = []
    for word in value.strip().split():
        cleaned = word.strip()
        key = cleaned.lower().strip("/-")
        if "/" in cleaned:
            words.append("/".join(special_terms.get(part.lower(), part.upper() if len(part) <= 2 else part.title()) for part in cleaned.split("/")))
        else:
            words.append(special_terms.get(key, cleaned[:1].upper() + cleaned[1:]))
    return " ".join(words).strip()


def _looks_like_role(value: str) -> bool:
    return bool(re.search(r"\b(intern|internship|developer|engineer|analyst|role|position)\b", value, re.IGNORECASE))


def _important_words(value: str) -> list:
    stop_words = {
        "and",
        "or",
        "the",
        "a",
        "an",
        "to",
        "with",
        "for",
        "of",
        "in",
        "on",
        "using",
        "build",
        "work",
        "will",
        "include",
        "includes",
        "intern",
        "internship",
    }
    words = re.findall(r"[A-Za-z][A-Za-z0-9.+#-]*", value)
    return [
        word.upper() if word.lower() in {"ai", "ml", "nlp", "api"} else word.title()
        for word in words
        if len(word) > 2 and word.lower() not in stop_words
    ]
