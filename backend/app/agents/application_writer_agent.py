import json
import logging
import re
from time import perf_counter

from app.agents.writer_grounding import (
    diagnose_unsupported_skill_claims,
    build_writer_evidence_ledger,
    has_unsupported_numeric_claims,
    has_unsupported_project_detail_claims,
    is_learning_or_negated_skill_mention,
    normalized_claim_tokens,
    rank_projects,
    validation_diagnostic,
)
from app.services.llm_service import LLMService
from app.config import settings
from app.services.evaluation_report import EvaluationReportStore, prepare_evaluation_context
from app.utils import (
    education_for_writing,
    join_human_list,
    normalize_spaces,
    normalize_text_artifacts,
    normalize_unmatched_brackets,
    strip_project_dates,
)

logger = logging.getLogger(__name__)


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
- A missing skill may be mentioned only as an honest learning goal, never as existing expertise.
- Preserve an explicitly stated education status and do not infer one.
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
    evaluation_context: dict | None = None,
) -> dict:
    writer_started = perf_counter()
    rule_based_result = generate_rule_based_answer(
        resume_profile=resume_profile,
        job_profile=job_profile,
        match_result=match_result,
        skill_gap_result=skill_gap_result,
        application_question=application_question,
        tone=tone,
        word_limit=word_limit,
    )

    llm_service = LLMService()
    llm_status = llm_service.get_status()
    if llm_status.get("provider") == "mock":
        return _with_generation_metadata(
            rule_based_result,
            source="rule_based",
            provider=llm_status.get("provider", "mock"),
            used_fallback=True,
            generation_time_ms=round((perf_counter() - writer_started) * 1000, 3),
            fallback_reason="provider_mock",
        )

    evidence = build_application_evidence(
        resume_profile=resume_profile,
        job_profile=job_profile,
        match_result=match_result,
        question=application_question,
        tone=tone,
        word_limit=word_limit,
    )
    report_context = None
    if settings.groq_evaluation_mode and llm_status.get("provider") == "groq" and evaluation_context is not None:
        report_context = prepare_evaluation_context(evaluation_context)
    system_prompt, user_prompt = build_application_answer_prompt(
        resume_profile=resume_profile,
        job_profile=job_profile,
        match_result=match_result,
        skill_gap_result=skill_gap_result,
        question=application_question,
        tone=tone,
        word_limit=word_limit,
    )
    call_started = perf_counter()
    try:
        llm_result = llm_service.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.25,
            max_tokens=max(250, min(350, int(word_limit * 2.2))),
            **({"evaluation_context": report_context} if report_context is not None else {}),
        )
    except Exception:
        return _with_generation_metadata(
            rule_based_result,
            source="rule_based",
            provider=llm_status.get("provider", "mock"),
            used_fallback=True,
            generation_time_ms=round((perf_counter() - call_started) * 1000, 3),
            fallback_reason="provider_exception",
        )
    llm_answer = clean_generated_text(_extract_llm_json_field(llm_result.get("text"), "answer"))
    validation_issue = _llm_answer_validation_issue(llm_answer, word_limit, evidence)
    validation_diagnostics = (
        diagnose_llm_answer_validation(llm_answer, word_limit, evidence)
        if validation_issue and not llm_result.get("used_fallback")
        else []
    )
    _log_validation_diagnostics(validation_diagnostics)

    if report_context is not None:
        selected_text = llm_answer if validation_issue and not llm_result.get("used_fallback") else rule_based_result["generated_answer"] if llm_result.get("used_fallback") else llm_answer
        EvaluationReportStore().append_writer_result(
            report_context,
            writer="application_answer",
            provider=str(llm_result.get("provider") or llm_status.get("provider") or "groq"),
            model=str(llm_result.get("model") or llm_service.model),
            latency_ms=llm_result.get("generation_time_ms"),
            generation_source="rule_based" if llm_result.get("used_fallback") or validation_issue else "groq",
            fallback_reason=(llm_result.get("error") or {}).get("fallback_reason") if llm_result.get("used_fallback") else f"validation_{validation_issue}" if validation_issue else None,
            rejected_rule_ids=[item["rejected_rule_id"] for item in validation_diagnostics],
            synthetic_text=selected_text,
            accepted=not bool(llm_result.get("used_fallback") or validation_issue),
        )

    if llm_result.get("used_fallback") or validation_issue:
        return _with_generation_metadata(
            rule_based_result,
            source="rule_based",
            provider=llm_result.get("provider", llm_status.get("provider", "mock")),
            used_fallback=True,
            generation_time_ms=llm_result.get("generation_time_ms") or round((perf_counter() - call_started) * 1000, 3),
            fallback_reason=(
                (llm_result.get("error") or {}).get("fallback_reason", "llm_provider_fallback")
                if llm_result.get("used_fallback")
                else f"validation_{validation_issue}"
            ),
            llm_error=_safe_llm_error_metadata(llm_result),
        )

    return {
        **rule_based_result,
        "generated_answer": llm_answer,
        "word_count": count_words(llm_answer),
        "generation_source": "llm",
        "llm_provider": llm_result.get("provider", llm_status.get("provider", "")),
        "used_fallback": False,
        "generation_time_ms": llm_result.get("generation_time_ms"),
    }


def generate_rule_based_answer(
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
        application_question=application_question,
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


def build_application_answer_prompt(
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
    skill_gap_result: dict,
    question: str,
    tone: str,
    word_limit: int,
) -> tuple[str, str]:
    evidence = build_application_evidence(
        resume_profile=resume_profile,
        job_profile=job_profile,
        match_result=match_result,
        question=question,
        tone=tone,
        word_limit=word_limit,
    )

    system_prompt = (
        "Write a natural, question-focused internship answer. Use only candidate_factual_anchors for candidate facts and preserve explicit education status as stated. "
        "project_work supports only its description and listed project technologies; listed_skills means only those skills are listed, not hands-on use; stated_goals supports only explicit goals. "
        "Use job_context only to select relevant anchors; JD content is not candidate evidence. Paraphrase naturally without adding implementation details or outcomes. "
        "Do not invent personal activities, plans, or qualities absent from the anchors. With no stated_goals, invent no coursework or future projects. Answer the question and omit unsupported claims. "
        "Meet tone and word_limit. Return strict JSON only with exactly one key: {\"answer\":\"...\"}."
    )
    ledger = build_writer_evidence_ledger(evidence, resume_profile)
    user_prompt = json.dumps(
        {"evidence": {
            "task": evidence["task"],
            "question": evidence["question"],
            "question_type": evidence["question_type"],
            "tone": evidence["tone"],
            "word_limit": evidence["word_limit"],
            "candidate_factual_anchors": ledger["candidate_factual_anchors"],
            "job_context": ledger["job_context"],
        }},
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return system_prompt, user_prompt


def is_valid_llm_answer(answer: str, word_limit: int, evidence: dict | None = None) -> bool:
    return _llm_answer_validation_issue(answer, word_limit, evidence) is None


def _llm_answer_validation_issue(answer: str, word_limit: int, evidence: dict | None = None) -> str | None:
    if len(answer) < 30:
        return "empty_or_too_short"
    lowered = answer.lower()
    blocked_phrases = (
        "[your name]",
        "lorem ipsum",
        "i don't have enough information",
        "i do not have enough information",
        "mock llm response",
        "<think",
        "</think>",
        "reasoning:",
        "analysis:",
    )
    if any(phrase in lowered for phrase in blocked_phrases):
        return "blocked_or_malformed_text"
    if evidence and _has_unsupported_claims(answer, evidence):
        return "unsupported_claims"

    if word_limit > 0:
        allowed_words = max(word_limit + 30, int(word_limit * 1.25))
        if count_words(answer) > allowed_words:
            return "word_limit_exceeded"
    return None


def diagnose_llm_answer_validation(answer: str, word_limit: int, evidence: dict | None = None) -> list[dict]:
    """Explain a rejected answer without exposing its text or candidate evidence."""
    issue = _llm_answer_validation_issue(answer, word_limit, evidence)
    diagnostics = []
    if issue == "empty_or_too_short":
        diagnostics.append(validation_diagnostic("application_answer", "minimum_output_length"))
    if issue == "blocked_or_malformed_text":
        diagnostics.append(validation_diagnostic("application_answer", "blocked_or_malformed_text"))
    if issue == "word_limit_exceeded":
        diagnostics.append(validation_diagnostic("application_answer", "output_word_limit"))
    if evidence:
        diagnostics.extend(_diagnose_unsupported_claims(answer, evidence, "application_answer"))
    if issue is not None and not diagnostics:
        diagnostics.append(validation_diagnostic("application_answer", "unsupported_claim_unclassified"))
    return _unique_diagnostics(diagnostics)


def _diagnose_unsupported_claims(text: str, evidence: dict, writer: str) -> list[dict]:
    rule_ids = diagnose_unsupported_skill_claims(text, evidence)
    if has_unsupported_numeric_claims(text, evidence):
        rule_ids.append("unsupported_numeric_claim")
    lowered = normalize_text(text).lower()
    candidate_evidence_text = _candidate_evidence_text(evidence)
    if _has_unverified_claim_markers(lowered, candidate_evidence_text):
        rule_ids.append("unsupported_claim_marker")
    if _has_unsupported_project_claims(text, evidence):
        rule_ids.append("project_claim_low_evidence_overlap")
    if has_unsupported_project_detail_claims(text, evidence):
        rule_ids.append("unsupported_project_detail_claim")

    allowed_skills = {
        normalize_text(skill).lower()
        for skill in evidence.get("matched_skills", [])
        if normalize_text(skill)
    }
    for project in evidence.get("projects", []):
        for technology in project.get("technologies", []):
            allowed_skills.add(normalize_text(technology).lower())
    known_terms = {
        "docker", "kubernetes", "aws", "tensorflow", "pytorch", "fastapi", "django", "flask",
        "react", "next.js", "node.js", "sql", "langchain", "rag", "python",
    }
    listed_skills = {str(skill).lower() for skill in evidence.get("listed_skills", []) or []}
    missing_skills = {str(skill).lower() for skill in evidence.get("unsupported_skills", []) or []}
    if any(
        _term_in_text(term, lowered) and not is_learning_or_negated_skill_mention(lowered, term)
        for term in known_terms - allowed_skills - listed_skills - missing_skills
    ):
        rule_ids.append("unverified_known_skill")

    project_names = {
        normalize_text(project.get("name")).lower()
        for project in evidence.get("projects", [])
        if normalize_text(project.get("name"))
    }
    project_like_claims = re.findall(
        r"\b([A-Z][A-Za-z0-9/& -]+(?:Project|System|Platform|Dashboard|Application|App|Chatbot|Tool|Model))\b",
        text,
    )
    if any(
        not any(normalize_text(claim).lower() in name or name in normalize_text(claim).lower() for name in project_names)
        for claim in project_like_claims
    ):
        rule_ids.append("unrecognized_named_project")
    responsibilities = [
        normalize_text(item)
        for item in (evidence.get("job_context", {}) or {}).get("responsibilities", [])
        if normalize_text(item)
    ]
    if _has_unsupported_responsibility_claims(text, responsibilities, candidate_evidence_text):
        rule_ids.append("unsupported_job_responsibility_claim")
    return [validation_diagnostic(writer, rule_id) for rule_id in dict.fromkeys(rule_ids)]


def _unique_diagnostics(diagnostics: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for item in diagnostics:
        key = (item["writer"], item["rejected_rule_id"])
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _old_diagnose_unsupported_claims(text: str, evidence: dict, writer: str) -> list[dict]:
    skill_rules = diagnose_unsupported_skill_claims(text, evidence)
    if skill_rules:
        return [validation_diagnostic(writer, skill_rules[0])]
    if has_unsupported_numeric_claims(text, evidence):
        return [validation_diagnostic(writer, "unsupported_numeric_claim")]

    lowered = normalize_text(text).lower()
    candidate_evidence_text = _candidate_evidence_text(evidence)
    if _has_unverified_claim_markers(lowered, candidate_evidence_text):
        return [validation_diagnostic(writer, "unsupported_claim_marker")]
    if _has_unsupported_project_claims(text, evidence):
        return [validation_diagnostic(writer, "project_claim_low_evidence_overlap")]

    allowed_skills = {
        normalize_text(skill).lower()
        for skill in evidence.get("matched_skills", [])
        if normalize_text(skill)
    }
    for project in evidence.get("projects", []):
        for technology in project.get("technologies", []):
            allowed_skills.add(normalize_text(technology).lower())
    known_terms = {
        "docker", "kubernetes", "aws", "tensorflow", "pytorch", "fastapi", "django", "flask",
        "react", "next.js", "node.js", "sql", "langchain", "rag", "python",
    }
    listed_skills = {str(skill).lower() for skill in evidence.get("listed_skills", []) or []}
    if any(
        _term_in_text(term, lowered) and not is_learning_or_negated_skill_mention(lowered, term)
        for term in known_terms - allowed_skills - listed_skills
    ):
        return [validation_diagnostic(writer, "unverified_known_skill")]

    project_names = {
        normalize_text(project.get("name")).lower()
        for project in evidence.get("projects", [])
        if normalize_text(project.get("name"))
    }
    project_like_claims = re.findall(
        r"\b([A-Z][A-Za-z0-9/& -]+(?:Project|System|Platform|Dashboard|Application|App|Chatbot|Tool|Model))\b",
        text,
    )
    if any(
        not any(normalize_text(claim).lower() in name or name in normalize_text(claim).lower() for name in project_names)
        for claim in project_like_claims
    ):
        return [validation_diagnostic(writer, "unrecognized_named_project")]

    responsibilities = [
        normalize_text(item)
        for item in (evidence.get("job_context", {}) or {}).get("responsibilities", [])
        if normalize_text(item)
    ]
    if _has_unsupported_responsibility_claims(text, responsibilities, candidate_evidence_text):
        return [validation_diagnostic(writer, "unsupported_job_responsibility_claim")]
    return [validation_diagnostic(writer, "unsupported_claim_unclassified")]


def _log_validation_diagnostics(diagnostics: list[dict]) -> None:
    for diagnostic in diagnostics:
        logger.warning(
            "writer_validation_rejected writer=%s rule_id=%s evidence_category=%s explanation=%s",
            diagnostic["writer"],
            diagnostic["rejected_rule_id"],
            diagnostic["evidence_category"],
            diagnostic["safe_explanation"],
        )


def build_application_evidence(
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
    question: str,
    tone: str,
    word_limit: int,
) -> dict:
    grounding = _build_grounding_evidence(
        resume_profile=resume_profile,
        match_result=match_result,
        question=question,
        job_profile=job_profile,
    )
    return {
        "task": "application_answer",
        "question": normalize_text(question),
        "question_type": detect_question_type(question),
        "tone": normalize_text(tone) or "professional",
        "word_limit": word_limit,
        "candidate": {
            "name": extract_candidate_name(resume_profile),
            "education": summarize_education(resume_profile.get("education", [])),
            "experience": grounding["experience"],
        },
        "job_context": {
            "role_title": _safe_role_title(job_profile.get("role_title"), "this internship"),
            "company_name": normalize_text(job_profile.get("company_name")),
            "responsibilities": [
                normalize_text(item)
                for item in (job_profile.get("responsibilities", []) or [])[:3]
                if normalize_text(item)
            ],
            "missing_requirements": grounding["missing_requirements"],
            "related_requirements": grounding["related_skills"],
        },
        "matched_skills": _question_relevant_skills(
            extract_top_skills(resume_profile, match_result, limit=8),
            question,
            job_profile,
            limit=6,
        ),
        "projects": _verified_project_evidence(resume_profile, question, job_profile, limit=2),
        "demonstrated_experience": grounding["demonstrated_experience"],
        "listed_skills": grounding["listed_skills"],
        "transferable_experience": grounding["transferable_experience"],
        "missing_requirements": grounding["missing_requirements"],
        "low_evidence_guidance": grounding["low_evidence_guidance"],
        "unsupported_skills": [
            format_skill_display(skill)
            for skill in (match_result.get("missing_skills", []) or [])
            if normalize_text(skill)
        ],
    }


def _build_grounding_evidence(
    resume_profile: dict,
    match_result: dict,
    question: str = "",
    job_profile: dict | None = None,
) -> dict:
    evidence_summary = match_result.get("evidence_summary", {}) if isinstance(match_result, dict) else {}
    skill_evidence = (
        evidence_summary.get("required_skills", [])
        + evidence_summary.get("preferred_skills", [])
    )
    related_skills = [
        format_skill_display(item.get("requirement"))
        for item in skill_evidence
        if item.get("status") == "related" and normalize_text(item.get("requirement"))
    ]
    missing = [
        format_skill_display(item.get("requirement"))
        for item in skill_evidence
        if item.get("status") == "missing" and normalize_text(item.get("requirement"))
    ] or [
        format_skill_display(skill)
        for skill in (match_result.get("missing_skills", []) or [])
        if normalize_text(skill)
    ]
    projects = _verified_project_evidence(resume_profile, question, job_profile or {}, limit=2)
    experience = [
        normalize_text(item)
        for item in (resume_profile.get("experience", []) or [])[:2]
        if normalize_text(item)
    ]
    return {
        "demonstrated_experience": [{"project": project.get("name", "")} for project in projects],
        "experience": experience,
        "listed_skills": _dedupe_strings(
            [format_skill_display(skill) for skill in (resume_profile.get("skills", []) or [])]
        )[:8],
        "transferable_experience": _dedupe_strings(experience)[:2],
        "missing_requirements": _dedupe_strings(missing)[:6],
        "related_skills": _dedupe_strings(related_skills)[:5],
        "low_evidence_guidance": _low_evidence_guidance(match_result, missing),
    }


def get_string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [normalize_text(item) for item in value if normalize_text(item)]


def _with_generation_metadata(
    result: dict,
    source: str,
    provider: str,
    used_fallback: bool,
    generation_time_ms=None,
    fallback_reason: str | None = None,
    llm_error: dict | None = None,
) -> dict:
    response = {
        **result,
        "generation_source": source,
        "llm_provider": provider,
        "used_fallback": used_fallback,
    }
    if generation_time_ms is not None:
        response["generation_time_ms"] = generation_time_ms
    if fallback_reason:
        response["fallback_reason"] = fallback_reason
    if used_fallback:
        logger.warning(
            "writer_fallback writer=application_answer provider=%s reason=%s duration_ms=%s",
            provider or "unknown",
            fallback_reason or "unknown",
            generation_time_ms,
        )
    if llm_error:
        response["llm_error"] = llm_error
    return response


def _safe_llm_error_metadata(llm_result: dict) -> dict | None:
    error = llm_result.get("error") if isinstance(llm_result, dict) else None
    if not isinstance(error, dict):
        return None
    safe_error = {}
    for key in ("type", "status_code"):
        if error.get(key) is not None:
            safe_error[key] = error.get(key)
    if error.get("message"):
        safe_error["message"] = normalize_text(error.get("message"))[:180]
    return safe_error or None


def normalize_text(value) -> str:
    return normalize_spaces(value)


def extract_candidate_name(resume_profile: dict) -> str:
    return normalize_unmatched_brackets(normalize_text(resume_profile.get("name"))) or "I"


def extract_top_skills(resume_profile: dict, match_result: dict, limit: int = 5) -> list:
    matched_skills = match_result.get("matched_skills", [])
    resume_skills = resume_profile.get("skills", [])
    skills = []

    source_skills = matched_skills if "matched_skills" in match_result else resume_skills
    for skill in source_skills:
        normalized_skill = format_skill_display(skill)
        if normalized_skill and normalized_skill.lower() not in [item.lower() for item in skills]:
            skills.append(normalized_skill)

    return skills[:limit]


def extract_project_highlights(
    resume_profile: dict,
    limit: int = 2,
    relevant_terms: set[str] | None = None,
) -> list:
    projects = resume_profile.get("projects", []) or []
    highlights = []

    for index, project in enumerate(projects[:limit]):
        project_text = format_project_for_answer(project, index, relevant_terms=relevant_terms)

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

    text = strip_project_dates(text)

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
        text = re.sub(rf"^{re.escape(project_name)}\b", "", text, flags=re.IGNORECASE).strip(" :-,.;")

    text = re.sub(
        r"\b(?:remote\s+developer\s+)?project\s+overview\b\s*:?",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    text = re.sub(
        r"(?:^|[.;])\s*(?:used|technologies? used:?|tech stack:?)\s+[A-Za-z0-9 .,+/&()#-]+$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    tech_tail = re.search(r"\s+Used\s+(.+)$", text, flags=re.IGNORECASE)
    if tech_tail and not re.search(
        r"\b(to|for|build|built|develop|developed|create|created|implement|implemented|analyz|classif|predict|match)\b",
        tech_tail.group(1),
        flags=re.IGNORECASE,
    ):
        text = text[: tech_tail.start()].strip()
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

    text = re.sub(r"^(I\s+)?(built|developed|created|implemented|worked|performed|conducted|designed)\b", lambda match: match.group(2).lower(), text, flags=re.IGNORECASE)
    text = re.sub(r"^(and|or)\s+", "", text, flags=re.IGNORECASE)
    if " using " in text.lower():
        text = re.split(r"\s+using\s+", text, maxsplit=1, flags=re.IGNORECASE)[0]
    return _trim_words(text.strip(" :-,.;"), 35).rstrip(".")


def format_project_for_answer(project: dict, index: int, relevant_terms: set[str] | None = None) -> str:
    name, description, technologies = _project_parts(project)
    action_summary = clean_project_description_for_writing(name, description)
    technology_text = _technology_text(technologies, relevant_terms=relevant_terms)

    if _is_messy_project_summary(action_summary):
        action_summary = _fallback_project_summary(name, technology_text)
    elif (
        technology_text
        and "," not in technology_text
        and _normalized_term(technology_text) not in _normalized_term(action_summary)
        and not re.search(r"\busing\b", action_summary, re.IGNORECASE)
    ):
        action_summary = f"{action_summary} using {technology_text}"

    action_summary = _trim_words(action_summary, 35).rstrip(".")
    if not name:
        name = "practical"

    if index == 0:
        return f"For my {name} project, I {action_summary}."
    action_summary = re.sub(r"^worked on\s+", "", action_summary, flags=re.IGNORECASE)
    if re.match(r"^(built|developed|created|implemented|performed|conducted|analyzed|designed)\b", action_summary, flags=re.IGNORECASE):
        return f"In {name}, I {action_summary}."
    return f"Another relevant project, {name}, focused on {action_summary}."


def summarize_project_for_writing(project: dict, max_words: int = 35) -> str:
    return _trim_words(format_project_for_answer(project, 0), max_words + 8)


def _verified_project_evidence(
    resume_profile: dict,
    question: str = "",
    job_profile: dict | None = None,
    limit: int = 2,
) -> list[dict]:
    relevant_terms = _question_relevant_terms(question, job_profile or {})
    projects = []
    source_projects = resume_profile.get("projects", []) or []
    if not isinstance(source_projects, list):
        return []
    for project in source_projects:
        if not isinstance(project, (dict, str)):
            continue
        name, description, technologies = _project_parts(project)
        name = _clean_project_name_for_writing(name)
        description = clean_project_description_for_writing(name, description)
        if not name and not description:
            continue
        projects.append(
            {
                "name": name,
                "description": _trim_words(description, 32).rstrip("."),
                "technologies": _filter_relevant_technologies(technologies, relevant_terms, limit=3),
            }
        )
    return rank_projects(projects, relevant_terms, limit)


def _project_parts(project: dict) -> tuple[str, str, list]:
    if isinstance(project, str):
        name = normalize_text(project)
        description = ""
        technologies = []
    elif isinstance(project, dict):
        name = normalize_text(project.get("name")) if isinstance(project.get("name"), str) else ""
        description = normalize_text(project.get("description")) if isinstance(project.get("description"), str) else ""
        raw_technologies = project.get("technologies", [])
        technologies = [
            format_skill_display(item)
            for item in raw_technologies
            if isinstance(item, str) and normalize_text(item)
        ] if isinstance(raw_technologies, list) else []
    else:
        name = normalize_text(getattr(project, "name", ""))
        description = normalize_text(getattr(project, "description", ""))
        raw_technologies = getattr(project, "technologies", [])
        technologies = [
            format_skill_display(item)
            for item in raw_technologies
            if isinstance(item, str) and normalize_text(item)
        ] if isinstance(raw_technologies, list) else []
    return name, description, technologies


def _clean_project_name_for_writing(name: str) -> str:
    text = normalize_text(name)
    text = re.sub(
        r"\s*(?:\||-|–|—)\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec)[a-z]*\s+\d{4}"
        r"(?:\s*[-–]\s*(?:present|(?:jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec)[a-z]*\s+\d{4}))?\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return strip_project_dates(text)


def _dedupe_strings(items: list) -> list[str]:
    values = []
    for item in items:
        value = normalize_text(item)
        if value and value.lower() not in [existing.lower() for existing in values]:
            values.append(value)
    return values


def summarize_education(education) -> str:
    return select_best_education(education)


def detect_question_type(application_question: str) -> str:
    question = normalize_text(application_question).lower()

    if any(phrase in question for phrase in ("compensation", "salary", "stipend", "pay expectation", "expected ctc")):
        return "compensation"
    if any(phrase in question for phrase in ("availability", "available", "notice period", "start date", "joining")):
        return "availability"
    if any(phrase in question for phrase in ("tell me about yourself", "introduce yourself", "about yourself")):
        return "about_self"
    if any(phrase in question for phrase in ("strength", "strengths", "what are you good at")):
        return "strengths"
    if any(phrase in question for phrase in ("skill", "technical", "technology", "tools")):
        return "technical_skills"
    if any(phrase in question for phrase in ("why should we hire", "why hire", "hire you")):
        return "general_suitability"
    if any(phrase in question for phrase in ("why are you interested", "why interested", "why this role", "why do you want")):
        return "role_motivation"
    if any(phrase in question for phrase in ("experience", "project", "worked on", "relevant")):
        return "project_experience"
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

    if education:
        key_points.append(f"Education: {education}")
    key_points.append(f"Target role: {role_title}")
    if company_name:
        key_points.append(f"Company: {company_name}")
    if top_skills:
        key_points.append("Matched skills: " + ", ".join(top_skills))
    for project in projects:
        key_points.append(f"Project: {_project_name_from_summary(project)}")

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
    application_question: str,
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
    skill_gap_result: dict,
) -> str:
    role_title = _safe_role_title(job_profile.get("role_title"), "this internship")
    company_name = normalize_text(job_profile.get("company_name"))
    education = summarize_education(resume_profile.get("education", []))
    skills = _question_relevant_skills(
        extract_top_skills(resume_profile, match_result, limit=8),
        application_question,
        job_profile,
        limit=4,
    )
    projects = extract_project_highlights(
        resume_profile,
        relevant_terms=_question_relevant_terms(application_question, job_profile),
    )

    role_phrase = _role_phrase(role_title, company_name)

    context_sentence = _context_sentence(education, role_phrase, role_title)
    skills_sentence = _skills_sentence(skills)
    projects_sentence = _projects_sentence(projects)
    overlap_sentence = _overlap_sentence(skills, role_phrase)

    if question_type == "compensation":
        return (
            "Draft requiring input: my compensation expectation is not provided in the resume or job description. "
            "Before submitting, add the expected stipend, salary range, or a line such as that you are open to discussing compensation based on the role scope."
        )

    if question_type == "availability":
        return (
            "Draft requiring input: my availability or notice period is not provided in the resume or job description. "
            "Before submitting, add the exact joining date, notice period, or weekly availability."
        )

    if question_type == "about_self":
        return (
            f"{context_sentence} My strongest relevant evidence is {join_human_list(skills) if skills else 'the project work in my resume'}. "
            f"{projects_sentence} I am looking for work where I can contribute carefully while building stronger role-specific evidence."
        )

    if question_type == "technical_skills":
        return (
            f"My most relevant technical skills for {role_phrase} are {join_human_list(skills) if skills else 'the skills shown through my projects'}. "
            f"{projects_sentence} I would use these strengths where they match the role and avoid overstating tools that are not shown in my resume."
        )

    if question_type == "strengths":
        strengths = [normalize_text(item) for item in (resume_profile.get("strengths", []) or []) if normalize_text(item)]
        strength_text = join_human_list(strengths[:3]) if strengths else "practical project execution and a relevant academic foundation"
        return (
            f"My strongest areas are {strength_text}. {skills_sentence} {projects_sentence} "
            f"These strengths would help me contribute reliably to {role_phrase}."
        )

    if question_type == "general_suitability":
        if not skills:
            return (
                f"{context_sentence} {projects_sentence} "
                f"My current evidence is limited for {role_phrase}, so I would be careful not to overstate my fit while bringing communication, consistency, and willingness to learn."
            )
        return (
            f"{context_sentence} {overlap_sentence} {projects_sentence} "
            f"I can bring careful execution and project-backed preparation to the role."
        )

    if question_type == "role_motivation":
        if not skills:
            return (
                f"I am interested in {role_phrase} because it would let me build practical web development experience. "
                f"{context_sentence} {projects_sentence} "
                "I would approach the opportunity as a learning-focused candidate and avoid overstating skills that are not yet shown in my resume."
            )
        return (
            f"I am interested in {role_phrase} because it connects closely with my current skills and project work. "
            f"{context_sentence} {skills_sentence} {projects_sentence} "
            "I would be excited to contribute to practical work with a team that can use this background."
        )

    if question_type == "project_experience":
        if not skills:
            return (
                "The clearest project I can reference from my resume is not direct web development experience, "
                f"but it does show practical follow-through. {projects_sentence} {context_sentence} "
                "I would approach the internship as a learning-focused candidate and avoid overstating experience that is not shown in my resume."
            )
        return (
            f"My most relevant experience comes from project work and hands-on practice. "
            f"{projects_sentence} {skills_sentence} {context_sentence}"
        )

    if question_type == "cover_message":
        return (
            f"Dear Hiring Team, I am writing to express my interest in {role_phrase}. "
            f"{context_sentence} {skills_sentence} {projects_sentence} "
            "I would welcome the opportunity to contribute useful work."
        )

    return (
        f"{context_sentence} I am interested in {role_phrase}. "
        f"{skills_sentence} {projects_sentence} "
        "I would bring curiosity, consistency, and evidence from my project work."
    )


def _context_sentence(education: str, role_phrase: str, role_title: str = "") -> str:
    if education and education != "my academic background":
        if not _education_supports_role(education, role_title):
            if education.lower().startswith("currently pursuing"):
                return f"I am {education[0].lower() + education[1:]}."
            return f"My academic background includes {education}."
        if education.lower().startswith("currently pursuing"):
            return f"I am {education[0].lower() + education[1:]}, which aligns with {role_phrase}."
        if education.lower().startswith(("a b.tech", "a bachelor")):
            return f"My academic background includes {education}, which aligns with {role_phrase}."
        if re.search(r"\bb\.?\s?tech\b|\bbtech\b|bachelor|b\.e\b", education, re.IGNORECASE):
            return f"My academic background in {education} aligns with {role_phrase}."
        return f"My background in {education} connects well with {role_phrase}."
    return f"I am applying for {role_phrase}."


def _education_supports_role(education: str, role_title: str) -> bool:
    education_text = normalize_text(education).lower()
    role_text = normalize_text(role_title).lower()
    if not role_text:
        return True
    if any(term in education_text for term in ("computer science", "information technology", "engineering", "data science", "artificial intelligence", "software")):
        return True
    if any(term in role_text for term in ("web", "software", "developer", "frontend", "backend", "ai", "ml", "data")):
        return False
    return True


def _skills_sentence(skills: list) -> str:
    if not skills:
        return "My profile is grounded in the project work included in my resume."
    return "The strongest overlaps with the role are " + join_human_list(skills) + "."


def _overlap_sentence(skills: list, role_phrase: str) -> str:
    if not skills:
        return "My profile is grounded in the project work included in my resume."
    return f"My clearest skill matches are {join_human_list(skills)}."


def _projects_sentence(projects: list) -> str:
    if not projects:
        return "I am also working on building clearer project evidence for my resume."
    if len(projects) == 1:
        return projects[0]
    return f"{projects[0]} {projects[1]}"


def _learning_sentence(learning_focus: list) -> str:
    if not learning_focus:
        return "I would focus on understanding the team's standards and contributing reliable work."
    return (
        "For the remaining gaps, I would be careful not to overstate them and would prioritize "
        + join_human_list(learning_focus)
        + " during preparation."
    )


def _learning_focus(match_result: dict, skill_gap_result: dict) -> list:
    return []


def _low_evidence_guidance(match_result: dict, missing_requirements: list) -> str:
    score = int(match_result.get("match_score") or 0)
    missing_count = len([item for item in missing_requirements if normalize_text(item)])
    if score < 30:
        return "Weak match: write modestly. Do not claim direct role qualification. Emphasize motivation, communication, and learning interest only when supported."
    if missing_count >= 3:
        return "Partial match: emphasize demonstrated skills and transferable experience. Do not name missing requirements as candidate experience."
    return "Strong or focused match: emphasize demonstrated projects and directly supported skills."


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
    text = normalize_unmatched_brackets(re.sub(r"\s+", " ", value).strip(" -•\t.,"))
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
    return education_for_writing(value)


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


def _technology_text(technologies: list, relevant_terms: set[str] | None = None) -> str:
    return ", ".join(_filter_relevant_technologies(technologies, relevant_terms or set(), limit=3))


def _filter_relevant_technologies(
    technologies: list,
    relevant_terms: set[str],
    limit: int = 3,
) -> list[str]:
    unique_technologies = _dedupe_strings([format_skill_display(technology) for technology in technologies])
    if not relevant_terms:
        return unique_technologies[: min(2, limit)]

    selected = [
        technology
        for technology in unique_technologies
        if _normalized_term(technology) in relevant_terms
    ]
    return (selected or unique_technologies)[:limit]


def _question_relevant_terms(question: str, job_profile: dict) -> set[str]:
    text = " ".join(
        [
            normalize_text(question),
            normalize_text(job_profile.get("role_title")),
            " ".join(normalize_text(item) for item in (job_profile.get("responsibilities", []) or [])),
            " ".join(normalize_text(item) for item in (job_profile.get("required_skills", []) or [])),
            " ".join(normalize_text(item) for item in (job_profile.get("preferred_skills", []) or [])),
        ]
    ).lower()
    terms = set()
    for skill in re.findall(r"[a-z][a-z0-9.+#-]*(?:\s+[a-z0-9.+#-]+){0,3}", text):
        terms.add(_normalized_term(skill))
    for skill in (
        "python",
        "sql",
        "react",
        "next.js",
        "langchain",
        "rag",
        "nlp",
        "machine learning",
        "ai",
        "fastapi",
        "node.js",
        "javascript",
        "html",
        "css",
        "rest api",
        "git",
        "tailwind css",
    ):
        if re.search(rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])", text):
            terms.add(_normalized_term(skill))
    return {term for term in terms if term}


def _question_relevant_skills(
    skills: list,
    question: str,
    job_profile: dict,
    limit: int,
) -> list[str]:
    relevant_terms = _question_relevant_terms(question, job_profile)
    formatted = _dedupe_strings([format_skill_display(skill) for skill in skills])
    selected = [skill for skill in formatted if _normalized_term(skill) in relevant_terms]
    return (selected or formatted)[:limit]


def _normalized_term(value: str) -> str:
    text = normalize_text(value).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    aliases = {
        "js": "javascript",
        "nextjs": "next.js",
        "next js": "next.js",
        "reactjs": "react",
        "nodejs": "node.js",
        "node js": "node.js",
        "natural language processing": "nlp",
        "retrieval augmented generation": "rag",
        "artificial intelligence": "ai",
    }
    return aliases.get(text, text)


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
        return "worked on a phishing detection project" + (f" using {technology_text}" if technology_text else "")
    if "restaurant growth" in lowered_name:
        return "worked on a restaurant growth analysis project" + (f" using {technology_text}" if technology_text else "")
    if technology_text:
        return f"worked on the project using {technology_text}"
    return "worked on the project"


def clean_generated_text(text: str) -> str:
    cleaned = normalize_text_artifacts(text, preserve_newlines=False)
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\b(?:reasoning|analysis)\s*:\s*[^.?!]*(?:[.?!]|$)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[[^\]\n]{0,80}\]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.replace(" ,", ",")
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = re.sub(r"where I Projects include", "where I", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"project,\s+I\s+and\b", "project involving", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"involving\s+worked\s+on\s+", "involving ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"project,\s+I\s+Strategic\b", "project involving strategic", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"project,\s+I\s+Hybrid Phishing Detection System\b", "project, I built", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)
    return cleaned.strip()


def _extract_llm_json_field(text: str, field_name: str) -> str:
    payload = _parse_llm_json(text)
    if not isinstance(payload, dict):
        return ""
    return normalize_text(payload.get(field_name) or payload.get("generated_answer") or "")


def _parse_llm_json(text: str):
    raw_text = str(text or "").strip()
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
        raw_text = re.sub(r"\s*```$", "", raw_text)
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw_text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _has_unsupported_claims(text: str, evidence: dict) -> bool:
    return bool(_diagnose_unsupported_claims(text, evidence, "application_answer"))


def _candidate_evidence_text(evidence: dict) -> str:
    parts = []
    candidate = evidence.get("candidate", {}) or {}
    parts.append(candidate.get("education", ""))
    parts.extend(evidence.get("listed_skills", []) or [])
    parts.extend(evidence.get("transferable_experience", []) or [])
    parts.extend(evidence.get("matched_skills", []) or [])
    for project in evidence.get("projects", []) or []:
        parts.append(project.get("name", ""))
        parts.append(project.get("description", ""))
        parts.extend(project.get("technologies", []) or [])
    return normalize_text(" ".join(str(part) for part in parts if part)).lower()


def _has_unverified_claim_markers(text: str, candidate_evidence_text: str) -> bool:
    unsupported_claims = (
        (r"\b(?:currently completing|recently completed|graduated)\b", r"\bcurrently\s+(?:completing|pursuing)\b|\b(?:recently completed|graduated)\b"),
        (r"\bdata processing pipelines?\b", r"\bdata processing pipelines?\b"),
        (r"\bautomated image classification\b", r"\bautomated image classification\b"),
        (r"\bdata collection\b", r"\bdata collection\b"),
        (r"\bfaster and more reliable\b", r"\bfaster and more reliable\b"),
        (r"\bworking knowledge of\b", r"\bworking knowledge of\b"),
        (r"\bcreate accessible layouts\b", r"\bcreate accessible layouts\b"),
        (r"\bsoftware-focused project\b", r"\bsoftware-focused project\b"),
        (r"\bcollaborative (?:workflow|software development)\b", r"\bcollaborative (?:workflow|software development)\b"),
        (r"\b(?:clear|strong|effective) communication (?:skills|abilities)\b", r"\b(?:clear|strong|effective) communication (?:skills|abilities)\b"),
        (r"\bquickly (?:adopt|learn)\b|\blearn\w* (?:new )?(?:tools|technologies) quickly\b", r"\bquickly (?:adopt|learn)\b|\blearn\w* (?:new )?(?:tools|technologies) quickly\b"),
        (r"\b(?:systematic|methodical) problem[- ]solving\b|\bapproach(?:es|ed)? problems systematically\b", r"\b(?:systematic|methodical) problem[- ]solving\b|\bapproach(?:es|ed)? problems systematically\b"),
        (r"\b(?:learn|pick up|adapt to) (?:new )?(?:tools|technologies|skills)? ?quickly\b", r"\b(?:learn|pick up|adapt to) (?:new )?(?:tools|technologies|skills)? ?quickly\b"),
        (r"\bcommunicat(?:e|es|ed|ing) (?:my )?(?:findings|results|progress|insights)\b", r"\bcommunicat(?:e|es|ed|ing) (?:my )?(?:findings|results|progress|insights)\b"),
        (r"\bfocused on building modern web interfaces\b", r"\bfocused on building modern web interfaces\b"),
    )
    return any(
        re.search(pattern, text) and not re.search(support_pattern, candidate_evidence_text)
        for pattern, support_pattern in unsupported_claims
    )


def _has_unsupported_project_claims(text: str, evidence: dict) -> bool:
    stop_words = {
        "about", "ability", "across", "also", "and", "as", "at", "by", "can", "could",
        "create", "created", "creating", "data", "demonstrates", "designed", "developed",
        "during", "for", "from", "gives", "has", "have", "i", "in", "into", "is", "it",
        "me", "my", "of", "on", "or", "our", "project", "provides", "that", "the", "their",
        "this", "to", "using", "was", "were", "which", "with", "work", "worked", "built",
        "implemented", "integrated", "added", "used", "connected", "helped", "contributed",
        "focused", "resulted", "resulting", "ensured", "ensuring", "made", "maintained",
        "performed", "prepared", "organized", "documented", "analyzed", "conducted", "led",
    }
    claim_verbs = re.compile(
        r"\b(?:built|developed|created|designed|implemented|automated|contributed|worked|used|analyzed|integrated|added|prepared|conducted|maintained|organized|documented)\b",
        re.IGNORECASE,
    )
    sentences = re.split(r"(?<=[.!?])\s+", normalize_text(text))
    for project in evidence.get("projects", []) or []:
        if not isinstance(project, dict):
            continue
        name = normalize_text(project.get("name"))
        if not name:
            continue
        name_tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
        technologies = project.get("technologies", []) or []
        source = normalize_text(" ".join([project.get("description", ""), *technologies])).lower()
        supported = normalized_claim_tokens(source) - stop_words - name_tokens
        for sentence in sentences:
            name_match = re.search(re.escape(name), sentence, flags=re.IGNORECASE)
            project_reference = re.search(r"\b(?:in|during|on) my project\b", sentence, flags=re.IGNORECASE)
            if name_match:
                claim_text = sentence[name_match.end():]
            elif project_reference:
                claim_text = sentence[project_reference.end():]
            else:
                continue
            claim_text = re.split(r",?\s+and\s+my\b", claim_text, maxsplit=1, flags=re.IGNORECASE)[0]
            if not claim_verbs.search(claim_text):
                continue
            claimed = normalized_claim_tokens(claim_text) - stop_words - name_tokens
            if len(claimed) >= 4 and len(claimed & supported) / len(claimed) < 0.25:
                return True
    return False


def _has_unsupported_responsibility_claims(
    text: str,
    responsibilities: list[str],
    candidate_evidence_text: str,
) -> bool:
    if not responsibilities:
        return False
    unsupported_phrases = _unsupported_candidate_phrases(
        responsibilities,
        candidate_evidence_text,
    )
    if not unsupported_phrases:
        return False

    claim_patterns = (
        r"\b(?:i|my|me)\b[^.?!]{0,120}\b(?:built|build|developed|develop|created|create|implemented|implement|prepared|prepare|evaluated|evaluate|analyzed|analyze|worked on|experience in|experience with|practical experience in|proficiency in)\b[^.?!]*",
        r"\b(?:my projects?|my experience|my background)\b[^.?!]{0,140}",
    )
    claim_spans = [
        match.group(0).lower()
        for pattern in claim_patterns
        for match in re.finditer(pattern, text, flags=re.IGNORECASE)
    ]
    for claim in claim_spans:
        if _is_transferable_or_learning_context(claim):
            continue
        if any(phrase in claim for phrase in unsupported_phrases):
            return True
    return False


def _unsupported_candidate_phrases(
    responsibilities: list[str],
    candidate_evidence_text: str,
) -> set[str]:
    phrases = set()
    for responsibility in responsibilities:
        normalized = normalize_text(responsibility).lower()
        for phrase in _responsibility_phrases(normalized):
            if phrase and phrase not in candidate_evidence_text:
                phrases.add(phrase)
    return phrases


def _responsibility_phrases(text: str) -> set[str]:
    phrases = set()
    for verb in (
        "build",
        "building",
        "evaluate",
        "evaluating",
        "prepare",
        "preparing",
        "develop",
        "developing",
        "create",
        "creating",
    ):
        match = re.search(
            rf"\b{verb}\s+([^.;,]+?)(?:\s+and\s+|\s*,\s*|$)",
            text,
        )
        if match:
            phrases.add(_normalize_claim_phrase(match.group(1)))
    for noun_phrase in (
        "generative ai workflows",
        "chatbot responses",
        "sql-backed analysis reports",
        "agent prototypes",
    ):
        if noun_phrase in text:
            phrases.add(noun_phrase)
    return {phrase for phrase in phrases if len(phrase.split()) >= 2}


def _normalize_claim_phrase(value: str) -> str:
    text = normalize_text(value).lower()
    text = re.sub(r"^(?:small|basic|simple|the|a|an)\s+", "", text)
    return text.strip(" .,:;")


def _is_transferable_or_learning_context(text: str) -> bool:
    return bool(
        re.search(
            r"\b(transferable|relevant foundation|preparation for|prepared me to learn|interested in learning|grow into|continue(?:ing)? to grow|learning interest)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def _term_in_text(term: str, lowered_text: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])", lowered_text))
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
