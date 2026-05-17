from app.agents.application_writer_agent import generate_application_answer
from app.agents.cover_letter_agent import generate_cover_letter
from app.agents.jd_analyzer import analyze_jd_text
from app.agents.match_scorer import calculate_match_score
from app.agents.resume_analyzer import analyze_resume_text
from app.agents.skill_gap_agent import analyze_skill_gap


class OrchestratorStepError(Exception):
    def __init__(self, step_name: str, original_error: Exception):
        self.step_name = step_name
        self.original_error = original_error
        super().__init__(f"{step_name} failed: {original_error}")


def run_full_application_analysis(
    resume_text: str,
    job_description: str,
    application_question: str = "Why should we hire you for this internship?",
    tone: str = "professional",
    word_limit: int = 180,
    cover_letter_length: str = "short",
) -> dict:
    """Run the full InternAI analysis pipeline using existing local agents."""
    if not resume_text or not resume_text.strip():
        raise ValueError("resume_text is required and cannot be empty.")
    if not job_description or not job_description.strip():
        raise ValueError("job_description is required and cannot be empty.")

    resume_profile = _run_step(
        "Resume Analyzer Agent",
        analyze_resume_text,
        resume_text,
    )
    job_profile = _run_step(
        "JD Analyzer Agent",
        analyze_jd_text,
        job_description,
    )
    match_result = _run_step(
        "Match Scoring Agent",
        calculate_match_score,
        resume_profile,
        job_profile,
    )
    skill_gap_result = _run_step(
        "Skill Gap Agent",
        analyze_skill_gap,
        resume_profile,
        job_profile,
        match_result,
    )
    application_answer = _run_step(
        "Application Writer Agent",
        generate_application_answer,
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        application_question,
        tone,
        word_limit,
    )
    cover_letter = _run_step(
        "Cover Letter Agent",
        generate_cover_letter,
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        tone,
        cover_letter_length,
    )

    return {
        "resume_profile": resume_profile,
        "job_profile": job_profile,
        "match_result": match_result,
        "skill_gap_result": skill_gap_result,
        "application_answer": application_answer,
        "cover_letter": cover_letter,
        "pipeline_summary": build_pipeline_summary(
            resume_profile,
            job_profile,
            match_result,
            skill_gap_result,
        ),
    }


def build_pipeline_summary(
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
    skill_gap_result: dict,
) -> dict:
    highest_priority_skills = [
        item.get("skill", "")
        for item in skill_gap_result.get("priority_skills", [])
        if item.get("priority") == "High"
    ]

    if not highest_priority_skills:
        highest_priority_skills = [
            item.get("skill", "")
            for item in skill_gap_result.get("priority_skills", [])[:3]
        ]

    return {
        "candidate_name": resume_profile.get("name", ""),
        "target_role": job_profile.get("role_title", ""),
        "company_name": job_profile.get("company_name", ""),
        "match_score": match_result.get("match_score", 0),
        "match_level": match_result.get("match_level", ""),
        "top_matched_skills": match_result.get("matched_skills", [])[:5],
        "top_missing_skills": match_result.get("missing_skills", [])[:5],
        "highest_priority_skills": highest_priority_skills[:5],
        "recommended_next_step": _recommended_next_step(match_result, skill_gap_result),
    }


def _run_step(step_name: str, function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except Exception as exc:
        raise OrchestratorStepError(step_name, exc) from exc


def _recommended_next_step(match_result: dict, skill_gap_result: dict) -> str:
    missing_skills = match_result.get("missing_skills", [])
    priority_skills = skill_gap_result.get("priority_skills", [])

    high_priority_skills = [
        item.get("skill", "")
        for item in priority_skills
        if item.get("priority") == "High"
    ]

    if high_priority_skills:
        return "Start with the highest priority missing skills: " + ", ".join(high_priority_skills[:3]) + "."
    if missing_skills:
        return "Add clearer evidence for missing skills: " + ", ".join(missing_skills[:3]) + "."
    return "Review the generated application answer and cover letter for company-specific details before submitting."
