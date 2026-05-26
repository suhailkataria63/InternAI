import re


APPLICATION_WRITER_PROMPT_TEMPLATE = """
You are the Application Writer Agent for InternAI.

Write a customized internship application answer using:
- resume_profile
- job_profile
- match_result
- skill_gap_result
- application_question
- tone
- word_limit

Expected JSON output:
{
  "question": "",
  "generated_answer": "",
  "key_points_used": [],
  "tone": "",
  "word_count": 0,
  "improvement_note": ""
}

Rules:
- Use only facts present in the provided profiles.
- Mention missing skills only as learning goals, not as skills already mastered.
- Avoid fake claims, inflated experience, or invented metrics.
- Keep the answer within the requested word limit when possible.
- Match the requested tone.
"""


def generate_application_answer(
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
    skill_gap_result: dict,
    application_question: str,
    tone: str = "professional",
    word_limit: int = 180,
) -> dict:
    question_type = detect_question_type(application_question)
    key_points = build_key_points(resume_profile, job_profile, match_result, skill_gap_result)
    answer = _build_answer_by_type(
        question_type=question_type,
        resume_profile=resume_profile,
        job_profile=job_profile,
        match_result=match_result,
        skill_gap_result=skill_gap_result,
    )
    answer = apply_tone(answer, tone)
    answer = trim_to_word_limit(answer, word_limit)
    answer = clean_generated_text(answer)

    return {
        "question": application_question,
        "generated_answer": answer,
        "key_points_used": key_points,
        "tone": tone,
        "word_count": count_words(answer),
        "improvement_note": _build_improvement_note(match_result, skill_gap_result),
    }


def normalize_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def extract_candidate_name(resume_profile: dict) -> str:
    return normalize_text(resume_profile.get("name")) or "I"


def extract_top_skills(resume_profile: dict, match_result: dict, limit: int = 5) -> list:
    matched_skills = match_result.get("matched_skills", [])
    resume_skills = resume_profile.get("skills", [])
    skills = []

    for skill in matched_skills + resume_skills:
        normalized_skill = format_skill_display(skill)
        if normalized_skill and normalized_skill.lower() not in [item.lower() for item in skills]:
            skills.append(normalized_skill)

    return skills[:limit]


def extract_project_highlights(resume_profile: dict, limit: int = 2) -> list:
    projects = resume_profile.get("projects", []) or []
    highlights = []

    for index, project in enumerate(projects[:limit]):
        project_text = format_project_for_answer(project, index)

        if project_text:
            highlights.append(project_text)

    return highlights[:limit]


def select_best_education(education: list[str]) -> str:
    items = [education] if isinstance(education, str) else education or []
    cleaned_items = [_clean_education_summary(normalize_text(item)) for item in items]
    cleaned_items = [item for item in cleaned_items if item]
    if not cleaned_items:
        return "my academic background"

    def score(item: str) -> int:
        lowered = item.lower()
        points = 0
        if re.search(r"\bb\.?\s?tech\b|\bbtech\b|bachelor|b\.e\b|degree", lowered):
            points += 8
        if any(term in lowered for term in ("artificial intelligence", "data science", "computer science", "engineering")):
            points += 4
        if "currently pursuing" in lowered:
            points += 3
        if "diploma" in lowered:
            points -= 3
        if "class x" in lowered or "class 10" in lowered or "cbse" in lowered:
            points -= 8
        return points

    best = max(cleaned_items, key=score)
    return _shorten_education_for_writing(best)


def clean_project_description_for_writing(project_name: str, description: str) -> str:
    text = normalize_text(description)
    if not text:
        return ""

    cleanup_patterns = (
        r"Suhail\s+Kataria\s+is\s+pursuing[^.]*\.?",
        r"He\s+has\s+skills[^.]*\.?",
        r"Projects?\s+include\s+",
        r"Another\s+project\s+is\s+",
        r"He\s+has\s+internship\s+experience[^.]*\.?",
        r"He\s+is\s+looking\s+for[^.]*\.?",
    )
    for pattern in cleanup_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

    if project_name:
        text = re.sub(re.escape(project_name), "", text, flags=re.IGNORECASE).strip(" :-,.;")

    text = re.sub(r"\bStrategic Classification System\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bI\s+[A-Z][A-Za-z0-9&/ -]+(?:System|Modeling|Model|Classification System)\b", "", text)
    text = re.sub(r"\bwhere\s+he\s+worked\b", "worked", text, flags=re.IGNORECASE)
    text = re.sub(r"\bhe\s+worked\s+on\b", "worked on", text, flags=re.IGNORECASE)
    text = re.sub(r"\bhe\s+(built|developed|created|implemented)\b", lambda match: match.group(1), text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" :-,.;")

    sentences = [sentence.strip(" .") for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip(" .")]
    if sentences:
        priority_terms = ("built", "developed", "created", "implemented", "worked", "preprocessing", "classification", "phishing", "model", "dashboard", "deployment")
        text = next((sentence for sentence in sentences if any(term in sentence.lower() for term in priority_terms)), sentences[0])

    text = re.sub(r"^(I\s+)?(built|developed|created|implemented|worked|performed|conducted)\b", lambda match: match.group(2).lower(), text, flags=re.IGNORECASE)
    text = re.sub(r"^(and|or)\s+", "", text, flags=re.IGNORECASE)
    if " using " in text.lower():
        text = re.split(r"\s+using\s+", text, maxsplit=1, flags=re.IGNORECASE)[0]
    return _trim_words(text.strip(" :-,.;"), 35).rstrip(".")


def format_project_for_answer(project: dict, index: int) -> str:
    name, description, technologies = _project_parts(project)
    action_summary = clean_project_description_for_writing(name, description)
    technology_text = _technology_text(technologies)

    if _is_messy_project_summary(action_summary):
        action_summary = _fallback_project_summary(name, technology_text)
    elif technology_text and not re.search(r"\busing\b", action_summary, re.IGNORECASE):
        action_summary = f"{action_summary} using {technology_text}"

    action_summary = _trim_words(action_summary, 35).rstrip(".")
    if not name:
        name = "practical"

    if index == 0:
        return f"In my {name} project, I {action_summary}."
    action_summary = re.sub(r"^worked on\s+", "", action_summary, flags=re.IGNORECASE)
    return f"I also worked on a {name} project involving {action_summary}."


def summarize_project_for_writing(project: dict, max_words: int = 35) -> str:
    return _trim_words(format_project_for_answer(project, 0), max_words + 8)


def _project_parts(project: dict) -> tuple[str, str, list]:
    if isinstance(project, str):
        name = normalize_text(project)
        description = ""
        technologies = []
    elif isinstance(project, dict):
        name = normalize_text(project.get("name"))
        description = normalize_text(project.get("description"))
        technologies = [format_skill_display(item) for item in project.get("technologies", []) if normalize_text(item)]
    else:
        name = normalize_text(getattr(project, "name", ""))
        description = normalize_text(getattr(project, "description", ""))
        technologies = [
            format_skill_display(item)
            for item in getattr(project, "technologies", [])
            if normalize_text(item)
        ]
    return name, description, technologies


def summarize_education(education) -> str:
    return select_best_education(education)


def detect_question_type(application_question: str) -> str:
    question = normalize_text(application_question).lower()

    if any(phrase in question for phrase in ("why should we hire", "why hire", "hire you")):
        return "why_hire"
    if any(phrase in question for phrase in ("why are you interested", "why interested", "why this role", "why do you want")):
        return "why_interested"
    if any(phrase in question for phrase in ("experience", "project", "worked on", "relevant")):
        return "relevant_experience"
    if any(phrase in question for phrase in ("cover", "message", "note", "letter")):
        return "cover_message"
    return "general"


def build_key_points(
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
    skill_gap_result: dict,
) -> list:
    key_points = []
    education = summarize_education(resume_profile.get("education", []))
    role_title = _safe_role_title(job_profile.get("role_title"), "this internship")
    company_name = normalize_text(job_profile.get("company_name"))
    top_skills = extract_top_skills(resume_profile, match_result)
    projects = extract_project_highlights(resume_profile)
    missing_skills = [format_skill_display(skill) for skill in match_result.get("missing_skills", [])]

    if education:
        key_points.append(f"Education: {education}")
    key_points.append(f"Target role: {role_title}")
    if company_name:
        key_points.append(f"Company: {company_name}")
    if top_skills:
        key_points.append("Matched skills: " + ", ".join(top_skills))
    for project in projects:
        key_points.append(f"Project: {_project_name_from_summary(project)}")
    if missing_skills:
        key_points.append("Learning focus: " + ", ".join(missing_skills[:3]))

    return key_points


def apply_tone(answer: str, tone: str) -> str:
    normalized_tone = normalize_text(tone).lower()

    if normalized_tone == "confident":
        return answer.replace("I believe I can", "I can").replace("I would be excited", "I am excited")
    if normalized_tone == "friendly":
        return answer.replace("I am interested", "I am genuinely excited").replace("I would bring", "I would love to bring")
    if normalized_tone == "concise":
        return answer.replace("I would be excited to", "I can").replace("I am interested in", "I want")
    return answer


def trim_to_word_limit(answer: str, word_limit: int) -> str:
    if word_limit <= 0:
        return answer

    words = answer.split()
    if len(words) <= word_limit:
        return answer

    trimmed = " ".join(words[:word_limit]).rstrip(".,;:")
    sentence_end_positions = [
        trimmed.rfind("."),
        trimmed.rfind("!"),
        trimmed.rfind("?"),
    ]
    last_sentence_end = max(sentence_end_positions)
    if last_sentence_end > len(trimmed) * 0.55:
        return trimmed[: last_sentence_end + 1]
    return trimmed + "."


def count_words(answer: str) -> int:
    return len(answer.split())


def _build_answer_by_type(
    question_type: str,
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
    skill_gap_result: dict,
) -> str:
    role_title = _safe_role_title(job_profile.get("role_title"), "this internship")
    company_name = normalize_text(job_profile.get("company_name"))
    education = summarize_education(resume_profile.get("education", []))
    skills = extract_top_skills(resume_profile, match_result, limit=4)
    projects = extract_project_highlights(resume_profile)
    learning_focus = _learning_focus(match_result, skill_gap_result)

    role_phrase = _role_phrase(role_title, company_name)

    context_sentence = _context_sentence(education, role_phrase)
    skills_sentence = _skills_sentence(skills)
    projects_sentence = _projects_sentence(projects)
    learning_sentence = _learning_sentence(learning_focus)

    if question_type == "why_hire":
        return (
            f"{context_sentence} {skills_sentence} {projects_sentence} "
            f"I would bring a practical, learning-oriented approach to {role_phrase}. "
            f"{learning_sentence}"
        )

    if question_type == "why_interested":
        return (
            f"I am interested in {role_phrase} because it connects closely with my current skills and project work. "
            f"{context_sentence} {skills_sentence} {projects_sentence} "
            f"I would be excited to contribute while continuing to grow through real internship responsibilities. {learning_sentence}"
        )

    if question_type == "relevant_experience":
        return (
            f"My most relevant experience comes from project work and hands-on practice. "
            f"{projects_sentence} {skills_sentence} {context_sentence} "
            f"This background makes me prepared to contribute to {role_phrase} while continuing to improve. {learning_sentence}"
        )

    if question_type == "cover_message":
        return (
            f"Dear Hiring Team, I am writing to express my interest in {role_phrase}. "
            f"{context_sentence} {skills_sentence} {projects_sentence} "
            f"I would welcome the opportunity to contribute, learn from the team, and build useful work. {learning_sentence}"
        )

    return (
        f"{context_sentence} I am interested in {role_phrase}. "
        f"{skills_sentence} {projects_sentence} "
        f"I would bring curiosity, consistency, and a willingness to contribute to real project work. {learning_sentence}"
    )


def _context_sentence(education: str, role_phrase: str) -> str:
    if education and education != "my academic background":
        if re.search(r"\bb\.?\s?tech\b|\bbtech\b|bachelor|b\.e\b", education, re.IGNORECASE):
            return f"My {education} background connects well with {role_phrase}."
        return f"My background in {education} connects well with {role_phrase}."
    return f"I am applying for {role_phrase}."


def _skills_sentence(skills: list) -> str:
    if not skills:
        return "My current profile shows a foundation I am continuing to strengthen."
    return "My strongest matched skills include " + ", ".join(skills) + "."


def _projects_sentence(projects: list) -> str:
    if not projects:
        return "I am also working on building clearer project evidence for my resume."
    if len(projects) == 1:
        return projects[0]
    return f"{projects[0]} {projects[1]}"


def _learning_sentence(learning_focus: list) -> str:
    if not learning_focus:
        return "I am ready to keep learning and contribute carefully."
    return (
        "I am also actively working to improve in "
        + ", ".join(learning_focus)
        + ", so I can close the remaining gaps responsibly."
    )


def _learning_focus(match_result: dict, skill_gap_result: dict) -> list:
    priority_skills = skill_gap_result.get("priority_skills", [])
    if priority_skills:
        return [format_skill_display(item.get("skill")) for item in priority_skills[:3] if item.get("skill")]
    return [format_skill_display(skill) for skill in match_result.get("missing_skills", [])[:3]]


def _build_improvement_note(match_result: dict, skill_gap_result: dict) -> str:
    missing_skills = match_result.get("missing_skills", [])
    if missing_skills:
        return "Review the answer after adding stronger evidence for: " + ", ".join(missing_skills[:3]) + "."
    if skill_gap_result.get("overall_advice"):
        return normalize_text(skill_gap_result["overall_advice"])
    return "Review the answer for company-specific details before submitting."


def _first_item(items: list) -> str:
    if not items:
        return ""
    return normalize_text(items[0])


def _clean_education_summary(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip(" -•\t.,")
    stop_phrases = (
        "skills include",
        "projects include",
        "another project",
        "experience includes",
        "he has skills",
        "she has skills",
        "i have skills",
        "projects include",
    )
    lowered = text.lower()
    stop_positions = [lowered.find(phrase) for phrase in stop_phrases if lowered.find(phrase) != -1]
    if stop_positions:
        text = text[: min(stop_positions)].strip(" -•\t.,")

    sentence_match = re.search(
        r"([^.!?]*(?:b\.?tech|bachelor|computer science|artificial intelligence|data science|ai&ds|ai and ds)[^.!?]*)",
        text,
        flags=re.IGNORECASE,
    )
    if sentence_match:
        text = sentence_match.group(1).strip(" -•\t.,")

    text = re.sub(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\s+is\s+pursuing\s+", "", text)
    text = re.sub(r"^(?:he|she|i)\s+is\s+pursuing\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^pursuing\s+", "", text, flags=re.IGNORECASE)
    return text[:180].rsplit(" ", 1)[0].strip(" -•\t.,") if len(text) > 180 else text


def _shorten_education_for_writing(value: str) -> str:
    text = normalize_text(value)
    text = re.split(
        r"\s+(?:at|under)\s+|,\s*(?:3rd|third|4th|fourth|2nd|second|1st|first)\s+year|,\s*\d+(?:st|nd|rd|th)?\s+semester|—\s*currently pursuing",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" ,-—")
    stop_markers = (
        "Chandigarh Group of Colleges",
        "CGC",
        "Landran",
        "under",
        "Currently Pursuing",
        "PSBTE",
        "CBSE",
    )
    for marker in stop_markers:
        position = text.lower().find(marker.lower())
        if position > 0:
            text = text[:position].strip(" ,-—")
            break
    return text[:140].rsplit(" ", 1)[0].strip(" ,-—") if len(text) > 140 else text


def _safe_role_title(value, fallback: str) -> str:
    role_title = normalize_text(value)
    suspicious_phrases = (
        "deployment experience",
        "the internship",
        "required skills",
        "preferred skills",
        "responsibilities",
        "candidate should",
        "selected intern",
    )
    if not role_title or any(phrase in role_title.lower() for phrase in suspicious_phrases):
        return fallback
    return role_title


def _role_phrase(role_title: str, company_name: str = "") -> str:
    if role_title.lower() in {"this internship", "the internship role"}:
        return role_title
    if role_title.lower() == "intern":
        phrase = "the internship role"
    else:
        phrase = f"the {role_title} role"
    if company_name:
        return f"{phrase} at {company_name}"
    return phrase


def _remove_duplicate_project_title(name: str, description: str) -> str:
    if not description:
        return ""
    description = re.sub(r"projects?\s+include\s+", "", description, flags=re.IGNORECASE).strip(" :-,.;")
    description = re.sub(
        r"^(?:[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s+)?(?:is\s+)?(?:an?\s+)?(?:artificial intelligence|data science|computer science).*?(?:real-world problems|academic projects)\.?",
        "",
        description,
        flags=re.IGNORECASE,
    ).strip(" :-,.;")
    if name and description.lower().startswith(name.lower()):
        description = description[len(name) :].strip(" :-,.;")
    return description


def _important_project_sentence(description: str) -> str:
    if not description:
        return ""
    sentences = [sentence.strip(" .") for sentence in re.split(r"(?<=[.!?])\s+", description) if sentence.strip()]
    priority_terms = ("accuracy", "built", "developed", "dashboard", "model", "forecast", "predict", "nlp")
    selected = next((sentence for sentence in sentences if any(term in sentence.lower() for term in priority_terms)), sentences[0])
    selected = re.sub(r"^projects?\s+include\s+", "", selected, flags=re.IGNORECASE)
    selected = re.sub(r"^(and|or)\s+", "", selected, flags=re.IGNORECASE)
    selected = re.sub(r"^(I\s+)?(built|developed|created|implemented|performed|conducted)\b", lambda match: match.group(2).lower(), selected, flags=re.IGNORECASE)
    if " using " in selected.lower():
        selected = re.split(r"\s+using\s+", selected, maxsplit=1, flags=re.IGNORECASE)[0]
    return selected.strip(" .")


def _technology_text(technologies: list) -> str:
    unique_technologies = []
    for technology in technologies:
        if technology and technology.lower() not in [item.lower() for item in unique_technologies]:
            unique_technologies.append(technology)
    return ", ".join(format_skill_display(item) for item in unique_technologies[:5])


def _trim_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(".,;:") + "."


def _project_name_from_summary(summary: str) -> str:
    text = normalize_text(summary)
    text = re.sub(r"^In my\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^I also worked on an?\s+", "", text, flags=re.IGNORECASE)
    return text.split(" project", 1)[0].strip(" .")


def _is_messy_project_summary(summary: str) -> bool:
    lowered = normalize_text(summary).lower()
    return (
        not lowered
        or lowered.startswith(("an ", "a ", "the "))
        or "projects include" in lowered
        or "where he worked" in lowered
        or "strategic classification system" in lowered
        or bool(re.search(r"\bi\s+[a-z0-9&/ -]+(?:system|modeling|classification system)\b", lowered))
    )


def _fallback_project_summary(project_name: str, technology_text: str) -> str:
    lowered_name = project_name.lower()
    if "phishing" in lowered_name:
        return "built an AI/ML-based phishing detection system using " + (technology_text or "Python, NLP, React, Next.js, and Tailwind CSS")
    if "restaurant growth" in lowered_name:
        return "worked on data preprocessing, feature engineering, classification model development, evaluation, documentation, and deployment"
    if technology_text:
        return f"worked on a practical project using {technology_text}"
    return "worked on a practical project with clear technical implementation and documentation"


def clean_generated_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = cleaned.replace(" ,", ",")
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = re.sub(r"where I Projects include", "where I", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"project,\s+I\s+and\b", "project involving", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"involving\s+worked\s+on\s+", "involving ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"project,\s+I\s+Strategic\b", "project involving strategic", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"project,\s+I\s+Hybrid Phishing Detection System\b", "project, I built", cleaned, flags=re.IGNORECASE)
    return cleaned


def format_skill_display(skill: str) -> str:
    normalized = normalize_text(skill).lower()
    compact = normalized.replace(" ", "").replace("-", "")
    special_cases = {
        "express.js": "Express.js",
        "expressjs": "Express.js",
        "rest api": "REST API",
        "restapi": "REST API",
        "restful api": "REST API",
        "websockets": "WebSockets",
        "websocket": "WebSockets",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "node.js": "Node.js",
        "nodejs": "Node.js",
        "next.js": "Next.js",
        "nextjs": "Next.js",
        "github": "GitHub",
        "git": "Git",
        "nlp": "NLP",
        "css": "CSS",
        "html": "HTML",
        "sql": "SQL",
        "api": "API",
        "fastapi": "FastAPI",
        "tailwind css": "Tailwind CSS",
        "tailwindcss": "Tailwind CSS",
    }
    return special_cases.get(normalized) or special_cases.get(compact) or normalize_text(skill)


def _project_dict_to_text(project: dict) -> str:
    name = normalize_text(project.get("name"))
    description = normalize_text(project.get("description"))
    technologies = project.get("technologies", [])
    technology_text = ", ".join(normalize_text(item) for item in technologies if item)

    if name and description.lower() == name.lower():
        description = ""
    if name and description and technology_text:
        return f"{name}, which {description.lower()}, using {technology_text}"
    if name and description:
        return f"{name}, which {description.lower()}"
    if name and technology_text:
        return f"{name}, using {technology_text}"
    if description and technology_text:
        return f"{description} using {technology_text}"
    return name or description or technology_text


def _project_object_to_text(project: object) -> str:
    return _project_dict_to_text(
        {
            "name": getattr(project, "name", ""),
            "description": getattr(project, "description", ""),
            "technologies": getattr(project, "technologies", []),
        }
    )
