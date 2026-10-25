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
- A missing skill may be mentioned only as an honest learning goal, never as existing expertise.
- Preserve an explicitly stated education status and do not infer one.
- Avoid fake claims, inflated experience, or invented metrics.
- Keep short letters around 120-180 words, medium letters around 180-260 words,
  and long letters around 260-360 words.
- Match the requested tone.
"""


def generate_cover_letter(
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
    skill_gap_result: dict,
    tone: str = "professional",
    length: str = "short",
    evaluation_context: dict | None = None,
) -> dict:
    writer_started = perf_counter()
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
            generation_time_ms=round((perf_counter() - writer_started) * 1000, 3),
            fallback_reason="provider_mock",
        )

    evidence = build_cover_letter_evidence(
        resume_profile=resume_profile,
        job_profile=job_profile,
        match_result=match_result,
        tone=tone,
        cover_letter_length=length,
    )
    report_context = None
    if settings.groq_evaluation_mode and llm_status.get("provider") == "groq" and evaluation_context is not None:
        report_context = prepare_evaluation_context(evaluation_context)
    system_prompt, user_prompt = build_cover_letter_prompt(
        resume_profile=resume_profile,
        job_profile=job_profile,
        match_result=match_result,
        skill_gap_result=skill_gap_result,
        tone=tone,
        cover_letter_length=length,
    )
    call_started = perf_counter()
    try:
        llm_result = llm_service.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.25,
            max_tokens=_llm_max_tokens_for_length(length),
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
    llm_cover_letter = clean_generated_text(_extract_llm_json_field(llm_result.get("text"), "cover_letter"))
    validation_issue = _llm_cover_letter_validation_issue(llm_cover_letter, length, evidence)
    validation_diagnostics = (
        diagnose_llm_cover_letter_validation(llm_cover_letter, length, evidence)
        if validation_issue and not llm_result.get("used_fallback")
        else []
    )
    _log_validation_diagnostics(validation_diagnostics)

    if report_context is not None:
        selected_text = llm_cover_letter if validation_issue and not llm_result.get("used_fallback") else rule_based_result["cover_letter"] if llm_result.get("used_fallback") else llm_cover_letter
        EvaluationReportStore().append_writer_result(
            report_context,
            writer="cover_letter",
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
        "cover_letter": llm_cover_letter,
        "word_count": count_words(llm_cover_letter),
        "generation_source": "llm",
        "llm_provider": llm_result.get("provider", llm_status.get("provider", "")),
        "used_fallback": False,
        "generation_time_ms": llm_result.get("generation_time_ms"),
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
    evidence = build_cover_letter_evidence(
        resume_profile=resume_profile,
        job_profile=job_profile,
        match_result=match_result,
        tone=tone,
        cover_letter_length=cover_letter_length,
    )

    system_prompt = (
        "Write a natural, relevant internship cover letter using only candidate_factual_anchors for candidate facts and preserve explicit education status as stated. "
        "project_work supports only its description and listed project technologies; listed_skills means only those skills are listed, not hands-on use; stated_goals supports only explicit goals. "
        "Use job_context only to select relevant anchors; JD content is not candidate evidence. Paraphrase naturally without adding implementation details or outcomes. "
        "Do not invent personal activities, plans, or qualities absent from the anchors. With no stated_goals, invent no coursework or future projects. Omit unsupported claims. "
        "Start with 'Dear Hiring Team,' and close with 'Sincerely,' plus the name only when candidate_factual_anchors.identity is present. "
        "Meet the requested length and tone. Return strict JSON only with exactly one key: {\"cover_letter\":\"...\"}."
    )
    ledger = build_writer_evidence_ledger(evidence, resume_profile)
    user_prompt = json.dumps(
        {"evidence": {
            "task": evidence["task"],
            "tone": evidence["tone"],
            "length": evidence["length"],
            "candidate_factual_anchors": ledger["candidate_factual_anchors"],
            "job_context": ledger["job_context"],
        }},
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return system_prompt, user_prompt


def is_valid_llm_cover_letter(text: str, length: str, evidence: dict | None = None) -> bool:
    return _llm_cover_letter_validation_issue(text, length, evidence) is None


def _llm_cover_letter_validation_issue(text: str, length: str, evidence: dict | None = None) -> str | None:
    if len(text.strip()) < 80:
        return "empty_or_too_short"

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
        "<think",
        "</think>",
        "reasoning:",
        "analysis:",
    )
    if any(phrase in lowered for phrase in blocked_phrases):
        return "blocked_or_malformed_text"
    if not text.startswith("Dear Hiring Team,"):
        return "missing_opening"
    if "Sincerely," not in text:
        return "missing_signature"
    if re.search(r"Sincerely,\s*\n\s*Candidate\b", text, flags=re.IGNORECASE):
        return "placeholder_signature"
    if evidence and _has_unsupported_claims(text, evidence):
        return "unsupported_claims"

    normalized_length = normalize_text(length).lower()
    if normalized_length == "long":
        max_words = 430
    elif normalized_length == "medium":
        max_words = 360
    else:
        max_words = 260
    if count_words(text) > max_words:
        return "word_limit_exceeded"
    return None


def diagnose_llm_cover_letter_validation(text: str, length: str, evidence: dict | None = None) -> list[dict]:
    """Explain a rejected letter without exposing its text or candidate evidence."""
    issue = _llm_cover_letter_validation_issue(text, length, evidence)
    diagnostics = []
    if issue == "empty_or_too_short":
        diagnostics.append(validation_diagnostic("cover_letter", "minimum_output_length"))
    if issue == "blocked_or_malformed_text":
        diagnostics.append(validation_diagnostic("cover_letter", "blocked_or_malformed_text"))
    if issue == "missing_opening":
        diagnostics.append(validation_diagnostic("cover_letter", "missing_cover_letter_opening"))
    if issue == "missing_signature":
        diagnostics.append(validation_diagnostic("cover_letter", "missing_cover_letter_signature"))
    if issue == "placeholder_signature":
        diagnostics.append(validation_diagnostic("cover_letter", "placeholder_signature"))
    if issue == "word_limit_exceeded":
        diagnostics.append(validation_diagnostic("cover_letter", "output_word_limit"))
    if evidence:
        diagnostics.extend(_diagnose_unsupported_claims(text, evidence, "cover_letter"))
    if issue is not None and not diagnostics:
        diagnostics.append(validation_diagnostic("cover_letter", "unsupported_claim_unclassified"))
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


def _log_validation_diagnostics(diagnostics: list[dict]) -> None:
    for diagnostic in diagnostics:
        logger.warning(
            "writer_validation_rejected writer=%s rule_id=%s evidence_category=%s explanation=%s",
            diagnostic["writer"],
            diagnostic["rejected_rule_id"],
            diagnostic["evidence_category"],
            diagnostic["safe_explanation"],
        )


def build_cover_letter_evidence(
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
    tone: str,
    cover_letter_length: str,
) -> dict:
    grounding = _build_grounding_evidence(
        resume_profile=resume_profile,
        match_result=match_result,
        job_profile=job_profile,
    )
    return {
        "task": "cover_letter",
        "tone": normalize_text(tone) or "professional",
        "length": normalize_text(cover_letter_length) or "short",
        "candidate": {
            "name": extract_candidate_name(resume_profile),
            "education": extract_education(resume_profile),
            "experience": grounding["experience"],
        },
        "job_context": {
            "role_title": _safe_role_title(job_profile.get("role_title"), "the internship role"),
            "company_name": normalize_text(job_profile.get("company_name")),
            "responsibilities": [
                normalize_text(item)
                for item in (job_profile.get("responsibilities", []) or [])[:3]
                if normalize_text(item)
            ],
            "missing_requirements": grounding["missing_requirements"],
            "related_requirements": grounding["related_skills"],
        },
        "matched_skills": extract_top_skills(resume_profile, match_result, limit=6),
        "projects": _verified_project_evidence(resume_profile, job_profile, limit=2),
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
    projects = _verified_project_evidence(resume_profile, job_profile or {}, limit=2)
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
            "writer_fallback writer=cover_letter provider=%s reason=%s duration_ms=%s",
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


def _llm_max_tokens_for_length(length: str) -> int:
    normalized_length = normalize_text(length).lower()
    if normalized_length == "long":
        return 700
    return 450 if normalized_length == "medium" else 350


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [normalize_text(item) for item in value if normalize_text(item)]


def normalize_text(value) -> str:
    return normalize_spaces(value)


def extract_candidate_name(resume_profile: dict) -> str:
    return _normalize_candidate_name(resume_profile.get("name"))


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
    highlights: list[str] = []

    for index, project in enumerate(projects[:limit]):
        project_text = format_project_for_answer(project, index, relevant_terms=relevant_terms)

        if project_text:
            highlights.append(project_text)

    return highlights[:limit]


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
        return f"One project I can point to is {name}, where I {action_summary}."
    action_summary = re.sub(r"^worked on\s+", "", action_summary, flags=re.IGNORECASE)
    if re.match(r"^(built|developed|created|implemented|performed|conducted|analyzed|designed)\b", action_summary, flags=re.IGNORECASE):
        return f"I also completed {name}, where I {action_summary}."
    return f"I also completed {name}, which focused on {action_summary}."


def summarize_project_for_writing(project: dict, max_words: int = 35) -> str:
    return _trim_words(format_project_for_answer(project, 0), max_words + 8)


def _verified_project_evidence(
    resume_profile: dict,
    job_profile: dict | None = None,
    limit: int = 2,
) -> list[dict]:
    relevant_terms = _job_relevant_terms(job_profile or {})
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
    projects = extract_project_highlights(
        resume_profile,
        limit=2,
        relevant_terms=_job_relevant_terms(job_profile),
    )
    experience = extract_experience_highlights(resume_profile, limit=2)
    role_phrase = _role_phrase(role_title, company_name)

    paragraphs = [
        "Dear Hiring Team,",
        _opening_paragraph(role_title, company_name, role_phrase, education),
        _evidence_paragraph(skills, projects, experience),
        _closing_body_paragraph(role_phrase),
    ]

    normalized_length = normalize_text(length).lower()
    if normalized_length in {"medium", "long"}:
        paragraphs.insert(
            3,
            _medium_detail_paragraph(job_profile, match_result),
        )
    if normalized_length == "long":
        paragraphs.insert(
            4,
            _long_detail_paragraph(resume_profile, job_profile, skill_gap_result),
        )

    candidate_name = extract_candidate_name(resume_profile)
    signature = "Sincerely" + (",\n" + candidate_name if candidate_name else ",")
    paragraphs.append("Thank you for your consideration.\n\n" + signature)
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
        if not _education_supports_role(education, role_title):
            if education.lower().startswith("currently pursuing"):
                return f"{first_sentence} I am {education[0].lower() + education[1:]}."
            return f"{first_sentence} My academic background includes {education}."
        if education.lower().startswith("currently pursuing"):
            return (
                f"{first_sentence} I am {education[0].lower() + education[1:]}, which gives me relevant preparation for the role."
            )
        if education.lower().startswith(("a b.tech", "a bachelor")):
            return (
                f"{first_sentence} My academic background includes {education}, which gives me relevant preparation for the role."
            )
        return (
            f"{first_sentence} My academic background in {education} gives me relevant preparation for the role."
        )
    return f"{first_sentence} My project work aligns with the responsibilities of this opportunity."


def _evidence_paragraph(skills: list, projects: list, experience: list) -> str:
    sentences = []
    if skills:
        sentences.append("The clearest skill matches are " + join_human_list(skills) + ".")
    if projects:
        if len(projects) == 1:
            sentences.append(projects[0])
        else:
            sentences.append(f"{projects[0]} {projects[1]}")
    if experience:
        sentences.append("I also bring related experience: " + "; ".join(_format_experience_phrase(item) for item in experience) + ".")
    if not sentences:
        sentences.append("I am building practical experience through focused projects and consistent learning.")
    return " ".join(sentences)


def _growth_paragraph(learning_focus: list, role_phrase: str) -> str:
    return _closing_body_paragraph(role_phrase)


def _closing_body_paragraph(role_phrase: str) -> str:
    return (
        "I would bring consistency, careful communication, and attention to the work assigned to me."
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


def _long_detail_paragraph(
    resume_profile: dict,
    job_profile: dict,
    skill_gap_result: dict,
) -> str:
    role_title = _safe_role_title(job_profile.get("role_title"), "this internship")
    suggestions = [
        normalize_text(item)
        for item in (skill_gap_result.get("resume_improvement_suggestions", []) or [])[:2]
        if normalize_text(item)
    ]
    projects = extract_project_highlights(
        resume_profile,
        limit=1,
        relevant_terms=_job_relevant_terms(job_profile),
    )

    sentences = [
        f"I would approach {role_title} with a balance of hands-on contribution and deliberate learning."
    ]
    if projects:
        sentences.append(
            "My project work gives me a base for translating technical concepts into working features."
        )
    if suggestions:
        sentences.append(
            "I am also actively improving my profile by focusing on " + " ".join(suggestions)
        )
    return " ".join(sentences)


def _build_opening_summary(resume_profile: dict, job_profile: dict) -> str:
    role_title = _safe_role_title(job_profile.get("role_title"), "the internship role")
    education = extract_education(resume_profile)
    if education and education != "my academic background":
        if education.lower().startswith("currently pursuing"):
            return f"Candidate {education[0].lower() + education[1:]} and applying for {role_title}."
        return f"Candidate pursuing {education} and applying for {role_title}."
    return f"Candidate applying for {role_title}."


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


def _format_experience_phrase(value: str) -> str:
    text = normalize_text(value)
    text = re.sub(r";\s*([A-Z])", lambda match: ", where I " + match.group(1).lower(), text)
    text = re.sub(r"\b(Cleaned|Created|Built|Fixed|Connected|Prepared)\b", lambda match: match.group(1).lower(), text)
    return text


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


def _fit_length(text: str, length: str) -> str:
    normalized_length = normalize_text(length).lower()
    if normalized_length == "long":
        target_max = 360
    elif normalized_length == "medium":
        target_max = 260
    else:
        target_max = 180
    if count_words(text) <= target_max:
        return text

    words = text.split()
    trimmed = " ".join(words[:target_max]).rstrip(".,;:")
    sentence_end = max(trimmed.rfind("."), trimmed.rfind("!"), trimmed.rfind("?"))
    if sentence_end > len(trimmed) * 0.65:
        return trimmed[: sentence_end + 1]
    return trimmed + "."


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


def _job_relevant_terms(job_profile: dict) -> set[str]:
    text = " ".join(
        [
            normalize_text(job_profile.get("role_title")),
            " ".join(normalize_text(item) for item in (job_profile.get("responsibilities", []) or [])),
            " ".join(normalize_text(item) for item in (job_profile.get("required_skills", []) or [])),
            " ".join(normalize_text(item) for item in (job_profile.get("preferred_skills", []) or [])),
        ]
    ).lower()
    terms = set()
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
    return terms


def _normalized_term(value: str) -> str:
    text = normalize_text(value).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    aliases = {
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


def _normalize_candidate_name(value) -> str:
    name = normalize_unmatched_brackets(normalize_text(value))
    if not name:
        return ""
    if not re.fullmatch(r"[A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){0,3}", name):
        return name
    if name.islower() or name.isupper():
        return " ".join(part[:1].upper() + part[1:].lower() for part in name.split())
    return name


def clean_generated_text(text: str) -> str:
    cleaned = normalize_text_artifacts(text, preserve_newlines=True)
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\b(?:reasoning|analysis)\s*:\s*[^.?!\n]*(?:[.?!]|\n|$)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[[^\]\n]{0,80}\]", "", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
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
    return str(payload.get(field_name) or "").strip()


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
    return bool(_diagnose_unsupported_claims(text, evidence, "cover_letter"))


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


def _experience_dict_to_text(experience: dict) -> str:
    title = normalize_text(experience.get("title") or experience.get("role"))
    company = normalize_text(experience.get("company") or experience.get("organization"))
    description = normalize_text(experience.get("description"))

    if title and company and description:
        return f"{title} at {company}: {description}"
    if title and company:
        return f"{title} at {company}"
    return title or company or description
