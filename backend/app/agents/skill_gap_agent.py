import json
import re

from app.services.llm_service import LLMService


SKILL_LEARNING_TASKS = {
    "python": [
        "Review Python fundamentals, functions, data structures, and error handling.",
        "Solve 10 small scripting problems using lists, dictionaries, and files.",
        "Build one small command-line tool and document how it works.",
    ],
    "fastapi": [
        "Learn FastAPI routing, request models, response models, and validation.",
        "Create CRUD endpoints with Pydantic schemas.",
        "Add one integration test for an API endpoint.",
    ],
    "sql": [
        "Practice SELECT, WHERE, JOIN, GROUP BY, and ORDER BY queries.",
        "Design a small database schema for a real use case.",
        "Use SQL queries inside a backend API endpoint.",
    ],
    "react": [
        "Review components, props, state, effects, and form handling.",
        "Build a small dashboard screen with reusable components.",
        "Connect a React page to a backend API.",
    ],
    "docker": [
        "Learn Dockerfile basics, images, containers, and ports.",
        "Containerize a small backend application.",
        "Write a short README explaining how to run the container.",
    ],
    "aws": [
        "Review core AWS services such as IAM, S3, EC2, and Lambda.",
        "Deploy a small static or API project using a beginner-friendly AWS service.",
        "Document the deployment steps and security assumptions.",
    ],
}


def analyze_skill_gap(resume_profile: dict, job_profile: dict, match_result: dict) -> dict:
    """Create a practical learning plan from resume, job, and match score outputs."""
    rule_based_result = generate_rule_based_skill_gap(
        resume_profile=resume_profile,
        job_profile=job_profile,
        match_result=match_result,
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

    system_prompt, user_prompt = build_skill_gap_prompt(
        resume_profile=resume_profile,
        job_profile=job_profile,
        match_result=match_result,
        rule_based_result=rule_based_result,
    )
    llm_result = llm_service.generate_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.25,
        max_tokens=1400,
    )

    if llm_result.get("used_fallback"):
        return _with_generation_metadata(
            rule_based_result,
            source="rule_based",
            provider=llm_result.get("provider", llm_status.get("provider", "mock")),
            used_fallback=True,
        )

    parsed_result = parse_llm_skill_gap_json(llm_result.get("text", ""))
    parsed_result = repair_short_llm_roadmap(
        llm_data=parsed_result,
        missing_skills=_canonical_skill_list(_missing_skill_candidates(match_result)),
        target_role=job_profile.get("role_title") or "the target internship",
    )
    if not is_valid_llm_skill_gap_result(parsed_result, match_result):
        return _with_generation_metadata(
            rule_based_result,
            source="rule_based",
            provider=llm_result.get("provider", llm_status.get("provider", "mock")),
            used_fallback=True,
        )

    enhanced_result = merge_llm_skill_gap_result(rule_based_result, parsed_result)
    return _with_generation_metadata(
        enhanced_result,
        source="llm",
        provider=llm_result.get("provider", llm_status.get("provider", "")),
        used_fallback=False,
    )


def generate_rule_based_skill_gap(
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
) -> dict:
    missing_skills = match_result.get("missing_skills", [])
    required_skills = job_profile.get("required_skills", [])
    preferred_skills = job_profile.get("preferred_skills", [])

    priority_skills = []
    for skill in missing_skills:
        normalized_skill = normalize_skill(skill)
        priority = get_skill_priority(normalized_skill, required_skills, preferred_skills)
        priority_skills.append(
            {
                "skill": format_skill_display(normalized_skill),
                "priority": priority,
                "reason": _get_priority_reason(normalized_skill, priority, job_profile),
                "estimated_learning_time": get_estimated_learning_time(normalized_skill, priority),
                "learning_tasks": get_learning_tasks(normalized_skill),
            }
        )

    priority_skills = _sort_priority_skills(priority_skills)

    return {
        "target_role": job_profile.get("role_title", ""),
        "priority_skills": priority_skills,
        "learning_roadmap": generate_learning_roadmap(priority_skills),
        "resume_improvement_suggestions": generate_resume_suggestions(
            priority_skills,
            resume_profile,
            job_profile,
        ),
        "recommended_projects": generate_recommended_projects(priority_skills, job_profile),
        "overall_advice": _generate_overall_advice(priority_skills, match_result),
    }


def build_skill_gap_prompt(
    resume_profile: dict,
    job_profile: dict,
    match_result: dict,
    rule_based_result: dict,
) -> tuple[str, str]:
    missing_skills = _canonical_skill_list(_missing_skill_candidates(match_result))
    current_projects = _normalize_projects(resume_profile.get("projects", []))
    education = [
        str(item).strip()
        for item in resume_profile.get("education", [])
        if str(item).strip()
    ]

    expected_schema = {
        "priority_skills": [
            {
                "skill": "Express.js",
                "priority": "High",
                "reason": "Why this skill matters for the role.",
                "estimated_learning_time": "1-2 weeks",
                "learning_tasks": [
                    "Beginner-friendly task 1.",
                    "Beginner-friendly task 2.",
                    "Beginner-friendly task 3.",
                ],
            }
        ],
        "learning_roadmap": [
            {
                "week": 1,
                "focus": "Node.js and Express.js fundamentals",
                "skills": ["Node.js", "Express.js"],
                "tasks": [
                    "Build a basic Express server with routes and middleware.",
                    "Create REST endpoints for internship applications.",
                    "Add error handling and request validation.",
                ],
                "outcome": "A working backend API that can be linked in GitHub.",
            },
            {
                "week": 2,
                "focus": "REST API integration and debugging",
                "skills": ["REST API", "Debugging"],
                "tasks": [
                    "Design REST endpoints for internship applications.",
                    "Add request validation and error handling.",
                    "Debug API responses using logs and API testing tools.",
                ],
                "outcome": "A tested REST API with cleaner error handling.",
            },
            {
                "week": 3,
                "focus": "HTML structure and frontend connection",
                "skills": ["HTML"],
                "tasks": [
                    "Build semantic HTML pages and forms.",
                    "Connect a frontend form to a backend API.",
                    "Display API response data in the UI.",
                ],
                "outcome": "A simple frontend connected to the backend.",
            },
            {
                "week": 4,
                "focus": "Problem solving and project proof",
                "skills": ["Problem Solving"],
                "tasks": [
                    "Fix bugs and edge cases in the project.",
                    "Write a README with setup steps and screenshots.",
                    "Add resume bullets explaining the project impact.",
                ],
                "outcome": "A GitHub-ready project that proves the missing skills.",
            }
        ],
        "resume_improvement_suggestions": [
            "Add one resume bullet proving Express.js with a working API project."
        ],
        "recommended_projects": [
            {
                "title": "Express.js REST API Mini Project",
                "description": "Build a small API that manages internship applications.",
                "skills_practiced": ["Express.js", "Node.js", "REST API"],
                "expected_outcome": "A GitHub-ready backend project with documentation.",
            }
        ],
        "overall_advice": "Start with the highest priority required skills and prove them through one focused mini-project.",
    }

    system_prompt = (
        "You are an internship skill gap and resume improvement assistant. "
        "Use only the provided structured data. Do not invent experience, certifications, "
        "or unrelated skills. Focus on missing skills and the target role. Return strict JSON only, "
        "with no markdown and no commentary. Keep tasks practical and beginner-friendly. "
        "Recommend projects that can be completed in 1-2 weeks. The learning_roadmap must be complete: "
        "when there are 4 or more missing skills, return 4 to 6 grouped weeks. Do not return only one week. "
        "Group related skills together and do not create one repetitive week per skill."
    )
    user_prompt = "\n".join(
        [
            f"Target role: {job_profile.get('role_title') or 'Not provided'}",
            f"Company: {job_profile.get('company_name') or 'Not provided'}",
            "Required skills: " + ", ".join(_canonical_skill_list(job_profile.get("required_skills", []))),
            "Preferred skills: " + ", ".join(_canonical_skill_list(job_profile.get("preferred_skills", []))),
            "Matched skills: " + ", ".join(_canonical_skill_list(match_result.get("matched_skills", []))),
            "Missing skills to focus on: " + (", ".join(missing_skills) or "None"),
            "Current projects: " + ("; ".join(current_projects[:4]) or "Not provided"),
            "Candidate education: " + ("; ".join(education[:3]) or "Not provided"),
            (
                "Roadmap requirements: each roadmap week must include week, focus, skills, tasks, and outcome. "
                "If there are 4 or more missing skills, learning_roadmap must contain at least 3 weeks and preferably 4 to 6 weeks. "
                "For Express.js, HTML, Node.js, Debugging, Problem Solving, and REST API, use grouped weeks like: "
                "Week 1 Node.js and Express.js fundamentals; Week 2 REST API integration and debugging; "
                "Week 3 HTML structure and frontend connection; Week 4 Problem solving and project proof."
            ),
            "Current rule-based roadmap baseline: " + json.dumps(rule_based_result, ensure_ascii=False),
            "Expected JSON schema: " + json.dumps(expected_schema, ensure_ascii=False),
        ]
    )
    return system_prompt, user_prompt


def parse_llm_skill_gap_json(text: str) -> dict | None:
    cleaned = str(text or "").strip()
    if not cleaned:
        return None

    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def is_valid_llm_skill_gap_result(result: dict | None, match_result: dict) -> bool:
    if not isinstance(result, dict):
        return False

    required_shapes = {
        "priority_skills": list,
        "learning_roadmap": list,
        "resume_improvement_suggestions": list,
        "recommended_projects": list,
        "overall_advice": str,
    }
    for key, expected_type in required_shapes.items():
        if not isinstance(result.get(key), expected_type):
            return False

    allowed_skills = {
        normalize_skill(skill) for skill in _missing_skill_candidates(match_result)
    }
    if not allowed_skills:
        return True
    if not result.get("priority_skills") or not result.get("learning_roadmap"):
        return False
    if len(allowed_skills) >= 4 and len(result.get("learning_roadmap", [])) < 3:
        return False

    for item in result.get("priority_skills", []):
        if not isinstance(item, dict):
            return False
        skill = normalize_skill(item.get("skill"))
        if skill and skill not in allowed_skills:
            return False

    roadmap_skills = []
    for week in result.get("learning_roadmap", []):
        if not isinstance(week, dict):
            return False
        roadmap_skills.extend(week.get("skills", []) or [])
    for skill in roadmap_skills:
        normalized_skill = normalize_skill(skill)
        if normalized_skill and normalized_skill not in allowed_skills:
            return False

    return True


def repair_short_llm_roadmap(
    llm_data: dict | None,
    missing_skills: list,
    target_role: str,
) -> dict | None:
    if not isinstance(llm_data, dict):
        return None

    required_shapes = {
        "priority_skills": list,
        "learning_roadmap": list,
        "resume_improvement_suggestions": list,
        "recommended_projects": list,
        "overall_advice": str,
    }
    for key, expected_type in required_shapes.items():
        if not isinstance(llm_data.get(key), expected_type):
            return llm_data

    canonical_missing_skills = _canonical_skill_list(missing_skills)
    if len(canonical_missing_skills) < 4 or len(llm_data.get("learning_roadmap", [])) >= 3:
        return llm_data

    repaired_data = dict(llm_data)
    repaired_data["learning_roadmap"] = generate_grouped_learning_roadmap(
        canonical_missing_skills,
        target_role,
    )
    return repaired_data


def merge_llm_skill_gap_result(rule_based_result: dict, llm_result: dict) -> dict:
    return {
        **rule_based_result,
        "priority_skills": _clean_priority_skills(llm_result.get("priority_skills", [])),
        "learning_roadmap": _clean_learning_roadmap(llm_result.get("learning_roadmap", [])),
        "resume_improvement_suggestions": _clean_string_list(
            llm_result.get("resume_improvement_suggestions", [])
        ),
        "recommended_projects": _clean_recommended_projects(
            llm_result.get("recommended_projects", [])
        ),
        "overall_advice": str(llm_result.get("overall_advice", "")).strip()
        or rule_based_result.get("overall_advice", ""),
    }


def generate_grouped_learning_roadmap(missing_skills: list, target_role: str) -> list[dict]:
    remaining_skills = _canonical_skill_list(missing_skills)
    roadmap: list[dict] = []

    def take_group(candidates: list[str]) -> list[str]:
        selected = [
            skill
            for skill in remaining_skills
            if normalize_skill(skill) in {normalize_skill(candidate) for candidate in candidates}
        ]
        for skill in selected:
            if skill in remaining_skills:
                remaining_skills.remove(skill)
        return selected

    backend_group = take_group(["Node.js", "Express.js"])
    if backend_group:
        roadmap.append(
            {
                "week": len(roadmap) + 1,
                "focus": "Node.js and Express.js fundamentals",
                "skills": backend_group,
                "tasks": [
                    "Set up a Node.js project.",
                    "Build an Express.js server with GET and POST routes.",
                    "Test endpoints using Postman or Thunder Client.",
                ],
                "outcome": "A working backend server with basic routes.",
            }
        )

    api_group = take_group(["REST API", "Debugging"])
    if api_group:
        roadmap.append(
            {
                "week": len(roadmap) + 1,
                "focus": "REST API integration and debugging",
                "skills": api_group,
                "tasks": [
                    "Design REST endpoints for internship applications.",
                    "Add request validation and error handling.",
                    "Debug API responses using logs and API testing tools.",
                ],
                "outcome": "A tested REST API with cleaner error handling.",
            }
        )

    frontend_group = take_group(["HTML", "CSS", "JavaScript", "React", "Next.js", "Tailwind CSS"])
    if frontend_group:
        roadmap.append(
            {
                "week": len(roadmap) + 1,
                "focus": "HTML structure and frontend integration",
                "skills": frontend_group,
                "tasks": [
                    "Build semantic HTML pages and forms.",
                    "Connect a frontend form to your backend API.",
                    "Display API response data in the UI.",
                ],
                "outcome": "A simple frontend connected to your backend.",
            }
        )

    problem_solving_group = take_group(["Problem Solving", "Communication"])
    if problem_solving_group:
        roadmap.append(
            {
                "week": len(roadmap) + 1,
                "focus": "Problem solving and project proof",
                "skills": problem_solving_group,
                "tasks": [
                    "Fix 3 bugs or edge cases in the project.",
                    "Write a README with setup steps and screenshots.",
                    "Add resume bullets explaining the project impact.",
                ],
                "outcome": "A GitHub-ready project that proves your missing skills.",
            }
        )

    for skill_group in _chunk_list(remaining_skills, 2):
        roadmap.append(
            {
                "week": len(roadmap) + 1,
                "focus": "Practice " + " and ".join(skill_group),
                "skills": skill_group,
                "tasks": [
                    f"Study the fundamentals of {', '.join(skill_group)}.",
                    f"Apply {', '.join(skill_group)} in a small {target_role} exercise.",
                    "Document what you built with screenshots and setup steps.",
                ],
                "outcome": f"Practical proof of {', '.join(skill_group)} for the target role.",
            }
        )

    if len(missing_skills) >= 4 and len(roadmap) < 3:
        roadmap = _expand_minimum_roadmap(roadmap, _canonical_skill_list(missing_skills), target_role)

    return roadmap[:6]


def normalize_skill(skill: str) -> str:
    return re.sub(r"\s+", " ", str(skill or "").strip().lower())


def format_skill_display(skill: str) -> str:
    normalized = normalize_skill(skill).replace("_", " ")
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
        "problem solving": "Problem Solving",
        "problemsolving": "Problem Solving",
    }
    return special_cases.get(normalized) or special_cases.get(compact) or str(skill).strip().title()


def get_skill_priority(skill: str, required_skills: list, preferred_skills: list) -> str:
    normalized_required = {normalize_skill(item) for item in required_skills}
    normalized_preferred = {normalize_skill(item) for item in preferred_skills}

    if skill in normalized_required:
        return "High"
    if skill in normalized_preferred:
        return "Medium"
    return "Low"


def get_learning_tasks(skill: str) -> list:
    if skill in SKILL_LEARNING_TASKS:
        return SKILL_LEARNING_TASKS[skill]

    display_skill = _display_skill(skill)
    return [
        f"Learn the fundamentals of {display_skill} from official documentation or a beginner course.",
        f"Practice {display_skill} with three small exercises.",
        f"Apply {display_skill} in a small project and write a short summary for your resume.",
    ]


def get_estimated_learning_time(skill: str, priority: str) -> str:
    if priority == "High":
        return "2-3 weeks"
    if priority == "Medium":
        return "1-2 weeks"
    return "3-5 days"


def generate_resume_suggestions(
    priority_skills: list,
    resume_profile: dict,
    job_profile: dict,
) -> list:
    suggestions = []
    projects = _normalize_projects(resume_profile.get("projects", []))

    if priority_skills:
        high_priority_skills = [
            item["skill"] for item in priority_skills if item["priority"] == "High"
        ]
        if high_priority_skills:
            suggestions.append(
                "Add evidence for required skills: " + ", ".join(high_priority_skills) + "."
            )

    if not projects:
        suggestions.append("Add at least one project that matches the target internship role.")
    else:
        suggestions.append(
            "Rewrite project bullets to mention tools, measurable outcomes, and job-relevant keywords."
        )

    if not resume_profile.get("experience"):
        suggestions.append(
            "Add internship, freelance, volunteer, leadership, or open-source experience if available."
        )

    if job_profile.get("role_title"):
        suggestions.append(
            f"Tailor the resume summary toward the target role: {job_profile['role_title']}."
        )

    return suggestions


def generate_recommended_projects(priority_skills: list, job_profile: dict) -> list:
    target_role = job_profile.get("role_title") or "target internship"
    skills = [item["skill"] for item in priority_skills]
    top_skills = skills[:3]

    if not top_skills:
        return [
            {
                "title": f"{target_role} portfolio polish",
                "description": "Improve an existing project with documentation, tests, and deployment notes.",
                "skills_practiced": [],
                "expected_outcome": "A cleaner portfolio project that is easier for recruiters to evaluate.",
            }
        ]

    joined_skills = ", ".join(top_skills)
    return [
        {
            "title": f"{target_role} mini-project",
            "description": f"Build a small project that demonstrates {joined_skills} in a realistic workflow.",
            "skills_practiced": top_skills,
            "expected_outcome": "A resume-ready project with a short README, screenshots, and clear technical bullets.",
        },
        {
            "title": "Skill proof sprint",
            "description": f"Create focused examples for each missing priority skill: {joined_skills}.",
            "skills_practiced": top_skills,
            "expected_outcome": "Small GitHub examples that prove the missing skills with working code.",
        },
    ]


def generate_learning_roadmap(priority_skills: list) -> list:
    roadmap = []
    for index, priority_skill in enumerate(priority_skills, start=1):
        roadmap.append(
            {
                "week": index,
                "focus": f"{priority_skill['priority']} priority: {priority_skill['skill']}",
                "skills": [priority_skill["skill"]],
                "tasks": priority_skill["learning_tasks"],
                "outcome": f"Show practical evidence of {priority_skill['skill']} in a project or resume bullet.",
            }
        )

    if not roadmap:
        roadmap.append(
            {
                "week": 1,
                "focus": "Application readiness",
                "skills": [],
                "tasks": [
                    "Polish existing projects.",
                    "Add measurable resume bullets.",
                    "Prepare role-specific interview examples.",
                ],
                "outcome": "A stronger application package for the target internship.",
            }
        )

    return roadmap


def _get_priority_reason(skill: str, priority: str, job_profile: dict) -> str:
    display_skill = _display_skill(skill)
    role_title = job_profile.get("role_title") or "this role"

    if priority == "High":
        return f"{display_skill} is listed as a required skill for {role_title}."
    if priority == "Medium":
        return f"{display_skill} is listed as a preferred skill for {role_title}."
    return f"{display_skill} appears in the match gap but is not categorized as required or preferred."


def _generate_overall_advice(priority_skills: list, match_result: dict) -> str:
    if not priority_skills:
        return "No major skill gaps were found. Focus on sharpening project bullets and preparing for interviews."

    high_priority_count = len([item for item in priority_skills if item["priority"] == "High"])
    match_score = match_result.get("match_score", 0)

    if high_priority_count:
        return (
            f"Your current match score is {match_score}. Start with the High priority skills first, "
            "then add a project that proves those skills in context."
        )

    return (
        f"Your current match score is {match_score}. The biggest gaps are not required skills, "
        "so focus on quick practice and resume polish."
    )


def _sort_priority_skills(priority_skills: list) -> list:
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    return sorted(priority_skills, key=lambda item: priority_order[item["priority"]])


def _display_skill(skill: str) -> str:
    return format_skill_display(skill)


def _normalize_projects(projects: list | None) -> list[str]:
    if not projects:
        return []

    normalized_projects: list[str] = []
    for project in projects:
        if isinstance(project, str):
            project_text = project.strip()
        elif isinstance(project, dict):
            project_text = _project_dict_to_text(project)
        else:
            project_text = _project_object_to_text(project)

        if project_text:
            normalized_projects.append(project_text)

    return normalized_projects


def _project_dict_to_text(project: dict) -> str:
    parts: list[str] = []

    for key in ("name", "description"):
        value = project.get(key)
        if value:
            parts.append(str(value))

    technologies = project.get("technologies", [])
    if technologies:
        parts.append(", ".join(str(technology) for technology in technologies))

    return " | ".join(parts).strip()


def _project_object_to_text(project: object) -> str:
    parts: list[str] = []

    for key in ("name", "description"):
        value = getattr(project, key, None)
        if value:
            parts.append(str(value))

    technologies = getattr(project, "technologies", [])
    if technologies:
        parts.append(", ".join(str(technology) for technology in technologies))

    return " | ".join(parts).strip()


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


def _canonical_skill_list(skills: list) -> list[str]:
    canonical_skills: list[str] = []
    for skill in skills or []:
        formatted_skill = format_skill_display(skill)
        if formatted_skill and formatted_skill.lower() not in [
            item.lower() for item in canonical_skills
        ]:
            canonical_skills.append(formatted_skill)
    return canonical_skills


def _missing_skill_candidates(match_result: dict) -> list:
    skills = []
    for key in ("missing_required_skills", "missing_preferred_skills", "missing_skills"):
        for skill in match_result.get(key, []) or []:
            if normalize_skill(skill) not in [normalize_skill(item) for item in skills]:
                skills.append(skill)
    return skills


def _clean_priority_skills(priority_skills: list) -> list[dict]:
    cleaned: list[dict] = []
    allowed_priorities = {"High", "Medium", "Low"}
    for item in priority_skills:
        if not isinstance(item, dict):
            continue
        skill = format_skill_display(item.get("skill", ""))
        if not skill:
            continue
        priority = str(item.get("priority") or "Low").strip().title()
        if priority not in allowed_priorities:
            priority = "Low"
        cleaned.append(
            {
                "skill": skill,
                "priority": priority,
                "reason": str(item.get("reason") or "").strip()
                or f"{skill} is a gap to address for the target role.",
                "estimated_learning_time": str(
                    item.get("estimated_learning_time") or get_estimated_learning_time(
                        normalize_skill(skill),
                        priority,
                    )
                ).strip(),
                "learning_tasks": _clean_string_list(item.get("learning_tasks", []))[:5]
                or get_learning_tasks(normalize_skill(skill)),
            }
        )
    return cleaned


def _clean_learning_roadmap(roadmap: list) -> list[dict]:
    cleaned: list[dict] = []
    for index, item in enumerate(roadmap, start=1):
        if not isinstance(item, dict):
            continue
        skills = _canonical_skill_list(item.get("skills", []))
        cleaned.append(
            {
                "week": _safe_int(item.get("week"), index),
                "focus": str(item.get("focus") or "Skill gap practice").strip(),
                "skills": skills,
                "tasks": _clean_string_list(item.get("tasks", []))[:5],
                "outcome": str(item.get("outcome") or "Practical proof of the focus skills.").strip(),
            }
        )
    return cleaned


def _clean_recommended_projects(projects: list) -> list[dict]:
    cleaned: list[dict] = []
    for item in projects:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        if not title or not description:
            continue
        cleaned.append(
            {
                "title": title,
                "description": description,
                "skills_practiced": _canonical_skill_list(item.get("skills_practiced", [])),
                "expected_outcome": str(
                    item.get("expected_outcome")
                    or "A small portfolio-ready project with documentation."
                ).strip(),
            }
        )
    return cleaned


def _clean_string_list(items: list) -> list[str]:
    if not isinstance(items, list):
        return []
    cleaned: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text and text.lower() not in [existing.lower() for existing in cleaned]:
            cleaned.append(text)
    return cleaned


def _safe_int(value, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _chunk_list(items: list, chunk_size: int) -> list[list]:
    return [items[index : index + chunk_size] for index in range(0, len(items), chunk_size)]


def _expand_minimum_roadmap(roadmap: list[dict], missing_skills: list, target_role: str) -> list[dict]:
    if len(roadmap) >= 3:
        return roadmap

    used_skills = {
        normalize_skill(skill)
        for week in roadmap
        for skill in week.get("skills", [])
    }
    unused_skills = [
        skill for skill in missing_skills if normalize_skill(skill) not in used_skills
    ]
    fallback_groups = _chunk_list(unused_skills or missing_skills, 1)

    for skill_group in fallback_groups:
        if len(roadmap) >= 3:
            break
        roadmap.append(
            {
                "week": len(roadmap) + 1,
                "focus": "Portfolio practice for " + " and ".join(skill_group),
                "skills": skill_group,
                "tasks": [
                    f"Build a small exercise using {', '.join(skill_group)}.",
                    f"Connect the exercise to the {target_role} responsibilities.",
                    "Add a short README and one resume bullet.",
                ],
                "outcome": f"Visible project evidence for {', '.join(skill_group)}.",
            }
        )

    return roadmap
