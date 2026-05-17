import re


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
    missing_skills = match_result.get("missing_skills", [])
    required_skills = job_profile.get("required_skills", [])
    preferred_skills = job_profile.get("preferred_skills", [])

    priority_skills = []
    for skill in missing_skills:
        normalized_skill = normalize_skill(skill)
        priority = get_skill_priority(normalized_skill, required_skills, preferred_skills)
        priority_skills.append(
            {
                "skill": _display_skill(normalized_skill),
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


def normalize_skill(skill: str) -> str:
    return re.sub(r"\s+", " ", skill.strip().lower())


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
    special_cases = {
        "aws": "AWS",
        "css": "CSS",
        "html": "HTML",
        "sql": "SQL",
        "c#": "C#",
        "c++": "C++",
        "next.js": "Next.js",
        "node.js": "Node.js",
        "fastapi": "FastAPI",
        "sqlite": "SQLite",
        "github": "GitHub",
        "gcp": "GCP",
    }
    return special_cases.get(skill, skill.title())


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
