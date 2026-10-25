import re


DIAGNOSTIC_EXPLANATIONS = {
    "missing_skill_claimed_as_expertise": (
        "A requirement classified as missing was stated as existing candidate expertise."
    ),
    "unsupported_current_learning_activity": (
        "Current skill-learning activity was stated without support in candidate evidence."
    ),
    "listed_skill_upgraded_to_expertise": (
        "A resume-listed skill was described as hands-on experience without supporting project or experience evidence."
    ),
    "unsupported_numeric_claim": (
        "A numeric achievement or quantity was absent from the supplied candidate evidence."
    ),
    "unsupported_claim_marker": (
        "A claim matched a configured unsupported-claim marker without matching candidate evidence."
    ),
    "project_claim_low_evidence_overlap": (
        "A project-related claim had insufficient wording overlap with the selected project evidence."
    ),
    "unsupported_project_detail_claim": (
        "A specific project implementation detail was not present in the candidate evidence."
    ),
    "unverified_known_skill": (
        "A known technical skill appeared without support in matched, listed, or project evidence."
    ),
    "unrecognized_named_project": (
        "A named project or product type was not present in the selected project evidence."
    ),
    "unsupported_job_responsibility_claim": (
        "A job responsibility was phrased as completed candidate experience without matching candidate evidence."
    ),
    "unsupported_claim_unclassified": (
        "The grounding validator rejected the output, but no specific rule classifier matched."
    ),
    "minimum_output_length": "Generated writing was shorter than the validator minimum.",
    "blocked_or_malformed_text": "Output contained a placeholder, refusal, or model-format artifact.",
    "missing_cover_letter_opening": "The cover letter did not begin with the required greeting.",
    "missing_cover_letter_signature": "The cover letter did not include a closing signature.",
    "placeholder_signature": "The cover letter used a generic placeholder signature.",
    "output_word_limit": "Generated writing exceeded the validator word limit.",
}


EVIDENCE_CATEGORIES = {
    "missing_skill_claimed_as_expertise": "missing_requirement",
    "unsupported_current_learning_activity": "current_learning_activity",
    "listed_skill_upgraded_to_expertise": "listed_skill_and_demonstrated_experience",
    "unsupported_numeric_claim": "achievement_or_metric",
    "unsupported_claim_marker": "candidate_claim",
    "project_claim_low_evidence_overlap": "project_description",
    "unsupported_project_detail_claim": "project_implementation_detail",
    "unverified_known_skill": "skill_evidence",
    "unrecognized_named_project": "project_identity",
    "unsupported_job_responsibility_claim": "job_responsibility",
    "unsupported_claim_unclassified": "candidate_evidence",
    "minimum_output_length": "output_structure",
    "blocked_or_malformed_text": "output_quality",
    "missing_cover_letter_opening": "cover_letter_format",
    "missing_cover_letter_signature": "cover_letter_format",
    "placeholder_signature": "cover_letter_format",
    "output_word_limit": "output_length",
}


def validation_diagnostic(writer: str, rule_id: str) -> dict:
    """Return a safe rule diagnostic without including output or evidence values."""
    return {
        "writer": writer,
        "rejected_rule_id": rule_id,
        "evidence_category": EVIDENCE_CATEGORIES[rule_id],
        "safe_explanation": DIAGNOSTIC_EXPLANATIONS[rule_id],
    }


def normalized_claim_tokens(text: str) -> set[str]:
    aliases = {
        "built": "build", "developed": "build", "created": "build", "designed": "build", "implemented": "build",
        "classified": "classify", "classification": "classify", "classifies": "classify",
        "detected": "detect", "detection": "detect", "identifies": "identify", "identified": "identify",
        "analyzed": "analyze", "analysis": "analyze", "monitored": "monitor", "monitoring": "monitor",
        "tracked": "track", "tracking": "track", "urls": "url", "emails": "email",
    }
    return {aliases.get(token, token) for token in re.findall(r"[a-z0-9]+", text.lower())}


def rank_projects(projects: list[dict], relevance_terms: set[str], limit: int = 2) -> list[dict]:
    """Rank project evidence by deterministic text overlap, preserving resume order on ties."""
    terms = {term.lower().strip() for term in relevance_terms if term and term.strip()}
    term_tokens = {token for term in terms for token in re.findall(r"[a-z0-9+#.]+", term)}

    def score(project: dict) -> int:
        text = " ".join(
            str(value or "")
            for value in (
                project.get("name"),
                project.get("description"),
                *(project.get("technologies", []) if isinstance(project.get("technologies"), list) else []),
            )
        ).lower()
        tokens = set(re.findall(r"[a-z0-9+#.]+", text))
        phrase_hits = sum(2 for term in terms if len(term.split()) > 1 and term in text)
        return len(tokens & term_tokens) + phrase_hits

    indexed = list(enumerate(projects))
    indexed.sort(key=lambda item: (-score(item[1]), item[0]))
    return [project for _, project in indexed[:limit]]


def build_writer_evidence_ledger(evidence: dict, resume_profile: dict | None = None) -> dict:
    """Shape source facts into compact, clearly separated prompt evidence."""
    resume_profile = resume_profile if isinstance(resume_profile, dict) else {}
    candidate = evidence.get("candidate", {}) if isinstance(evidence, dict) else {}
    candidate = candidate if isinstance(candidate, dict) else {}

    def strings(value, limit=None):
        values = [value] if isinstance(value, str) else value if isinstance(value, list) else []
        result = list(dict.fromkeys(str(item).strip() for item in values if isinstance(item, str) and item.strip()))
        return result[:limit] if limit is not None else result

    goal_values = []
    for key in (
        "candidate_stated_goals", "stated_goals", "career_goal", "career_goals",
        "career_objective", "professional_goal", "professional_goals", "goals",
    ):
        goal_values.extend(strings(resume_profile.get(key)))
    goals = list(dict.fromkeys(goal_values))[:4]

    education = str(candidate.get("education") or "").strip()
    if education.lower() in {"my academic background", "academic background"}:
        education = ""

    projects = []
    for index, project in enumerate(evidence.get("projects", []) or [], start=1):
        if not isinstance(project, dict):
            continue
        name = str(project.get("name") or "").strip()
        description = str(project.get("description") or "").strip()
        technologies = strings(project.get("technologies"))
        if name or description or technologies:
            projects.append({
                "id": f"P{index}",
                "name": name,
                "description": description,
                "technologies": technologies,
            })

    experience = [
        fact for fact in strings(candidate.get("experience"), 3)
    ]
    listed_skills = strings(evidence.get("listed_skills"), 8)
    stated_goals = [
        {"id": f"G{index}", "goal": goal}
        for index, goal in enumerate(goals, start=1)
    ]
    job_context = evidence.get("job_context", {})
    job_context = job_context if isinstance(job_context, dict) else {}
    candidate_evidence = {
        "candidate": {
            "name": str(candidate.get("name") or "").strip(),
            "education": education,
            "experience": experience,
        },
        "projects": projects,
        "listed_skills": listed_skills,
        "candidate_stated_goals": stated_goals,
    }
    ledger = {
        "candidate_evidence": candidate_evidence,
        "job_context": {
            "role_title": str(job_context.get("role_title") or "").strip(),
            "company_name": str(job_context.get("company_name") or "").strip(),
            "responsibilities": strings(job_context.get("responsibilities"), 3),
            "missing_requirements": strings(job_context.get("missing_requirements"), 6),
            "related_requirements": strings(job_context.get("related_requirements"), 5),
        },
    }
    ledger["candidate_factual_anchors"] = build_candidate_factual_anchors(
        candidate_evidence,
        strings(evidence.get("matched_skills"), 8),
    )
    return ledger


def build_candidate_factual_anchors(candidate_evidence: dict, relevant_skills: list[str] | None = None) -> dict:
    """Return compact, category-separated candidate facts selected for relevance."""
    candidate = candidate_evidence.get("candidate", {}) if isinstance(candidate_evidence, dict) else {}
    candidate = candidate if isinstance(candidate, dict) else {}
    anchors = {}
    project_anchors = []
    for project in candidate_evidence.get("projects", []) or []:
        if not isinstance(project, dict):
            continue
        name = str(project.get("name") or "").strip()
        description = str(project.get("description") or "").strip()
        technologies = list(dict.fromkeys(
            str(value).strip()
            for value in project.get("technologies", []) or []
            if isinstance(value, str) and value.strip()
        ))
        if description or technologies:
            project_anchor = {"project": name}
            if description:
                project_anchor["fact"] = description
            if technologies:
                project_anchor["technologies"] = technologies
            project_anchors.append(project_anchor)
    if project_anchors:
        anchors["project_work"] = project_anchors

    listed = candidate_evidence.get("listed_skills", []) or []
    listed_by_normalized = {
        str(skill).strip().casefold(): str(skill).strip()
        for skill in listed
        if isinstance(skill, str) and skill.strip()
    }
    relevant_order = list(dict.fromkeys(
        str(skill).strip().casefold()
        for skill in (relevant_skills or [])
        if isinstance(skill, str) and skill.strip()
    ))
    selected_skills = [listed_by_normalized[key] for key in relevant_order if key in listed_by_normalized]
    if selected_skills:
        anchors["listed_skills"] = selected_skills

    name = str(candidate.get("name") or "").strip()
    education = str(candidate.get("education") or "").strip()
    experience_facts = [
        str(fact).strip()
        for fact in candidate.get("experience", []) or []
        if isinstance(fact, str) and fact.strip()
    ]
    goals = [
        str(goal.get("goal") or "").strip()
        for goal in candidate_evidence.get("candidate_stated_goals", []) or []
        if isinstance(goal, dict) and str(goal.get("goal") or "").strip()
    ]
    if name:
        anchors["identity"] = name
    if education:
        anchors["education"] = education
    if experience_facts:
        anchors["experience"] = experience_facts
    if goals:
        anchors["stated_goals"] = goals
    return anchors


def evidence_ledger_ids(ledger: dict) -> set[str]:
    """Return the IDs actually present in a ledger; useful for local reference checks."""
    ids = set()
    candidate = ledger.get("candidate_evidence", {}) if isinstance(ledger, dict) else {}
    candidate = candidate if isinstance(candidate, dict) else {}
    for key in ("projects", "candidate_stated_goals"):
        for item in candidate.get(key, []) or []:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                ids.add(item["id"])
    return ids


def has_unsupported_skill_claims(text: str, evidence: dict) -> bool:
    return bool(diagnose_unsupported_skill_claims(text, evidence))


def diagnose_unsupported_skill_claims(text: str, evidence: dict) -> list[str]:
    """Return every applicable skill-grounding rule ID."""
    lowered = text.lower()
    missing = [str(skill).strip() for skill in evidence.get("unsupported_skills", []) or [] if str(skill).strip()]
    candidate = evidence.get("candidate", {}) or {}
    demonstrated_parts = []
    for project in evidence.get("projects", []) or []:
        if isinstance(project, dict):
            demonstrated_parts.extend((project.get("description", ""), *(project.get("technologies", []) or [])))
    demonstrated_parts.extend(candidate.get("experience", []) or [])
    demonstrated = " ".join(str(part) for part in demonstrated_parts).lower()
    rule_ids = []
    for skill in missing:
        for match in _skill_occurrences(lowered, skill):
            context = lowered[max(0, match.start() - 110):match.start()]
            if re.search(r"\bactively\s+learning\s+$", context):
                if not re.search(rf"\bactively\s+learning\s+{re.escape(skill.lower())}\b", demonstrated):
                    rule_ids.append("unsupported_current_learning_activity")
            elif not _is_negated_or_future_learning_context(context):
                rule_ids.append("missing_skill_claimed_as_expertise")

    expertise_patterns = (
        r"\b(?:experience|expertise|proficiency|proficient|skilled|knowledge)\s+(?:in|with|of)\s+$",
        r"\b(?:used|applied|built|developed|implemented|worked with|hands-on with)\s+$",
    )
    for skill in evidence.get("listed_skills", []) or []:
        skill = str(skill).strip()
        if not skill:
            continue
        for match in re.finditer(rf"(?<![a-z0-9]){re.escape(skill.lower())}(?![a-z0-9])", lowered):
            context = lowered[max(0, match.start() - 55):match.start()]
            if any(re.search(pattern, context) for pattern in expertise_patterns):
                if not re.search(rf"(?<![a-z0-9]){re.escape(skill.lower())}(?![a-z0-9])", demonstrated):
                    rule_ids.append("listed_skill_upgraded_to_expertise")
    return list(dict.fromkeys(rule_ids))


def _skill_occurrences(text: str, skill: str):
    patterns = [rf"(?<![a-z0-9]){re.escape(skill.lower())}(?![a-z0-9])"]
    if skill.strip().lower() == "aws":
        patterns.extend((r"\bcloud services\b", r"\bcloud platforms?\b", r"\bcloud deployment\b"))
    matches = [match for pattern in patterns for match in re.finditer(pattern, text)]
    return sorted(matches, key=lambda match: (match.start(), match.end()))


def _is_negated_or_future_learning_context(context: str) -> bool:
    patterns = (
        r"\b(?:no|not|never|without)\s+(?:\w+\s+){0,3}(?:experience|proficiency|expertise|knowledge)\s+(?:in|with|of)\s+$",
        r"\b(?:not|never)\s+(?:proficient|skilled|experienced)\s+(?:in|with|at)\s+$",
        r"\b(?:not|never)\s+familiar\s+with\s+$",
        r"\b(?:have|has|had)\s+(?:not|never)\s+(?:yet\s+)?(?:worked|used|built|developed|applied)\s+(?:with|in|on)\s+$",
        r"\b(?:would like|would love|hope|want|aim|plan|intend|eager|keen)\s+(?:to\s+)?learn\s+$",
        r"\binterested\s+in\s+learning\s+$",
        r"\blooking\s+forward\s+to\s+learning\s+$",
        r"\b(?:learning|learn|exploring|building familiarity with|developing familiarity with)\s+$",
    )
    if re.search(r"\bactively\s+learning\s+$", context):
        return False
    return any(re.search(pattern, context) for pattern in patterns)


def is_learning_or_negated_skill_mention(text: str, skill: str) -> bool:
    lowered = text.lower()
    matches = _skill_occurrences(lowered, skill)
    if not matches:
        return False
    for match in matches:
        context = lowered[max(0, match.start() - 110):match.start()]
        if not _is_negated_or_future_learning_context(context):
            return False
    return True


def has_unsupported_numeric_claims(text: str, evidence: dict) -> bool:
    source_parts = []
    for key in ("candidate", "projects", "demonstrated_experience", "listed_skills", "transferable_experience"):
        source_parts.append(str(evidence.get(key, "")))
    source_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", " ".join(source_parts)))
    for number in re.findall(r"\b\d+(?:\.\d+)?%?\b", text):
        if number not in source_numbers:
            return True
    return False


def has_unsupported_project_detail_claims(text: str, evidence: dict) -> bool:
    """Catch specific implementation features that generic project overlap misses."""
    candidate = evidence.get("candidate", {}) or {}
    projects = [project for project in evidence.get("projects", []) or [] if isinstance(project, dict)]
    project_sources = [
        " ".join(str(part or "") for part in (project.get("description", ""), *(project.get("technologies", []) or []))).lower()
        for project in projects
    ]
    all_source = " ".join([
        str(candidate.get("experience", "")),
        str(evidence.get("demonstrated_experience", "")),
        *project_sources,
    ]).lower()
    output = (text or "").lower()

    detail_checks = (
        (r"\b(?:unit|integration|end[- ]to[- ]end|automated)?\s*tests?\b|\btest suites?\b", r"\b(?:unit|integration|end[- ]to[- ]end|automated)?\s*tests?\b|\btest suites?\b"),
        (r"\b(?:error|exception) handling\b", r"\b(?:error|exception) handling\b"),
        (r"\b(?:real[- ]time|in real time|live updates?)\b", r"\b(?:real[- ]time|in real time|live updates?)\b"),
        (r"\bproduction[- ]grade\b|\bin production\b|\bdeployed\b|\bdeployment\b", r"\bproduction[- ]grade\b|\bin production\b|\bdeployed\b|\bdeployment\b"),
        (r"\b(?:hands[- ]on practice|experience)\b[^.!?]{0,70}\bdocumenting\b|\b(?:i|we)\s+(?:wrote|created|prepared|maintained|documented)\b[^.!?]{0,55}\b(?:documentation|docs|endpoints?|project|system|code)\b", r"\b(?:documented|documenting|documentation|docs)\b"),
        (r"\b(?:improved|increased|reduced|optimized|accelerated|boosted)\b[^.!?]{0,60}\b(?:performance|speed|latency|response time|efficiency)\b|\b(?:faster|more reliable)\b", r"\b(?:improved|increased|reduced|optimized|accelerated|boosted|faster|more reliable)\b[^.!?]{0,60}\b(?:performance|speed|latency|response time|efficiency)\b"),
    )
    for paragraph in re.split(r"\n\s*\n", output):
        current_project_index = None
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            for index, project in enumerate(projects):
                name = str(project.get("name") or "").strip().lower()
                if name and re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", sentence):
                    current_project_index = index
                    break
            source = project_sources[current_project_index] if current_project_index is not None else all_source
            for index, (claim_pattern, evidence_pattern) in enumerate(detail_checks):
                if re.search(claim_pattern, sentence) and not re.search(evidence_pattern, source):
                    # Future learning goals do not assert that deployment work is completed.
                    if index == 3 and re.search(r"\b(?:eager|want|would like|hope|plan)\b[^.!?]{0,45}\blearn\b", sentence):
                        continue
                    return True
            if not re.search(r"\b(?:api|endpoint)s?\b", sentence):
                continue
            operations = re.findall(r"\b(?:creat\w*|updat\w*|retriev\w*|delet\w*|read\w*)\b", sentence)
            if operations and any(not re.search(rf"\b{re.escape(operation[:5])}\w*\b", source) for operation in operations):
                return True
            if re.search(r"\bcrud\b", sentence) and not re.search(r"\bcrud\b", source):
                return True
    return False
