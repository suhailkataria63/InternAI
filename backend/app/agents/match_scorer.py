import re


REQUIRED_SKILL_POINTS = 50
PREFERRED_SKILL_POINTS = 15
PROJECT_RELEVANCE_POINTS = 20
EDUCATION_ROLE_POINTS = 10
EXPERIENCE_CERTIFICATION_POINTS = 5


def calculate_match_score(resume_profile: dict, job_profile: dict) -> dict:
    """Compare parsed resume and job profiles and return a deterministic fit score."""
    resume_skills = _normalize_list(resume_profile.get("skills", []))
    required_skills = _normalize_list(job_profile.get("required_skills", []))
    preferred_skills = _normalize_list(job_profile.get("preferred_skills", []))

    matched_required = _matched_items(required_skills, resume_skills)
    matched_preferred = _matched_items(preferred_skills, resume_skills)
    missing_required = _missing_items(required_skills, resume_skills)

    required_score = _weighted_ratio_score(
        matched_count=len(matched_required),
        total_count=len(required_skills),
        max_points=REQUIRED_SKILL_POINTS,
    )
    preferred_score = _weighted_ratio_score(
        matched_count=len(matched_preferred),
        total_count=len(preferred_skills),
        max_points=PREFERRED_SKILL_POINTS,
    )
    project_score, project_notes = _score_project_relevance(resume_profile, job_profile)
    education_score = _score_education_role_relevance(resume_profile, job_profile)
    experience_score = _score_experience_and_certifications(resume_profile, job_profile)

    match_score = min(
        100,
        required_score
        + preferred_score
        + project_score
        + education_score
        + experience_score,
    )

    matched_skills = _unique_preserve_order(matched_required + matched_preferred)

    return {
        "match_score": match_score,
        "match_level": _get_match_level(match_score),
        "matched_skills": matched_skills,
        "missing_skills": missing_required,
        "project_relevance_notes": project_notes,
        "recommendation": _build_recommendation(match_score, missing_required, project_notes),
    }


def _weighted_ratio_score(matched_count: int, total_count: int, max_points: int) -> int:
    if total_count == 0:
        return max_points
    return round((matched_count / total_count) * max_points)


def _score_project_relevance(resume_profile: dict, job_profile: dict) -> tuple[int, list[str]]:
    projects = resume_profile.get("projects", [])
    if not projects:
        return 0, ["No resume projects were found to compare against the job description."]

    job_terms = _job_relevance_terms(job_profile)
    if not job_terms:
        return 10, ["Projects are present, but the job profile has limited keywords for comparison."]

    notes: list[str] = []
    relevant_project_count = 0

    for project in projects:
        project_display = _project_to_display_text(project)
        project_text = _normalize_text(project_display)
        matched_terms = [term for term in job_terms if term in project_text]
        if matched_terms:
            relevant_project_count += 1
            notes.append(
                f"Project '{project_display}' matches job terms: {', '.join(_display_terms(matched_terms))}."
            )

    if relevant_project_count == 0:
        return 5, ["Projects are listed, but no clear overlap with job skills or keywords was found."]

    score = round((relevant_project_count / len(projects)) * PROJECT_RELEVANCE_POINTS)
    return score, notes


def _score_education_role_relevance(resume_profile: dict, job_profile: dict) -> int:
    education_text = _normalize_text(" ".join(resume_profile.get("education", [])))
    role_text = _normalize_text(job_profile.get("role_title", ""))
    eligibility_text = _normalize_text(" ".join(job_profile.get("eligibility", [])))

    if not education_text:
        return 0

    relevance_terms = {
        "computer",
        "science",
        "engineering",
        "software",
        "data",
        "analytics",
        "business",
        "design",
        "marketing",
        "finance",
        "management",
    }
    role_terms = _tokenize(role_text + " " + eligibility_text)
    education_terms = _tokenize(education_text)

    if education_terms & role_terms:
        return EDUCATION_ROLE_POINTS
    if education_terms & relevance_terms:
        return round(EDUCATION_ROLE_POINTS * 0.7)
    return round(EDUCATION_ROLE_POINTS * 0.4)


def _score_experience_and_certifications(resume_profile: dict, job_profile: dict) -> int:
    experience = resume_profile.get("experience", [])
    certifications = resume_profile.get("certifications", [])

    if not experience and not certifications:
        return 0

    job_terms = _job_relevance_terms(job_profile)
    combined_text = _normalize_text(" ".join(experience + certifications))

    if any(term in combined_text for term in job_terms):
        return EXPERIENCE_CERTIFICATION_POINTS
    return round(EXPERIENCE_CERTIFICATION_POINTS * 0.6)


def _job_relevance_terms(job_profile: dict) -> list[str]:
    terms: list[str] = []
    terms.extend(job_profile.get("required_skills", []))
    terms.extend(job_profile.get("preferred_skills", []))
    terms.extend(job_profile.get("keywords", []))
    terms.extend(_important_words(job_profile.get("role_title", "")))
    for responsibility in job_profile.get("responsibilities", []):
        terms.extend(_important_words(responsibility))

    return _unique_preserve_order([_normalize_text(term) for term in terms if term])


def _matched_items(job_items: list[str], resume_items: list[str]) -> list[str]:
    matches: list[str] = []
    for job_item in job_items:
        if any(_items_match(job_item, resume_item) for resume_item in resume_items):
            matches.append(_display_value(job_item))
    return _unique_preserve_order(matches)


def _missing_items(job_items: list[str], resume_items: list[str]) -> list[str]:
    missing: list[str] = []
    for job_item in job_items:
        if not any(_items_match(job_item, resume_item) for resume_item in resume_items):
            missing.append(_display_value(job_item))
    return _unique_preserve_order(missing)


def _items_match(job_item: str, resume_item: str) -> bool:
    normalized_job = _normalize_text(job_item)
    normalized_resume = _normalize_text(resume_item)
    return normalized_job == normalized_resume or normalized_job in normalized_resume


def _get_match_level(score: int) -> str:
    if score >= 75:
        return "Strong Fit"
    if score >= 60:
        return "Good Fit"
    if score >= 40:
        return "Partial Fit"
    return "Needs Improvement"


def _build_recommendation(
    match_score: int,
    missing_skills: list[str],
    project_notes: list[str],
) -> str:
    if match_score >= 80 and not missing_skills:
        return "Strong match. This internship is a good target based on the current resume profile."

    if missing_skills:
        skills = ", ".join(missing_skills[:5])
        return f"Improve the match by adding evidence for these required skills: {skills}."

    if project_notes:
        return "Improve the match by making project descriptions more specific to the job responsibilities."

    return "Add more skills, projects, experience, or certifications before applying."


def _normalize_list(items: list) -> list[str]:
    normalized_items = [_normalize_text(str(item)) for item in items if str(item).strip()]
    return _unique_preserve_order(normalized_items)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _project_to_display_text(project) -> str:
    if isinstance(project, dict):
        parts = [
            str(project.get("name", "")).strip(),
            str(project.get("description", "")).strip(),
            ", ".join(str(item) for item in project.get("technologies", []) if item),
        ]
        return " | ".join(part for part in parts if part)
    return str(project)


def _tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#.]+", _normalize_text(value)))


def _important_words(value: str) -> list[str]:
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
        "write",
        "work",
    }
    return [word for word in _tokenize(value) if len(word) > 2 and word not in stop_words]


def _display_terms(terms: list[str]) -> list[str]:
    return [_display_value(term) for term in terms[:5]]


def _display_value(value: str) -> str:
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
    return special_cases.get(value, value.title())


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_items: list[str] = []

    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    return unique_items
