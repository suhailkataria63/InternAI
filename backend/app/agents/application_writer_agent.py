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
        normalized_skill = normalize_text(skill)
        if normalized_skill and normalized_skill.lower() not in [item.lower() for item in skills]:
            skills.append(normalized_skill)

    return skills[:limit]


def extract_project_highlights(resume_profile: dict, limit: int = 2) -> list:
    projects = resume_profile.get("projects", []) or []
    highlights = []

    for project in projects:
        if isinstance(project, str):
            project_text = normalize_text(project)
        elif isinstance(project, dict):
            project_text = _project_dict_to_text(project)
        else:
            project_text = _project_object_to_text(project)

        if project_text:
            highlights.append(project_text)

    return highlights[:limit]


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
    education = _first_item(resume_profile.get("education", []))
    role_title = normalize_text(job_profile.get("role_title")) or "the internship role"
    top_skills = extract_top_skills(resume_profile, match_result)
    projects = extract_project_highlights(resume_profile)
    missing_skills = match_result.get("missing_skills", [])

    if education:
        key_points.append(f"Education: {education}")
    key_points.append(f"Target role: {role_title}")
    if top_skills:
        key_points.append("Matched skills: " + ", ".join(top_skills))
    for project in projects:
        key_points.append(f"Project: {project}")
    if missing_skills:
        key_points.append("Learning focus: " + ", ".join(missing_skills[:3]))
    if skill_gap_result.get("overall_advice"):
        key_points.append("Skill gap advice: " + normalize_text(skill_gap_result["overall_advice"]))

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
    role_title = normalize_text(job_profile.get("role_title")) or "this internship"
    company_name = normalize_text(job_profile.get("company_name"))
    education = _first_item(resume_profile.get("education", []))
    skills = extract_top_skills(resume_profile, match_result, limit=4)
    projects = extract_project_highlights(resume_profile)
    learning_focus = _learning_focus(match_result, skill_gap_result)

    role_phrase = f"the {role_title} role"
    if company_name:
        role_phrase += f" at {company_name}"

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
    if education:
        return f"I am a candidate with education in {education}, applying for {role_phrase}."
    return f"I am applying for {role_phrase}."


def _skills_sentence(skills: list) -> str:
    if not skills:
        return "My current profile shows a foundation I am continuing to strengthen."
    return "My strongest matched skills include " + ", ".join(skills) + "."


def _projects_sentence(projects: list) -> str:
    if not projects:
        return "I am also working on building clearer project evidence for my resume."
    if len(projects) == 1:
        return f"One relevant project is {projects[0]}."
    return f"Relevant projects include {projects[0]} and {projects[1]}."


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
        return [normalize_text(item.get("skill")) for item in priority_skills[:3] if item.get("skill")]
    return [normalize_text(skill) for skill in match_result.get("missing_skills", [])[:3]]


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


def _project_dict_to_text(project: dict) -> str:
    name = normalize_text(project.get("name"))
    description = normalize_text(project.get("description"))
    technologies = project.get("technologies", [])
    technology_text = ", ".join(normalize_text(item) for item in technologies if item)

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
