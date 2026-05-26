import re

from app.services.llm_service import LLMService


COVER_LETTER_PROMPT_TEMPLATE = """
You are the Cover Letter Agent for InternAI.

Generate a customized internship cover letter using:
- resume_profile
- job_profile
- match_result
- skill_gap_result
- tone
- length

Expected JSON output:
{
  "cover_letter": "",
  "subject_line": "",
  "opening_summary": "",
  "key_points_used": [],
  "tone": "",
  "word_count": 0
}

Rules:
- Use only facts present in the provided profiles.
- Start the cover letter with "Dear Hiring Team,"
- Mention missing skills only as learning goals, not as skills already mastered.
- Avoid fake claims, inflated experience, or invented metrics.
- Keep short letters around 120-180 words and medium letters around 180-260 words.
- Match the requested tone.
"""


def generate_cover_letter(
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
    skill_gap_result: dict,
    tone: str = "professional",
    length: str = "short",
) -> dict:
    rule_based_result = generate_rule_based_cover_letter(
        resume_profile=resume_profile,
        job_profile=job_profile,
        match_result=match_result,
        skill_gap_result=skill_gap_result,
        tone=tone,
        length=length,
    )

    llm_service = LLMService()
    llm_status = llm_service.get_status()
    if llm_status.get("provider") == "mock":
        return _with_generation_metadata(
            rule_based_result,
            source="rule_based",
            provider=llm_status.get("provider", "mock"),
            used_fallback=True,
        )

    system_prompt, user_prompt = build_cover_letter_prompt(
        resume_profile=resume_profile,
        job_profile=job_profile,
        match_result=match_result,
        skill_gap_result=skill_gap_result,
        tone=tone,
        cover_letter_length=length,
    )
    llm_result = llm_service.generate_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.3,
        max_tokens=_llm_max_tokens_for_length(length),
    )
    llm_cover_letter = llm_result.get("text", "").strip()

    if llm_result.get("used_fallback") or not is_valid_llm_cover_letter(
        llm_cover_letter, length
    ):
        return _with_generation_metadata(
            rule_based_result,
            source="rule_based",
            provider=llm_result.get("provider", llm_status.get("provider", "mock")),
            used_fallback=True,
        )

    llm_cover_letter = clean_generated_text(llm_cover_letter)
    return {
        **rule_based_result,
        "cover_letter": llm_cover_letter,
        "word_count": count_words(llm_cover_letter),
        "generation_source": "llm",
        "llm_provider": llm_result.get("provider", llm_status.get("provider", "")),
        "used_fallback": False,
    }


def generate_rule_based_cover_letter(
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
    skill_gap_result: dict,
    tone: str = "professional",
    length: str = "short",
) -> dict:
    subject_line = build_subject_line(job_profile)
    key_points = build_key_points(resume_profile, job_profile, match_result)
    cover_letter = _build_cover_letter(
        resume_profile=resume_profile,
        job_profile=job_profile,
        match_result=match_result,
        skill_gap_result=skill_gap_result,
        length=length,
    )
    cover_letter = apply_tone(cover_letter, tone)
    cover_letter = _fit_length(cover_letter, length)
    cover_letter = clean_generated_text(cover_letter)

    return {
        "cover_letter": cover_letter,
        "subject_line": subject_line,
        "opening_summary": _build_opening_summary(resume_profile, job_profile),
        "key_points_used": key_points,
        "tone": tone,
        "word_count": count_words(cover_letter),
    }


def build_cover_letter_prompt(
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
    skill_gap_result: dict,
    tone: str,
    cover_letter_length: str,
) -> tuple[str, str]:
    candidate_name = extract_candidate_name(resume_profile)
    role_title = _safe_role_title(job_profile.get("role_title"), "the internship role")
    company_name = normalize_text(job_profile.get("company_name"))
    education = extract_education(resume_profile)
    candidate_skills = [
        format_skill_display(skill)
        for skill in _string_list(resume_profile.get("skills", []))
    ][:10]
    matched_skills = extract_top_skills(resume_profile, match_result, limit=5)
    missing_skills = [
        format_skill_display(skill)
        for skill in (
            match_result.get("missing_required_skills")
            or match_result.get("missing_skills")
            or []
        )
    ][:5]
    projects = extract_project_highlights(resume_profile, limit=2)
    responsibilities = [
        normalize_text(item)
        for item in (job_profile.get("responsibilities", []) or [])[:3]
        if normalize_text(item)
    ]

    system_prompt = (
        "You are an internship cover letter writing assistant. "
        "Use only the provided structured data. Do not invent experience, companies, "
        "certifications, achievements, metrics, or skills. Do not claim missing skills as "
        "already mastered; mention missing skills only as active learning or improvement focus. "
        "Keep the cover letter concise, professional, and grounded. Return only the cover letter "
        "text with no markdown. Include a greeting and closing. Do not include fake address or "
        "date blocks."
    )
    user_prompt = "\n".join(
        [
            f"Candidate name: {candidate_name}",
            f"Target role: {role_title}",
            f"Company: {company_name or 'Not provided'}",
            f"Education: {education}",
            f"Candidate skills: {', '.join(candidate_skills) or 'Not provided'}",
            f"Matched skills: {', '.join(matched_skills) or 'Not provided'}",
            f"Missing skills: {', '.join(missing_skills) or 'None listed'}",
            f"Top projects: {' '.join(projects) or 'Not provided'}",
            f"Job responsibilities: {'; '.join(responsibilities) or 'Not provided'}",
            f"Tone: {normalize_text(tone) or 'professional'}",
            f"Desired length: {normalize_text(cover_letter_length) or 'short'}",
        ]
    )
    return system_prompt, user_prompt


def is_valid_llm_cover_letter(text: str, length: str) -> bool:
    if len(text.strip()) < 80:
        return False

    lowered = text.lower()
    blocked_phrases = (
        "[your name]",
        "[company name]",
        "[date]",
        "[address]",
        "dear [",
        "sincerely,\n[",
        "lorem ipsum",
        "i don't have enough information",
        "i do not have enough information",
        "mock llm response",
    )
    if any(phrase in lowered for phrase in blocked_phrases):
        return False

    max_words = 360 if normalize_text(length).lower() == "medium" else 260
    return count_words(text) <= max_words


def _with_generation_metadata(
    result: dict,
    source: str,
    provider: str,
    used_fallback: bool,
) -> dict:
    return {
        **result,
        "generation_source": source,
        "llm_provider": provider,
        "used_fallback": used_fallback,
    }


def _llm_max_tokens_for_length(length: str) -> int:
    return 750 if normalize_text(length).lower() == "medium" else 550


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [normalize_text(item) for item in value if normalize_text(item)]


def normalize_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def extract_candidate_name(resume_profile: dict) -> str:
    return normalize_text(resume_profile.get("name")) or "Candidate"


def extract_education(resume_profile: dict) -> str:
    return summarize_education(resume_profile.get("education", []))


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


def summarize_education(education) -> str:
    return select_best_education(education)


def extract_top_skills(resume_profile: dict, match_result: dict, limit: int = 5) -> list:
    matched_skills = match_result.get("matched_skills", [])
    resume_skills = resume_profile.get("skills", [])
    skills: list[str] = []

    for skill in matched_skills + resume_skills:
        normalized_skill = format_skill_display(skill)
        if normalized_skill and normalized_skill.lower() not in [item.lower() for item in skills]:
            skills.append(normalized_skill)

    return skills[:limit]


def extract_project_highlights(resume_profile: dict, limit: int = 2) -> list:
    projects = resume_profile.get("projects", []) or []
    highlights: list[str] = []

    for index, project in enumerate(projects[:limit]):
        project_text = format_project_for_answer(project, index)

        if project_text:
            highlights.append(project_text)

    return highlights[:limit]


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


def extract_experience_highlights(resume_profile: dict, limit: int = 2) -> list:
    experience = resume_profile.get("experience", []) or []
    highlights: list[str] = []

    for item in experience:
        if isinstance(item, str):
            text = normalize_text(item)
        elif isinstance(item, dict):
            text = _experience_dict_to_text(item)
        else:
            text = normalize_text(item)
        if text:
            highlights.append(text)

    return highlights[:limit]


def build_subject_line(job_profile: dict) -> str:
    role_title = _safe_role_title(job_profile.get("role_title"), "the internship role")
    company_name = normalize_text(job_profile.get("company_name"))
    if company_name:
        return f"Application for {role_title} at {company_name}"
    return f"Application for {role_title}"


def build_key_points(resume_profile: dict, job_profile: dict, match_result: dict) -> list:
    key_points = []
    education = extract_education(resume_profile)
    role_title = _safe_role_title(job_profile.get("role_title"), "the internship role")
    company_name = normalize_text(job_profile.get("company_name"))
    skills = extract_top_skills(resume_profile, match_result)
    projects = extract_project_highlights(resume_profile)
    experience = extract_experience_highlights(resume_profile)

    key_points.append(f"Target role: {role_title}")
    if company_name:
        key_points.append(f"Company: {company_name}")
    if education:
        key_points.append(f"Education: {education}")
    if skills:
        key_points.append("Matched skills: " + ", ".join(skills))
    for project in projects:
        key_points.append(f"Project: {_project_name_from_summary(project)}")
    for item in experience:
        key_points.append(f"Experience: {item}")

    return key_points


def apply_tone(text: str, tone: str) -> str:
    normalized_tone = normalize_text(tone).lower()

    if normalized_tone == "confident":
        return text.replace("I would welcome", "I am ready for").replace("I believe", "I know")
    if normalized_tone == "friendly":
        return text.replace("I am interested", "I am genuinely excited").replace("Thank you for your consideration.", "Thank you for considering my application.")
    if normalized_tone == "concise":
        return text.replace("I would welcome the opportunity to", "I can").replace("I am interested in", "I want")
    return text


def count_words(text: str) -> int:
    return len(text.split())


def _build_cover_letter(
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
    skill_gap_result: dict,
    length: str,
) -> str:
    role_title = _safe_role_title(job_profile.get("role_title"), "the internship role")
    company_name = normalize_text(job_profile.get("company_name"))
    education = extract_education(resume_profile)
    skills = extract_top_skills(resume_profile, match_result, limit=4)
    projects = extract_project_highlights(resume_profile, limit=2)
    experience = extract_experience_highlights(resume_profile, limit=2)
    learning_focus = _learning_focus(match_result, skill_gap_result)
    role_phrase = _role_phrase(role_title, company_name)

    paragraphs = [
        "Dear Hiring Team,",
        _opening_paragraph(role_title, company_name, role_phrase, education),
        _evidence_paragraph(skills, projects, experience),
        _growth_paragraph(learning_focus, role_phrase),
    ]

    if normalize_text(length).lower() == "medium":
        paragraphs.insert(
            3,
            _medium_detail_paragraph(job_profile, match_result),
        )

    paragraphs.append("Thank you for your consideration.\n\nSincerely,\n" + extract_candidate_name(resume_profile))
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _opening_paragraph(role_title: str, company_name: str, role_phrase: str, education: str) -> str:
    if role_title.lower() in {"the internship role", "this internship"}:
        first_sentence = "I am writing to apply for this internship opportunity."
    elif role_title.lower() == "intern":
        first_sentence = "I am writing to apply for the internship role."
    elif company_name:
        first_sentence = f"I am writing to apply for the {role_title} role at {company_name}."
    else:
        first_sentence = f"I am writing to apply for the {role_title} role."

    if education and education != "my academic background":
        return (
            f"{first_sentence} My {education} background gives me a strong foundation for approaching "
            "internship work with curiosity, structure, and consistency."
        )
    return f"{first_sentence} My current project work and learning path align with the responsibilities of this opportunity."


def _evidence_paragraph(skills: list, projects: list, experience: list) -> str:
    sentences = []
    if skills:
        sentences.append("My strongest matched skills include " + ", ".join(skills) + ".")
    if projects:
        if len(projects) == 1:
            sentences.append(projects[0])
        else:
            sentences.append(f"{projects[0]} {projects[1]}")
    if experience:
        sentences.append("I also bring experience from " + "; ".join(experience) + ".")
    if not sentences:
        sentences.append("I am building practical experience through focused projects and consistent learning.")
    return " ".join(sentences)


def _growth_paragraph(learning_focus: list, role_phrase: str) -> str:
    if learning_focus:
        return (
            "I am also actively strengthening "
            + ", ".join(learning_focus)
            + f" so I can close the remaining gaps and contribute responsibly in {role_phrase}. "
            "I would approach new tasks by applying what I already know, asking focused questions, and documenting what I learn."
        )
    return (
        f"I would welcome the opportunity to contribute to {role_phrase} while continuing to learn from real team work. "
        "I would bring consistency, curiosity, and care to the work assigned to me."
    )


def _medium_detail_paragraph(job_profile: dict, match_result: dict) -> str:
    responsibilities = job_profile.get("responsibilities", []) or []
    match_level = normalize_text(match_result.get("match_level"))

    if responsibilities:
        return (
            "The responsibilities that stand out to me include "
            + "; ".join(normalize_text(item) for item in responsibilities[:2])
            + ". I would approach these responsibilities by applying my current strengths, asking thoughtful questions when learning new tools, "
            "and turning feedback into cleaner work. This would help me contribute from the beginning, communicate progress clearly, and continue growing in the areas highlighted by the match and skill-gap results."
        )
    if match_level:
        return f"The current match result indicates a {match_level}, and I see this as a useful signal to focus my preparation."
    return ""


def _build_opening_summary(resume_profile: dict, job_profile: dict) -> str:
    role_title = _safe_role_title(job_profile.get("role_title"), "the internship role")
    education = extract_education(resume_profile)
    if education and education != "my academic background":
        return f"Candidate pursuing {education} and applying for {role_title}."
    return f"Candidate applying for {role_title}."


def _learning_focus(match_result: dict, skill_gap_result: dict) -> list:
    priority_skills = skill_gap_result.get("priority_skills", []) or []
    if priority_skills:
        return [format_skill_display(item.get("skill")) for item in priority_skills[:3] if item.get("skill")]
    return [format_skill_display(skill) for skill in match_result.get("missing_skills", [])[:3]]


def _fit_length(text: str, length: str) -> str:
    target_max = 260 if normalize_text(length).lower() == "medium" else 180
    if count_words(text) <= target_max:
        return text

    words = text.split()
    trimmed = " ".join(words[:target_max]).rstrip(".,;:")
    sentence_end = max(trimmed.rfind("."), trimmed.rfind("!"), trimmed.rfind("?"))
    if sentence_end > len(trimmed) * 0.65:
        return trimmed[: sentence_end + 1]
    return trimmed + "."


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
    cleaned = re.sub(r"[ \t]+", " ", text).strip()
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


def _experience_dict_to_text(experience: dict) -> str:
    title = normalize_text(experience.get("title") or experience.get("role"))
    company = normalize_text(experience.get("company") or experience.get("organization"))
    description = normalize_text(experience.get("description"))

    if title and company and description:
        return f"{title} at {company}: {description}"
    if title and company:
        return f"{title} at {company}"
    return title or company or description
