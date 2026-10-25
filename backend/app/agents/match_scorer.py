import re
from functools import lru_cache


BASE_WEIGHTS = {
    "required_skills": 35,
    "project_relevance": 25,
    "experience_relevance": 20,
    "education_relevance": 10,
    "preferred_skills": 10,
}

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
    "PyTorch": {"pytorch", "torch"},
    "Tailwind CSS": {"tailwind", "tailwind css"},
    "HTML": {"html"},
    "CSS": {"css"},
    "EDA": {"eda", "exploratory data analysis", "exploratory data analysis eda"},
    "Feature Engineering": {"feature engineering"},
    "Data Preprocessing": {"data preprocessing", "preprocessing"},
    "Data Analysis": {"data analysis", "data analytics"},
    "Data Science": {"data science"},
    "Data Structures": {"data structures", "dsa"},
    "Neural Networks": {"neural networks", "neural network"},
    "Problem Solving": {"problem solving", "analytical thinking"},
    "Communication": {"communication", "communication skills"},
    "LangChain": {"langchain", "lang chain"},
    "LangGraph": {"langgraph", "lang graph"},
    "CrewAI": {"crewai", "crew ai"},
    "RAG": {"rag", "retrieval augmented generation"},
    "AI Agents": {"ai agents", "agentic ai"},
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
RELATED_SKILLS = {
    "REST API": {"FastAPI", "Django", "Flask", "Node.js", "Express.js", "API"},
    "API": {"FastAPI", "Django", "Flask", "Node.js", "Express.js", "REST API"},
    "Backend Development": BACKEND_RELEVANT_SKILLS,
    "Frontend Development": FRONTEND_RELEVANT_SKILLS,
    "JavaScript": {"TypeScript"},
    "TypeScript": {"JavaScript"},
    "GitHub": {"Git"},
    "Machine Learning": {"Scikit-learn", "TensorFlow", "PyTorch", "Keras", "Data Science"},
    "Artificial Intelligence": {"Machine Learning", "NLP", "RAG", "AI Agents"},
    "AI Agents": {"LangGraph", "CrewAI", "LangChain"},
    "RAG": {"LangChain", "NLP"},
}

PROJECT_RELEVANCE_TERMS = {
    "ai", "ml", "machine learning", "backend", "frontend", "api", "apis", "dashboard",
    "data", "model", "nlp", "rag", "agent", "agents", "deployment", "deployed",
    "chatbot", "workflow", "reports", "analysis",
}


def calculate_match_score(resume_profile: dict, job_profile: dict) -> dict:
    """EvidenceMatch: deterministic, explainable resume/JD scoring."""
    requirements = build_jd_requirements(job_profile)
    candidate = build_candidate_evidence(resume_profile)
    active_weights = _active_weights(requirements)

    required = score_skill_requirements(requirements["required_skills"], candidate)
    preferred = score_skill_requirements(requirements["preferred_skills"], candidate)
    projects = score_project_evidence(candidate["projects"], requirements)
    experience = score_experience_evidence(candidate["experience"], requirements)
    education = score_education_evidence(candidate["education_text"], requirements)

    dimension_scores = {
        "required_skills": required["score_ratio"],
        "project_relevance": projects["score_ratio"],
        "experience_relevance": experience["score_ratio"],
        "education_relevance": education["score_ratio"],
        "preferred_skills": preferred["score_ratio"],
    }
    weighted_score = sum(dimension_scores[name] * weight for name, weight in active_weights.items())
    match_score = _apply_mandatory_caps(round(weighted_score), required, education, requirements)
    match_score = _cap_sparse_job_score(match_score, job_profile, requirements)

    matched_required = required["matched"]
    missing_required = required["missing"]
    matched_preferred = preferred["matched"]
    missing_preferred = preferred["missing"]
    matched_skills = deduplicate_preserve_order(matched_required + matched_preferred)
    missing_skills = deduplicate_preserve_order(missing_required + missing_preferred)
    confidence = assessment_confidence(requirements, candidate, required, preferred, projects, experience, education)

    return {
        "match_score": match_score,
        "match_level": determine_match_level(match_score),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "project_relevance_notes": projects["notes"],
        "recommendation": build_recommendation(match_score, missing_required, missing_preferred, projects["notes"]),
        "score_breakdown": {
            "required_skills": round(dimension_scores["required_skills"] * active_weights.get("required_skills", 0)),
            "preferred_skills": round(dimension_scores["preferred_skills"] * active_weights.get("preferred_skills", 0)),
            "project_relevance": round(dimension_scores["project_relevance"] * active_weights.get("project_relevance", 0)),
            "education_relevance": round(dimension_scores["education_relevance"] * active_weights.get("education_relevance", 0)),
            "experience_certifications": round(dimension_scores["experience_relevance"] * active_weights.get("experience_relevance", 0)),
            "evidence_weights": active_weights,
            "education_note": education["note"],
            "experience_note": experience["note"],
        },
        "required_skill_match_percentage": required["match_percentage"],
        "preferred_skill_match_percentage": preferred["match_percentage"],
        "matched_required_skills": matched_required,
        "missing_required_skills": missing_required,
        "matched_preferred_skills": matched_preferred,
        "missing_preferred_skills": missing_preferred,
        "assessment_confidence": confidence,
        "evidence_summary": {
            "required_skills": required["evidence"],
            "preferred_skills": preferred["evidence"],
            "projects": projects["evidence"],
            "experience": experience["evidence"],
            "education": education["evidence"],
        },
        "missing_or_uncertain_requirements": deduplicate_preserve_order(
            required["missing"] + education["missing"] + experience["missing"]
        ),
    }


def build_jd_requirements(job_profile: dict) -> dict:
    required_skills = normalize_list(job_profile.get("required_skills", []))
    preferred_skills = [
        skill for skill in normalize_list(job_profile.get("preferred_skills", []))
        if skill not in required_skills
    ]
    responsibilities = _string_list(job_profile.get("responsibilities", []))
    eligibility = _string_list(job_profile.get("eligibility", []))
    experience_requirements = _string_list(job_profile.get("experience_requirements", [])) or _extract_experience_requirements(responsibilities + eligibility)
    education_requirements = _string_list(job_profile.get("education_requirements", [])) or _extract_education_requirements(eligibility)
    return {
        "role_title": str(job_profile.get("role_title", "") or ""),
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "responsibilities": responsibilities,
        "eligibility": eligibility,
        "experience_requirements": experience_requirements,
        "education_requirements": education_requirements,
        "keywords": _string_list(job_profile.get("keywords", [])),
    }


def build_candidate_evidence(resume_profile: dict) -> dict:
    explicit_skills = normalize_list(resume_profile.get("skills", []))
    projects = [_project_evidence(project) for project in resume_profile.get("projects", []) or []]
    experience = [_experience_evidence(item) for item in resume_profile.get("experience", []) or []]
    certifications = [_normalize_search_text(str(item)) for item in resume_profile.get("certifications", []) or []]
    education_text = _normalize_search_text(" ".join(str(item) for item in resume_profile.get("education", []) or []))
    return {
        "explicit_skills": explicit_skills,
        "projects": [project for project in projects if project["text"]],
        "experience": [item for item in experience if item["text"]] + [{"title": "Certification", "text": item, "skills": _skills_in_text(item)} for item in certifications],
        "education_text": education_text,
    }


def score_skill_requirements(target_skills: list, candidate: dict) -> dict:
    if not target_skills:
        return {"score_ratio": 0, "matched": [], "missing": [], "match_percentage": 100, "evidence": []}

    evidence_items = []
    matched = []
    missing = []
    total_ratio = 0.0
    for skill in target_skills:
        evidence = best_skill_evidence(skill, candidate)
        total_ratio += evidence["score"]
        evidence_items.append(evidence)
        if evidence["status"] in {"direct", "alias"}:
            matched.append(_display_skill(skill))
        elif evidence["status"] == "related":
            missing.append(_display_skill(skill))
        else:
            missing.append(_display_skill(skill))

    direct_matches = len(matched)
    return {
        "score_ratio": total_ratio / len(target_skills),
        "matched": deduplicate_preserve_order(matched),
        "missing": deduplicate_preserve_order(missing),
        "match_percentage": round((direct_matches / len(target_skills)) * 100),
        "evidence": evidence_items,
    }


def best_skill_evidence(target_skill: str, candidate: dict) -> dict:
    target = normalize_skill(target_skill)
    candidates = []
    for skill in candidate["explicit_skills"]:
        if skills_match(skill, target):
            candidates.append(_skill_evidence(target, "direct", 0.72, "explicit skills", skill))
        elif skills_related(skill, target):
            candidates.append(_skill_evidence(target, "related", 0.35, "explicit skills", skill))

    for project in candidate["projects"]:
        score = _text_skill_score(project["text"], project["skills"], target, demonstrated=True)
        if score:
            status, value = score
            candidates.append(_skill_evidence(target, status, value, f"project: {project['name']}", project["name"]))

    for item in candidate["experience"]:
        score = _text_skill_score(item["text"], item["skills"], target, demonstrated=True, experience=True)
        if score:
            status, value = score
            candidates.append(_skill_evidence(target, status, value, f"experience: {item['title']}", item["title"]))

    if not candidates:
        return _skill_evidence(target, "missing", 0.0, "", "")
    status_rank = {"direct": 3, "alias": 3, "related": 2, "missing": 1}
    return max(candidates, key=lambda item: (item["score"], status_rank.get(item["status"], 0)))


def _skill_evidence(skill: str, status: str, score: float, source: str, detail: str) -> dict:
    return {
        "requirement": _display_skill(skill),
        "status": status,
        "score": round(score, 3),
        "source": source,
        "evidence": detail,
    }


def _text_skill_score(text: str, skills: list, target: str, demonstrated: bool = False, experience: bool = False):
    if any(skills_match(skill, target) for skill in skills) or _text_has_skill(text, target):
        if demonstrated:
            return "direct", 1.0 if not experience else 0.9
        return "direct", 0.72
    if any(skills_related(skill, target) for skill in skills):
        return "related", 0.5 if demonstrated else 0.35
    for skill in RELATED_SKILLS.get(normalize_skill(target), set()):
        if _text_has_skill(text, skill):
            return "related", 0.5 if demonstrated else 0.35
    return None


def score_project_evidence(projects: list, requirements: dict) -> dict:
    if not _project_dimension_active(requirements):
        return {"score_ratio": 0, "notes": [], "evidence": []}
    if not projects:
        return {
            "score_ratio": 0,
            "notes": ["No resume projects were found to compare against the job description."],
            "evidence": [],
        }

    target_skills = requirements["required_skills"] + requirements["preferred_skills"]
    job_terms = _requirement_terms(requirements)
    project_results = []
    notes = []
    for project in projects:
        direct = [skill for skill in target_skills if _text_has_skill(project["text"], skill) or any(skills_match(skill, tech) for tech in project["skills"])]
        related = [skill for skill in target_skills if skill not in direct and any(skills_related(skill, tech) for tech in project["skills"])]
        responsibility_overlap = len(job_terms & set(_important_words(project["text"])))
        domain_overlap = [term for term in PROJECT_RELEVANCE_TERMS if _term_in_text(term, project["text"])]
        score = min(1.0, (0.28 * len(direct)) + (0.12 * len(related)) + (0.08 * min(responsibility_overlap, 3)) + (0.05 * min(len(domain_overlap), 4)))
        if direct:
            score = max(score, 0.65)
        elif related or responsibility_overlap:
            score = max(score, 0.35)
        evidence = {
            "project": project["name"],
            "score": round(score, 3),
            "direct_skills": [_display_skill(skill) for skill in direct],
            "related_skills": [_display_skill(skill) for skill in related],
            "responsibility_overlap_terms": sorted((job_terms & set(_important_words(project["text"]))))[:6],
        }
        project_results.append(evidence)
        if score > 0:
            reasons = []
            if direct:
                reasons.append("demonstrates " + ", ".join(_display_skill(skill) for skill in direct[:4]))
            if related:
                reasons.append("has transferable evidence for " + ", ".join(_display_skill(skill) for skill in related[:3]))
            if responsibility_overlap:
                reasons.append("overlaps with responsibility terms")
            notes.append(f"Project '{project['name']}' is relevant because it {', '.join(reasons)}.")

    best_two = sorted((item["score"] for item in project_results), reverse=True)[:2]
    score_ratio = sum(best_two) / max(1, min(2, len(best_two)))
    if not notes:
        notes = ["Projects are listed, but no clear overlap with job skills, role, or responsibilities was found."]
    return {"score_ratio": min(1.0, score_ratio), "notes": notes[:5], "evidence": project_results}


def score_experience_evidence(experience: list, requirements: dict) -> dict:
    active = bool(requirements["experience_requirements"] or _experience_terms(requirements))
    if not active:
        return {"score_ratio": 0, "note": "No experience requirement specified.", "missing": [], "evidence": []}
    if not experience:
        return {"score_ratio": 0, "note": "No experience or certifications found.", "missing": requirements["experience_requirements"][:3], "evidence": []}

    job_terms = _requirement_terms(requirements) | _experience_terms(requirements)
    evidence = []
    best = 0.0
    for item in experience:
        words = set(_important_words(item["text"]))
        overlap = sorted(words & job_terms)
        skill_overlap = [skill for skill in requirements["required_skills"] + requirements["preferred_skills"] if _text_has_skill(item["text"], skill)]
        score = min(1.0, 0.28 * len(skill_overlap) + 0.08 * min(len(overlap), 5))
        if re.search(r"\b(intern|internship|work|worked|developer|development|engineer)\b", item["text"]):
            score = max(score, 0.35)
        best = max(best, score)
        evidence.append({"source": item["title"], "score": round(score, 3), "matched_terms": overlap[:6], "matched_skills": [_display_skill(skill) for skill in skill_overlap]})

    note = "Experience relevance: " + (", ".join(deduplicate_preserve_order(term for item in evidence for term in item["matched_terms"])[:6]) or "limited direct overlap") + "."
    missing = [] if best >= 0.5 else requirements["experience_requirements"][:3]
    return {"score_ratio": min(1.0, best), "note": note, "missing": missing, "evidence": evidence}


def score_education_evidence(education_text: str, requirements: dict) -> dict:
    education_requirements = requirements["education_requirements"]
    if not education_requirements:
        role_text = _normalize_search_text(requirements["role_title"])
        if not any(term in role_text for term in ("intern", "student", "graduate")):
            return {"score_ratio": 0, "note": "No education or eligibility requirement specified.", "missing": [], "evidence": []}
    if not education_text:
        return {"score_ratio": 0, "note": "No education details found.", "missing": education_requirements[:3], "evidence": []}

    req_text = _normalize_search_text(" ".join(education_requirements) + " " + requirements["role_title"])
    education_terms = {
        "b.tech", "btech", "bachelor", "computer science", "engineering", "artificial intelligence",
        "data science", "machine learning", "ai", "diploma", "degree", "student", "currently pursuing",
    }
    matched_terms = [term for term in education_terms if term in education_text and (not req_text or term in req_text or term in {"student", "currently pursuing"})]
    if not matched_terms and not education_requirements:
        matched_terms = [term for term in education_terms if term in education_text][:2]

    score = min(1.0, 0.3 + 0.18 * len(matched_terms)) if matched_terms else 0.15
    note = "Education is relevant: " + ", ".join(_display_skill(term) for term in matched_terms[:5]) + "." if matched_terms else "Education is present, but direct eligibility overlap is limited."
    missing = [] if score >= 0.5 else education_requirements[:3]
    return {"score_ratio": score, "note": note, "missing": missing, "evidence": [{"matched_terms": matched_terms, "score": round(score, 3)}]}


def _active_weights(requirements: dict) -> dict:
    active = {}
    if requirements["required_skills"]:
        active["required_skills"] = BASE_WEIGHTS["required_skills"]
    if _project_dimension_active(requirements):
        active["project_relevance"] = BASE_WEIGHTS["project_relevance"]
    if requirements["experience_requirements"] or _experience_terms(requirements):
        active["experience_relevance"] = BASE_WEIGHTS["experience_relevance"]
    if requirements["education_requirements"] or re.search(r"\b(intern|student|graduate)\b", requirements["role_title"], re.I):
        active["education_relevance"] = BASE_WEIGHTS["education_relevance"]
    if requirements["preferred_skills"]:
        active["preferred_skills"] = BASE_WEIGHTS["preferred_skills"]
    if not active:
        return {"required_skills": 100}
    total = sum(active.values())
    return {name: round((weight / total) * 100, 3) for name, weight in active.items()}


def _project_dimension_active(requirements: dict) -> bool:
    return bool(requirements["required_skills"] or requirements["preferred_skills"] or requirements["responsibilities"])


def _apply_mandatory_caps(score: int, required: dict, education: dict, requirements: dict) -> int:
    if requirements["required_skills"]:
        direct_ratio = required["match_percentage"] / 100
        if direct_ratio == 0:
            score = min(score, 45)
        elif direct_ratio < 0.5:
            score = min(score, 62)
        elif required["missing"]:
            score = min(score, 78)
    if requirements["education_requirements"] and education["score_ratio"] < 0.5:
        score = min(score, 68)
    return max(0, min(100, score))


def _cap_sparse_job_score(score: int, job_profile: dict, requirements: dict | None = None) -> int:
    requirements = requirements or build_jd_requirements(job_profile)
    requirement_count = len(requirements["required_skills"]) + len(requirements["preferred_skills"]) + len(requirements["responsibilities"]) + len(requirements["eligibility"])
    has_role = bool(str(job_profile.get("role_title", "")).strip())
    if requirement_count <= 1:
        return min(score, 55 if has_role else 50)
    if requirement_count <= 2 and not requirements["responsibilities"]:
        return min(score, 65)
    return score


def assessment_confidence(requirements: dict, candidate: dict, required: dict, preferred: dict, projects: dict, experience: dict, education: dict) -> str:
    jd_signal_count = len(requirements["required_skills"]) + len(requirements["preferred_skills"]) + len(requirements["responsibilities"]) + len(requirements["eligibility"])
    evidence_count = len(candidate["explicit_skills"]) + len(candidate["projects"]) + len(candidate["experience"]) + (1 if candidate["education_text"] else 0)
    evidence_hits = sum(1 for item in required["evidence"] + preferred["evidence"] if item["status"] in {"direct", "alias", "related"})
    evidence_hits += sum(1 for item in projects["evidence"] if item.get("score", 0) > 0.35)
    evidence_hits += sum(1 for item in experience["evidence"] if item.get("score", 0) > 0.35)
    if jd_signal_count <= 1:
        return "low"
    if jd_signal_count >= 4 and evidence_count >= 4 and evidence_hits >= 3:
        return "high"
    return "medium"


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


@lru_cache(maxsize=None)
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
            values = [item.get("name", ""), item.get("description", ""), " ".join(str(tech) for tech in item.get("technologies", []) if tech)]
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
    return False


def skills_related(candidate_skill: str, required_skill: str) -> bool:
    candidate = normalize_skill(candidate_skill)
    target = normalize_skill(required_skill)
    if skills_match(candidate, target):
        return False
    if target == "Frontend Development" and candidate in FRONTEND_RELEVANT_SKILLS:
        return True
    if candidate == "Frontend Development" and target in FRONTEND_RELEVANT_SKILLS:
        return True
    if target == "Backend Development" and candidate in BACKEND_RELEVANT_SKILLS:
        return True
    if candidate == "Backend Development" and target in BACKEND_RELEVANT_SKILLS:
        return True
    return candidate in RELATED_SKILLS.get(target, set()) or target in RELATED_SKILLS.get(candidate, set())


def calculate_skill_matches(candidate_skills: list, target_skills: list) -> dict:
    scored = score_skill_requirements(target_skills, {"explicit_skills": normalize_list(candidate_skills), "projects": [], "experience": [], "education_text": ""})
    return {"matched_skills": scored["matched"], "missing_skills": scored["missing"], "match_percentage": scored["match_percentage"]}


def calculate_required_skill_score(candidate_skills: list, required_skills: list) -> tuple:
    matches = calculate_skill_matches(candidate_skills, required_skills)
    if not required_skills:
        matches["match_percentage"] = 100
        return 0, matches
    return (matches["match_percentage"] / 100) * BASE_WEIGHTS["required_skills"], matches


def calculate_preferred_skill_score(candidate_skills: list, preferred_skills: list) -> tuple:
    matches = calculate_skill_matches(candidate_skills, preferred_skills)
    if not preferred_skills:
        matches["match_percentage"] = 100
        return 0, matches
    return (matches["match_percentage"] / 100) * BASE_WEIGHTS["preferred_skills"], matches


def calculate_project_relevance_score(projects: list, job_profile: dict) -> tuple:
    result = score_project_evidence([_project_evidence(project) for project in projects or []], build_jd_requirements(job_profile))
    return result["score_ratio"] * BASE_WEIGHTS["project_relevance"], result["notes"]


def calculate_education_score(education: list, job_profile: dict) -> tuple:
    result = score_education_evidence(_normalize_search_text(" ".join(str(item) for item in education or [])), build_jd_requirements(job_profile))
    return result["score_ratio"] * BASE_WEIGHTS["education_relevance"], result["note"]


def calculate_experience_score(experience: list, certifications: list, job_profile: dict) -> tuple:
    candidate = {"experience": [_experience_evidence(item) for item in (experience or [])] + [{"title": "Certification", "text": _normalize_search_text(str(item)), "skills": _skills_in_text(str(item))} for item in (certifications or [])]}
    result = score_experience_evidence(candidate["experience"], build_jd_requirements(job_profile))
    return result["score_ratio"] * BASE_WEIGHTS["experience_relevance"], result["note"]


def _project_evidence(project) -> dict:
    if isinstance(project, dict):
        name = str(project.get("name", "") or "").strip() or "Unnamed project"
        description = str(project.get("description", "") or "")
        technologies = normalize_list(project.get("technologies", []) or [])
        text = _normalize_search_text(" ".join([name, description, " ".join(technologies)]))
    else:
        name = str(project).strip()[:80] or "Unnamed project"
        text = _normalize_search_text(str(project))
        technologies = _skills_in_text(text)
    return {"name": name, "text": text, "skills": deduplicate_preserve_order(technologies + _skills_in_text(text))}


def _experience_evidence(item) -> dict:
    if isinstance(item, dict):
        title = str(item.get("title") or item.get("role") or item.get("company") or "Experience")
        text = _normalize_search_text(" ".join(str(value) for value in item.values() if value))
    else:
        title = str(item).strip()[:80] or "Experience"
        text = _normalize_search_text(str(item))
    return {"title": title, "text": text, "skills": _skills_in_text(text)}


def _skills_in_text(text: str) -> list:
    normalized_text = _normalize_search_text(text)
    return deduplicate_preserve_order([skill for skill in CANONICAL_SKILLS if _text_has_skill(normalized_text, skill)])


def _text_has_skill(text: str, skill: str) -> bool:
    return any(_skill_variant_pattern(variant).search(text) for variant in _skill_variants(skill))


def _term_in_text(term: str, text: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])", text))


@lru_cache(maxsize=None)
def _skill_variants(skill: str) -> frozenset:
    normalized = normalize_skill(skill)
    variants = {_comparison_key(normalized)}
    aliases = CANONICAL_SKILLS.get(normalized, set())
    variants.update(_comparison_key(alias) for alias in aliases)
    return frozenset(variant for variant in variants if variant)


@lru_cache(maxsize=None)
def _skill_variant_pattern(variant: str):
    return re.compile(rf"(?<![a-z0-9]){re.escape(variant)}(?![a-z0-9])")


@lru_cache(maxsize=None)
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
    text = str(value or "").lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _fallback_display_skill(value: str) -> str:
    special_cases = {"b.tech": "B.Tech", "btech": "B.Tech", "3rd year": "3rd Year", "third year": "3rd Year", "6th semester": "6th Semester", "sixth semester": "6th Semester"}
    if value in special_cases:
        return special_cases[value]
    return " ".join(word.upper() if word in {"ai", "ml", "nlp", "api", "sql", "css", "html", "rag"} else word.capitalize() for word in value.split())


def _display_skill(skill: str) -> str:
    return normalize_skill(skill)


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _extract_experience_requirements(items: list[str]) -> list[str]:
    requirements = []
    for item in items:
        lowered = item.lower()
        if re.search(r"\b(experience|internship|worked|work experience|projects?|hands[- ]on|familiarity)\b", lowered):
            requirements.append(item)
    return deduplicate_preserve_order(requirements)


def _extract_education_requirements(items: list[str]) -> list[str]:
    requirements = []
    for item in items:
        lowered = item.lower()
        if re.search(r"\b(b\.?tech|btech|bachelor|degree|computer science|engineering|student|graduate|semester|year|diploma)\b", lowered):
            requirements.append(item)
    return deduplicate_preserve_order(requirements)


def _requirement_terms(requirements: dict) -> set[str]:
    text = " ".join([requirements["role_title"], " ".join(requirements["responsibilities"]), " ".join(requirements["keywords"]), " ".join(requirements["required_skills"]), " ".join(requirements["preferred_skills"])])
    return set(_important_words(text))


def _experience_terms(requirements: dict) -> set[str]:
    text = " ".join(requirements["experience_requirements"] + requirements["responsibilities"])
    words = set(_important_words(text))
    if re.search(r"\b(intern|internship|experience|work|worked|project|hands[- ]on)\b", text, re.I):
        words.update({"intern", "internship", "experience", "project", "worked", "development"})
    return words


def _important_words(value: str) -> list:
    stop_words = {"and", "or", "the", "a", "an", "to", "with", "for", "of", "in", "on", "using", "build", "work", "will", "include", "includes", "intern", "internship", "skills", "required", "preferred", "small", "prepare", "evaluate", "create", "develop"}
    words = re.findall(r"[a-z][a-z0-9.+#-]*", _normalize_search_text(value))
    return [word for word in words if len(word) > 2 and word not in stop_words]
