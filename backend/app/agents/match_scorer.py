import re


REQUIRED_SKILL_POINTS = 45
PREFERRED_SKILL_POINTS = 15
PROJECT_RELEVANCE_POINTS = 20
EDUCATION_RELEVANCE_POINTS = 10
EXPERIENCE_CERTIFICATION_POINTS = 10

CANONICAL_SKILLS = {
    "Artificial Intelligence": {"ai", "artificial intelligence"},
    "Machine Learning": {"ml", "machine learning", "ai/ml", "ai ml"},
    "Deep Learning": {"dl", "deep learning"},
    "NLP": {"nlp", "natural language processing", "natural language processing nlp"},
    "React": {"react", "react.js", "reactjs"},
    "Next.js": {"next", "next.js", "nextjs", "next js"},
    "JavaScript": {"javascript", "js"},
    "TypeScript": {"typescript", "ts"},
    "REST API": {"rest api", "rest apis", "restful api", "rest"},
    "API": {"api", "apis", "backend api"},
    "FastAPI": {"fastapi", "fast api"},
    "SQL": {"sql"},
    "Docker": {"docker"},
    "Git": {"git"},
    "GitHub": {"github", "git hub"},
    "Scikit-learn": {"scikit-learn", "scikit learn", "sklearn"},
    "TensorFlow": {"tensorflow", "tensor flow"},
    "Keras": {"keras"},
    "Tailwind CSS": {"tailwind", "tailwind css"},
    "HTML": {"html"},
    "CSS": {"css"},
    "EDA": {"eda", "exploratory data analysis", "exploratory data analysis eda"},
    "Feature Engineering": {"feature engineering"},
    "Data Preprocessing": {"data preprocessing", "preprocessing"},
    "Data Science": {"data science"},
    "Data Structures": {"data structures", "dsa"},
    "Neural Networks": {"neural networks", "neural network"},
    "Problem Solving": {"problem solving", "analytical thinking"},
    "Communication": {"communication", "communication skills"},
    "LangChain": {"langchain", "lang chain"},
    "LangGraph": {"langgraph", "lang graph"},
    "CrewAI": {"crewai", "crew ai"},
    "RAG": {"rag", "retrieval augmented generation"},
    "Node.js": {"node.js", "nodejs", "node js"},
    "Express.js": {"express.js", "expressjs", "express"},
    "WebSockets": {"websockets", "web sockets", "websocket"},
    "Software Architecture": {"software architecture", "software design", "architecture patterns"},
    "Debugging": {"debugging"},
    "Django": {"django"},
    "Flask": {"flask"},
    "PostgreSQL": {"postgresql", "postgres"},
    "SQLite": {"sqlite", "sqlite3"},
    "Pandas": {"pandas"},
    "NumPy": {"numpy", "num py"},
    "Frontend Development": {"frontend development", "frontend", "front-end"},
    "Backend Development": {"backend development", "backend", "back-end"},
}

FRONTEND_RELEVANT_SKILLS = {"React", "Next.js", "JavaScript", "TypeScript", "HTML", "CSS", "Tailwind CSS"}
BACKEND_RELEVANT_SKILLS = {"FastAPI", "Django", "Flask", "Node.js", "REST API", "API"}
PROJECT_RELEVANCE_TERMS = {
    "ai",
    "ml",
    "machine learning",
    "backend",
    "frontend",
    "api",
    "apis",
    "dashboard",
    "data",
    "model",
    "nlp",
    "rag",
    "agent",
    "agents",
    "deployment",
    "deployed",
}


def calculate_match_score(resume_profile: dict, job_profile: dict) -> dict:
    """Compare parsed resume and job profiles and return a deterministic fit score."""
    candidate_skills = normalize_list(resume_profile.get("skills", []))
    required_skills = normalize_list(job_profile.get("required_skills", []))
    preferred_skills = normalize_list(job_profile.get("preferred_skills", []))

    required_score, required_details = calculate_required_skill_score(candidate_skills, required_skills)
    preferred_score, preferred_details = calculate_preferred_skill_score(candidate_skills, preferred_skills)
    project_score, project_notes = calculate_project_relevance_score(
        resume_profile.get("projects", []),
        job_profile,
    )
    education_score, education_note = calculate_education_score(
        resume_profile.get("education", []),
        job_profile,
    )
    experience_score, experience_note = calculate_experience_score(
        resume_profile.get("experience", []),
        resume_profile.get("certifications", []),
        job_profile,
    )

    match_score = min(
        100,
        round(required_score + preferred_score + project_score + education_score + experience_score),
    )

    matched_required = required_details["matched_skills"]
    missing_required = required_details["missing_skills"]
    matched_preferred = preferred_details["matched_skills"]
    missing_preferred = preferred_details["missing_skills"]
    matched_skills = deduplicate_preserve_order(matched_required + matched_preferred)
    missing_skills = deduplicate_preserve_order(missing_required + missing_preferred)

    return {
        "match_score": match_score,
        "match_level": determine_match_level(match_score),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "project_relevance_notes": project_notes,
        "recommendation": build_recommendation(
            match_score,
            missing_required,
            missing_preferred,
            project_notes,
        ),
        "score_breakdown": {
            "required_skills": round(required_score),
            "preferred_skills": round(preferred_score),
            "project_relevance": round(project_score),
            "education_relevance": round(education_score),
            "experience_certifications": round(experience_score),
            "education_note": education_note,
            "experience_note": experience_note,
        },
        "required_skill_match_percentage": required_details["match_percentage"],
        "preferred_skill_match_percentage": preferred_details["match_percentage"],
        "matched_required_skills": matched_required,
        "missing_required_skills": missing_required,
        "matched_preferred_skills": matched_preferred,
        "missing_preferred_skills": missing_preferred,
    }


def normalize_skill(skill: str) -> str:
    value = _comparison_key(skill)
    if not value:
        return ""

    for canonical, aliases in CANONICAL_SKILLS.items():
        canonical_key = _comparison_key(canonical)
        alias_keys = {_comparison_key(alias) for alias in aliases}
        if value == canonical_key or value in alias_keys:
            return canonical

    return _fallback_display_skill(value)


def normalize_list(items: list) -> list:
    if not items:
        return []

    normalized_items = []
    for item in items:
        if isinstance(item, dict):
            values = [
                item.get("name", ""),
                item.get("description", ""),
                " ".join(str(tech) for tech in item.get("technologies", []) if tech),
            ]
            normalized_items.append(normalize_skill(" ".join(values)))
        elif str(item).strip():
            normalized_items.append(normalize_skill(str(item)))

    return deduplicate_preserve_order(normalized_items)


def deduplicate_preserve_order(items: list) -> list:
    seen = set()
    unique_items = []

    for item in items:
        value = str(item).strip()
        if not value:
            continue
        key = value.lower()
        if key not in seen:
            seen.add(key)
            unique_items.append(value)

    return unique_items


def skills_match(candidate_skill: str, required_skill: str) -> bool:
    candidate = normalize_skill(candidate_skill)
    target = normalize_skill(required_skill)

    if not candidate or not target:
        return False
    if candidate == target:
        return True

    if target == "Frontend Development" and candidate in FRONTEND_RELEVANT_SKILLS:
        return True
    if candidate == "Frontend Development" and target in FRONTEND_RELEVANT_SKILLS:
        return True
    if target == "Backend Development" and candidate in BACKEND_RELEVANT_SKILLS:
        return True
    if candidate == "Backend Development" and target in BACKEND_RELEVANT_SKILLS:
        return True

    return False


def calculate_skill_matches(candidate_skills: list, target_skills: list) -> dict:
    normalized_candidate_skills = normalize_list(candidate_skills)
    normalized_target_skills = normalize_list(target_skills)
    matched_skills = []
    missing_skills = []

    for target_skill in normalized_target_skills:
        if any(skills_match(candidate_skill, target_skill) for candidate_skill in normalized_candidate_skills):
            matched_skills.append(_display_skill(target_skill))
        else:
            missing_skills.append(_display_skill(target_skill))

    match_percentage = (
        round((len(matched_skills) / len(normalized_target_skills)) * 100)
        if normalized_target_skills
        else 100
    )

    return {
        "matched_skills": deduplicate_preserve_order(matched_skills),
        "missing_skills": deduplicate_preserve_order(missing_skills),
        "match_percentage": match_percentage,
    }


def calculate_required_skill_score(candidate_skills: list, required_skills: list) -> tuple:
    matches = calculate_skill_matches(candidate_skills, required_skills)
    if not required_skills:
        matches["match_percentage"] = 100
        return 25, matches

    score = (matches["match_percentage"] / 100) * REQUIRED_SKILL_POINTS
    return score, matches


def calculate_preferred_skill_score(candidate_skills: list, preferred_skills: list) -> tuple:
    matches = calculate_skill_matches(candidate_skills, preferred_skills)
    if not preferred_skills:
        matches["match_percentage"] = 100
        return PREFERRED_SKILL_POINTS, matches

    score = (matches["match_percentage"] / 100) * PREFERRED_SKILL_POINTS
    return score, matches


def calculate_project_relevance_score(projects: list, job_profile: dict) -> tuple:
    if not projects:
        return 0, ["No resume projects were found to compare against the job description."]

    required_skills = normalize_list(job_profile.get("required_skills", []))
    preferred_skills = normalize_list(job_profile.get("preferred_skills", []))
    job_context = _job_context_text(job_profile)
    notes = []
    total_project_points = 0

    for project in projects:
        project_text = _project_to_display_text(project)
        normalized_project_text = _normalize_search_text(project_text)
        project_score = 0
        reasons = []

        matched_required = [
            _display_skill(skill)
            for skill in required_skills
            if _text_has_skill(normalized_project_text, skill)
        ]
        matched_preferred = [
            _display_skill(skill)
            for skill in preferred_skills
            if _text_has_skill(normalized_project_text, skill)
        ]
        related_evidence = _related_project_evidence(normalized_project_text, required_skills + preferred_skills)
        relevance_terms = [
            term
            for term in PROJECT_RELEVANCE_TERMS
            if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized_project_text)
        ]

        if matched_required:
            project_score += 12
            reasons.append(f"uses required skills: {', '.join(matched_required[:4])}")
        if matched_preferred:
            project_score += 4
            reasons.append(f"uses preferred skills: {', '.join(matched_preferred[:4])}")
        if related_evidence:
            project_score += 3
            reasons.extend(related_evidence[:2])
        if relevance_terms:
            project_score += 4
            reasons.append(f"shows relevant domain signals: {', '.join(_display_skill(term) for term in relevance_terms[:4])}")
        if job_context and any(term in normalized_project_text for term in _important_words(job_context)):
            project_score += 2
            reasons.append("overlaps with role or responsibility keywords")

        if reasons:
            total_project_points += min(20, project_score)
            notes.append(f"Project '{_project_name(project)}' is relevant because it {', '.join(reasons)}.")

    if not notes:
        return 5, ["Projects are listed, but no clear overlap with job skills, role, or responsibilities was found."]

    average_score = round(total_project_points / len(projects))
    return min(PROJECT_RELEVANCE_POINTS, max(5, average_score)), notes[:5]


def calculate_education_score(education: list, job_profile: dict) -> tuple:
    if not education:
        return 0, "No education details found."

    education_text = _normalize_search_text(" ".join(str(item) for item in education))
    job_text = _normalize_search_text(
        " ".join(
            [
                job_profile.get("role_title", ""),
                " ".join(job_profile.get("eligibility", [])),
                " ".join(job_profile.get("keywords", [])),
            ]
        )
    )
    score = 0
    matched_reasons = []

    education_terms = {
        "b.tech": 3,
        "btech": 3,
        "bachelor": 3,
        "computer science": 3,
        "engineering": 3,
        "artificial intelligence": 3,
        "data science": 3,
        "machine learning": 3,
        "ai": 2,
        "3rd year": 1,
        "third year": 1,
        "6th semester": 1,
        "sixth semester": 1,
    }

    for term, points in education_terms.items():
        if term in education_text:
            score += points
            matched_reasons.append(_display_skill(term))

    if job_text and any(term in education_text for term in _important_words(job_text)):
        score += 2
        matched_reasons.append("job eligibility overlap")

    if matched_reasons:
        return min(EDUCATION_RELEVANCE_POINTS, score), f"Education is relevant: {', '.join(deduplicate_preserve_order(matched_reasons)[:5])}."
    return 3, "Education is present, but direct role relevance is limited."


def calculate_experience_score(experience: list, certifications: list, job_profile: dict) -> tuple:
    if not experience and not certifications:
        return 0, "No experience or certifications found."

    combined_text = _normalize_search_text(
        " ".join(str(item) for item in experience + certifications)
    )
    job_text = _job_context_text(job_profile)
    score = 0
    reasons = []

    if experience:
        score += 3
        reasons.append("experience listed")
    if re.search(r"\b(intern|internship)\b", combined_text):
        score += 2
        reasons.append("internship experience")
    if re.search(r"\b(ai|ml|machine learning|data science|nlp|rag|agent)\b", combined_text):
        score += 2
        reasons.append("AI/ML or data exposure")
    if re.search(r"\b(software|developer|development|backend|frontend|api|fastapi|django|flask)\b", combined_text):
        score += 2
        reasons.append("software/development exposure")
    if certifications:
        score += 2
        reasons.append("certifications listed")
    if job_text and any(term in combined_text for term in _important_words(job_text)):
        score += 1
        reasons.append("overlaps with job keywords")

    return min(EXPERIENCE_CERTIFICATION_POINTS, score), f"Experience/certification relevance: {', '.join(deduplicate_preserve_order(reasons))}."


def determine_match_level(score: int) -> str:
    if score >= 85:
        return "Excellent Fit"
    if score >= 70:
        return "Strong Fit"
    if score >= 50:
        return "Good Fit"
    if score >= 30:
        return "Partial Fit"
    return "Weak Fit"


def build_recommendation(score: int, missing_required: list, missing_preferred: list, project_notes: list) -> str:
    if score >= 85:
        return "Apply confidently. The resume strongly matches the required skills and supporting evidence for this internship."
    if score >= 70:
        if missing_required:
            return f"Good match; strengthen minor required gaps before applying: {', '.join(missing_required[:3])}."
        if missing_preferred:
            return f"Good match; add evidence for preferred skills if possible: {', '.join(missing_preferred[:3])}."
        return "Good match; polish project outcomes and apply."
    if score >= 50:
        gaps = missing_required or missing_preferred
        if gaps:
            return f"Apply, but improve the resume around these gaps: {', '.join(gaps[:4])}."
        return "Apply, but make projects and experience more specific to the role."
    if score >= 30:
        gaps = missing_required or missing_preferred
        if gaps:
            return f"Build one relevant project before applying and cover these skills: {', '.join(gaps[:4])}."
        return "Build one relevant project before applying and add clearer role-specific evidence."
    if missing_required:
        return f"Focus on required skills first: {', '.join(missing_required[:5])}."
    return "Focus on core role skills and add relevant projects before applying."


def _skill_variants(skill: str) -> set:
    normalized = normalize_skill(skill)
    variants = {_comparison_key(normalized)}
    aliases = CANONICAL_SKILLS.get(normalized, set())
    variants.update(_comparison_key(alias) for alias in aliases)
    return {variant for variant in variants if variant}


def _text_has_skill(text: str, skill: str) -> bool:
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(variant)}(?![a-z0-9])", text)
        for variant in _skill_variants(skill)
    )


def _job_context_text(job_profile: dict) -> str:
    values = [
        job_profile.get("role_title", ""),
        " ".join(job_profile.get("required_skills", [])),
        " ".join(job_profile.get("preferred_skills", [])),
        " ".join(job_profile.get("responsibilities", [])),
        " ".join(job_profile.get("keywords", [])),
    ]
    return _normalize_search_text(" ".join(values))


def _project_to_display_text(project) -> str:
    if isinstance(project, dict):
        parts = [
            str(project.get("name", "")).strip(),
            str(project.get("description", "")).strip(),
            " ".join(str(item) for item in project.get("technologies", []) if item),
        ]
        return " ".join(part for part in parts if part)
    return str(project)


def _project_name(project) -> str:
    if isinstance(project, dict) and project.get("name"):
        return str(project["name"])
    text = str(project).strip()
    return text[:80] if text else "Unnamed project"


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
        "skills",
        "required",
        "preferred",
    }
    words = re.findall(r"[a-z][a-z0-9.+#-]*", _normalize_search_text(value))
    return [word for word in words if len(word) > 2 and word not in stop_words]


def _display_skill(skill: str) -> str:
    return normalize_skill(skill)


def _comparison_key(value: str) -> str:
    text = re.sub(r"\([^)]*\)", " ", str(value or "").lower())
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    compact = text.replace(" ", "")

    compact_mappings = {
        "reactjs": "react",
        "nextjs": "next",
        "nodejs": "node",
        "expressjs": "express",
        "websockets": "websockets",
        "fastapi": "fastapi",
        "restapis": "rest apis",
        "restfulapi": "restful api",
        "scikitlearn": "scikit learn",
        "tensorflow": "tensorflow",
        "tailwindcss": "tailwind css",
    }
    return compact_mappings.get(compact, text)


def _normalize_search_text(value: str) -> str:
    text = str(value or "").lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _fallback_display_skill(value: str) -> str:
    special_cases = {
        "b.tech": "B.Tech",
        "btech": "B.Tech",
        "3rd year": "3rd Year",
        "third year": "3rd Year",
        "6th semester": "6th Semester",
        "sixth semester": "6th Semester",
    }
    if value in special_cases:
        return special_cases[value]
    return " ".join(word.upper() if word in {"ai", "ml", "nlp", "api", "sql", "css", "html"} else word.capitalize() for word in value.split())


def _related_project_evidence(project_text: str, target_skills: list) -> list:
    notes = []
    targets = {normalize_skill(skill) for skill in target_skills}

    if "REST API" in targets and _text_has_skill(project_text, "FastAPI"):
        notes.append("shows related backend API evidence through FastAPI")
    if "API" in targets and any(_text_has_skill(project_text, skill) for skill in ("FastAPI", "REST API")):
        notes.append("shows related API evidence")
    if "JavaScript" in targets and _text_has_skill(project_text, "TypeScript"):
        notes.append("shows related frontend language evidence through TypeScript")
    if "GitHub" in targets and _text_has_skill(project_text, "Git"):
        notes.append("shows related version-control evidence through Git")

    return deduplicate_preserve_order(notes)
