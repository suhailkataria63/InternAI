import re


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

    return {
        "cover_letter": cover_letter,
        "subject_line": subject_line,
        "opening_summary": _build_opening_summary(resume_profile, job_profile),
        "key_points_used": key_points,
        "tone": tone,
        "word_count": count_words(cover_letter),
    }


def normalize_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def extract_candidate_name(resume_profile: dict) -> str:
    return normalize_text(resume_profile.get("name")) or "Candidate"


def extract_education(resume_profile: dict) -> str:
    education = resume_profile.get("education", [])
    if not education:
        return ""
    return normalize_text(education[0])


def extract_top_skills(resume_profile: dict, match_result: dict, limit: int = 5) -> list:
    matched_skills = match_result.get("matched_skills", [])
    resume_skills = resume_profile.get("skills", [])
    skills: list[str] = []

    for skill in matched_skills + resume_skills:
        normalized_skill = normalize_text(skill)
        if normalized_skill and normalized_skill.lower() not in [item.lower() for item in skills]:
            skills.append(normalized_skill)

    return skills[:limit]


def extract_project_highlights(resume_profile: dict, limit: int = 2) -> list:
    projects = resume_profile.get("projects", []) or []
    highlights: list[str] = []

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
    role_title = normalize_text(job_profile.get("role_title")) or "Internship"
    company_name = normalize_text(job_profile.get("company_name"))
    if company_name:
        return f"Application for {role_title} at {company_name}"
    return f"Application for {role_title}"


def build_key_points(resume_profile: dict, job_profile: dict, match_result: dict) -> list:
    key_points = []
    education = extract_education(resume_profile)
    role_title = normalize_text(job_profile.get("role_title")) or "the internship role"
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
        key_points.append(f"Project: {project}")
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
    role_title = normalize_text(job_profile.get("role_title")) or "the internship role"
    company_name = normalize_text(job_profile.get("company_name"))
    education = extract_education(resume_profile)
    skills = extract_top_skills(resume_profile, match_result, limit=4)
    projects = extract_project_highlights(resume_profile, limit=2)
    experience = extract_experience_highlights(resume_profile, limit=2)
    learning_focus = _learning_focus(match_result, skill_gap_result)
    role_phrase = f"the {role_title} role"
    if company_name:
        role_phrase += f" at {company_name}"

    paragraphs = [
        "Dear Hiring Team,",
        _opening_paragraph(role_phrase, education),
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


def _opening_paragraph(role_phrase: str, education: str) -> str:
    if education:
        return (
            f"I am interested in {role_phrase}. My education in {education} gives me a strong foundation "
            "for approaching internship work with curiosity, structure, and consistency."
        )
    return (
        f"I am interested in {role_phrase}. My current project work and learning path align with the responsibilities "
        "of this opportunity."
    )


def _evidence_paragraph(skills: list, projects: list, experience: list) -> str:
    sentences = []
    if skills:
        sentences.append("My strongest matched skills include " + ", ".join(skills) + ".")
    if projects:
        if len(projects) == 1:
            sentences.append(f"One relevant project is {projects[0]}.")
        else:
            sentences.append(f"Relevant projects include {projects[0]} and {projects[1]}.")
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
    role_title = normalize_text(job_profile.get("role_title")) or "the internship role"
    education = extract_education(resume_profile)
    if education:
        return f"Candidate with education in {education} applying for {role_title}."
    return f"Candidate applying for {role_title}."


def _learning_focus(match_result: dict, skill_gap_result: dict) -> list:
    priority_skills = skill_gap_result.get("priority_skills", []) or []
    if priority_skills:
        return [normalize_text(item.get("skill")) for item in priority_skills[:3] if item.get("skill")]
    return [normalize_text(skill) for skill in match_result.get("missing_skills", [])[:3]]


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


def _experience_dict_to_text(experience: dict) -> str:
    title = normalize_text(experience.get("title") or experience.get("role"))
    company = normalize_text(experience.get("company") or experience.get("organization"))
    description = normalize_text(experience.get("description"))

    if title and company and description:
        return f"{title} at {company}: {description}"
    if title and company:
        return f"{title} at {company}"
    return title or company or description
