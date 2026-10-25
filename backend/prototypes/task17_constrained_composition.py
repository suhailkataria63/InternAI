"""Offline prototype: lock candidate facts and select approved phrasing.

This deliberately stays outside the production writer path. The model response
contains enum choices only; local composition supplies all candidate facts and
the selected phrase text.
"""

from __future__ import annotations

import json
from typing import Any


CHOICES = {
    "opening_id": {"question_first", "project_first", "role_direct", "education_first"},
    "relevance_id": {"api_alignment", "data_tool_alignment", "skill_alignment"},
    "closing_id": {"brief", "warm"},
}
DEFAULT_DECISION = {
    "opening_id": "question_first",
    "relevance_id": "api_alignment",
    "closing_id": "brief",
}

APPROVED_PHRASES = {
    "openings": {
        "question_first": "I am applying for the {role} role at {company}.",
        "project_first": "I am pleased to apply for the {role} role at {company}.",
        "role_direct": "I am applying to {company} for the {role} position.",
        "education_first": "As a {education}, I am applying for the {role} role at {company}.",
    },
    "relevance": {
        "api_alignment": "That work is relevant to the role's backend API focus.",
        "data_tool_alignment": "That work also relates to the role's data-driven tools.",
        "skill_alignment": "Those skills are relevant to the technologies used in this project.",
    },
    "closings": {
        "brief": "Thank you for considering my application.",
        "warm": "Thank you for your consideration.",
    },
}


def classify_question(question: str) -> str:
    """Route to a question-specific, evidence-safe local composition."""
    lowered = (question or "").casefold()
    if any(term in lowered for term in ("challenge", "result", "impact", "outcome", "overcame")):
        return "challenge_result"
    if any(term in lowered for term in ("skill", "technology", "technical strength")):
        return "skills"
    if any(term in lowered for term in ("goal", "career aim", "aspiration")):
        return "stated_goal"
    if any(term in lowered for term in ("why", "interested", "motivat", "reason for applying")):
        return "role_alignment"
    return "project_example"


def build_choice_prompt(writer: str, question: str, anchors: dict, job_context: dict) -> tuple[str, str]:
    """Ask for style/structure selection without exposing implementation facts."""
    system = (
        "Choose only approved IDs for the question and role. Return strict JSON with opening_id, relevance_id, closing_id. "
        "Do not write prose, candidate facts, achievements, activities, or commitments."
    )
    projects = [
        {"id": item.get("id"), "name": item.get("project") or item.get("name")}
        for item in anchors.get("project_work", [])
        if isinstance(item, dict)
    ]
    focus = classify_question(question)
    payload = {
        "task": writer,
        "question": question,
        "focus": focus,
        "job_context": {
            "role_title": job_context.get("role_title", ""),
            "company_name": job_context.get("company_name", ""),
            "responsibilities": job_context.get("responsibilities", []),
        },
        "project_choices": projects,
        "choices": {
            "opening_id": {"question_first": "answer first", "project_first": "project first", "role_direct": "role first", "education_first": "education first"},
            "relevance_id": APPROVED_PHRASES["relevance"],
            "closing_id": {"brief": "brief thanks", "warm": "polite thanks"},
        },
    }
    return system, json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def parse_choice_response(raw: str) -> tuple[dict[str, str], bool]:
    """Return safe defaults if the mock/provider response adds arbitrary text."""
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return dict(DEFAULT_DECISION), False
    if not isinstance(value, dict) or set(value) != set(CHOICES):
        return dict(DEFAULT_DECISION), False
    if any(value.get(key) not in allowed for key, allowed in CHOICES.items()):
        return dict(DEFAULT_DECISION), False
    return {key: value[key] for key in CHOICES}, True


def _locked_project_sentence(anchors: dict, opening_id: str = "question_first") -> str:
    projects = anchors.get("project_work", [])
    if not projects:
        return ""
    project = projects[0]
    name = str(project.get("project") or project.get("name") or "project").strip()
    fact = str(project.get("fact") or project.get("description") or "").strip().rstrip(".")
    if not fact:
        return ""
    if fact[:6].casefold() == "built ":
        if opening_id == "project_first":
            return f"I built {fact[6:]} in my {name} project."
        return f"In my {name} project, I {fact}."
    return f"In my {name} project, {fact}."


def compose_locked_writing(
    writer: str,
    anchors: dict,
    job_context: dict,
    question: str,
    decision: dict[str, str] | None = None,
) -> str:
    """Render question-aware writing from approved phrases and locked facts."""
    selected = dict(DEFAULT_DECISION)
    if isinstance(decision, dict) and set(decision) == set(CHOICES):
        if all(decision.get(key) in allowed for key, allowed in CHOICES.items()):
            selected = decision

    project = (anchors.get("project_work") or [{}])[0]
    project_name = str(project.get("project") or project.get("name") or "this project")
    fact_sentence = _locked_project_sentence(anchors)
    company = str(job_context.get("company_name") or "the organization")
    role = str(job_context.get("role_title") or "the role")
    focus = classify_question(question)
    if writer == "application_answer":
        fact_sentence = _locked_project_sentence(anchors, selected["opening_id"])
        if focus == "skills":
            skills = anchors.get("listed_skills", [])
            if not skills:
                return "I do not have a listed skill in this profile that answers the question."
            skill_sentence = f"Relevant skills I have listed include {', '.join(skills)}."
            skill_transition = (
                APPROVED_PHRASES["relevance"]["skill_alignment"]
                if fact_sentence and selected["relevance_id"] == "skill_alignment"
                else ""
            )
            return " ".join(part for part in (skill_sentence, fact_sentence, skill_transition) if part)
        if focus == "stated_goal":
            goals = anchors.get("stated_goals", [])
            if not goals:
                return "I have not stated a specific career goal for this answer."
            goal = str(goals[0]).strip()
            end = "" if goal.endswith((".", "?", "!")) else "."
            return f"One goal I have stated is: “{goal}”{end}"
        if focus == "challenge_result":
            if not fact_sentence:
                return "I do not have a project description that answers this question about challenges or results."
            return f"I can describe the project: {fact_sentence} The information available to me does not specify a particular challenge or outcome."
        if not fact_sentence:
            return "I do not have a project description that answers this question."
        if focus == "role_alignment":
            role_line = APPROVED_PHRASES["relevance"][selected["relevance_id"]]
            return " ".join((fact_sentence, role_line))
        role_relevance = APPROVED_PHRASES["relevance"][selected["relevance_id"]]
        return " ".join((fact_sentence, role_relevance))

    if writer != "cover_letter":
        raise ValueError(f"Unsupported writer: {writer}")
    education = str(anchors.get("education") or "").strip()
    opening_id = selected["opening_id"]
    if opening_id == "education_first" and education and ("candidate" in education.casefold() or ", expected " in education):
        year = ""
        education_text = education
        if ", expected " in education:
            education_text, year = education.rsplit(", expected ", 1)
        if year.isdigit():
            intro = f"I am a {education_text} expecting to graduate in {year}, and I am applying for the {role} role at {company}."
        else:
            intro = f"I am applying for the {role} role at {company}."
    else:
        intro_template = APPROVED_PHRASES["openings"].get(opening_id, APPROVED_PHRASES["openings"]["question_first"])
        if opening_id == "education_first":
            intro_template = APPROVED_PHRASES["openings"]["question_first"]
        intro = intro_template.format(role=role, company=company, education=education, project=project_name)
    body_parts = [fact_sentence] if fact_sentence else []
    if fact_sentence:
        body_parts.append(APPROVED_PHRASES["relevance"][selected["relevance_id"]])
    goals = anchors.get("stated_goals", [])
    if goals:
        goal = str(goals[0]).strip()
        end = "" if goal.endswith((".", "?", "!")) else "."
        body_parts.append(f"One goal I have stated is: “{goal}”{end}")
    body = " ".join(body_parts)
    closing = APPROVED_PHRASES["closings"][selected["closing_id"]]
    signature = str(anchors.get("identity") or "")
    ending = f"Sincerely,\n{signature}" if signature else "Sincerely,"
    parts = ["Dear Hiring Team,", intro]
    if body:
        parts.append(body)
    parts.extend((closing, ending))
    return "\n\n".join(parts)


def mock_model_response(*, invalid: bool = False, decision: dict[str, str] | None = None) -> str:
    """Deterministic local fixture; this function never calls a provider."""
    response: dict[str, Any] = dict(DEFAULT_DECISION)
    if isinstance(decision, dict):
        response.update(decision)
    if invalid:
        response["project_detail"] = "I implemented CRUD operations, wrote unit tests, and deployed the app."
    return json.dumps(response)
