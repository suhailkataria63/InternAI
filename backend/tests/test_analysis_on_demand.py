from app.agents import application_writer_agent, cover_letter_agent
from app.services import orchestrator_service
from app.services.llm_service import LLMService


def test_full_analysis_prepares_results_without_writer_or_llm_calls(monkeypatch) -> None:
    resume_profile = {
        "name": "Synthetic Candidate",
        "skills": ["React"],
        "projects": [{"name": "Sample", "description": "A synthetic project."}],
        "education": [],
    }
    job_profile = {
        "role_title": "Software Engineering Intern",
        "company_name": "Example Labs",
        "required_skills": ["React", "AWS"],
        "preferred_skills": [],
    }
    match_result = {
        "match_score": 50,
        "match_level": "Developing Fit",
        "matched_skills": ["React"],
        "missing_skills": ["AWS"],
    }
    monkeypatch.setattr(orchestrator_service, "analyze_resume_text", lambda _text: resume_profile)
    monkeypatch.setattr(orchestrator_service, "analyze_jd_text", lambda _text: job_profile)
    monkeypatch.setattr(orchestrator_service, "calculate_match_score", lambda *_args: match_result)

    def unexpected_writer(*_args, **_kwargs):
        raise AssertionError("analysis must not invoke a writing agent")

    monkeypatch.setattr(application_writer_agent, "generate_application_answer", unexpected_writer)
    monkeypatch.setattr(cover_letter_agent, "generate_cover_letter", unexpected_writer)
    monkeypatch.setattr(
        LLMService,
        "generate_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("analysis must not call an LLM")
        ),
    )

    result = orchestrator_service.run_full_application_analysis(
        resume_text="Synthetic resume",
        job_description="Synthetic internship role",
    )

    assert result["application_answer"] == {}
    assert result["cover_letter"] == {}
    assert result["match_result"] is match_result
    assert result["skill_gap_result"]["learning_roadmap"]
    assert set(result["pipeline_summary"]["stage_timings_ms"]) == {
        "resume_analyzer",
        "jd_analyzer",
        "match_scorer",
        "skill_gap",
    }
