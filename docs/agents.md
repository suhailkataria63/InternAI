# InternAI Agents

This document tracks the planned multi-agent architecture for InternAI. The agent workflow will be implemented later with LangChain or LangGraph.

## Resume Analyzer Agent

Purpose: Convert extracted resume text into a structured candidate profile that other InternAI agents can use.

Input:

```json
{
  "resume_text": "Raw text extracted from a resume PDF..."
}
```

Output:

```json
{
  "profile": {
    "name": "",
    "email": "",
    "phone": "",
    "education": [],
    "skills": [],
    "projects": [],
    "experience": [],
    "certifications": [],
    "strengths": [],
    "improvement_areas": []
  }
}
```

Internal logic:

- Normalizes raw resume text into clean lines.
- Extracts email and phone with regular expressions.
- Infers the candidate name from the first readable lines when possible.
- Detects common resume section headings such as `Education`, `Skills`, `Projects`, `Experience`, and `Certifications`.
- Extracts section content into lists.
- Detects common technical skills from the whole resume and from the skills section.
- Builds simple strengths and improvement areas based on which profile fields are present or missing.
- Stores an LLM-ready prompt template for future LangChain or LangGraph integration.

Current limitations:

- The agent is rule-based and does not deeply understand resume context yet.
- Name detection works best when the candidate name appears near the top of the resume.
- Skills are detected from a starter keyword list and may miss uncommon tools.
- Section extraction depends on recognizable headings.
- The agent does not yet score resume quality or tailor content for a specific internship.

Future improvements:

- Use an LLM to extract richer structured data.
- Add confidence scores for each field.
- Support role-specific resume scoring.
- Store parsed profiles in the database.
- Add tests with real anonymized resume examples.

## JD Analyzer Agent

Purpose: Convert pasted internship or job descriptions into structured job profiles for matching, ranking, and application planning.

Input:

```json
{
  "job_description": "Raw internship or job description text..."
}
```

Output:

```json
{
  "job_profile": {
    "role_title": "",
    "company_name": "",
    "required_skills": [],
    "preferred_skills": [],
    "responsibilities": [],
    "eligibility": [],
    "stipend": "",
    "duration": "",
    "location": "",
    "work_mode": "",
    "keywords": []
  }
}
```

Internal logic:

- Normalizes pasted job description text into clean lines.
- Extracts role title from labels such as `Role`, `Position`, `Title`, or from common title words like `Intern`, `Developer`, and `Engineer`.
- Extracts company name from labels such as `Company`, `Organization`, or `Employer`.
- Detects sections such as `Required Skills`, `Preferred Skills`, `Responsibilities`, and `Eligibility`.
- Extracts stipend, duration, and location from labeled fields or common inline patterns.
- Detects work mode as `Remote`, `Hybrid`, or `On-site`.
- Builds keywords from skills, role title, company, location, and work mode.
- Stores an LLM-ready prompt template for future LangChain or LangGraph integration.

Current limitations:

- The agent is rule-based and works best with reasonably formatted job descriptions.
- Company and role extraction may be incomplete when descriptions use unusual formatting.
- Skills are detected from a starter keyword list and explicit sections.
- The agent does not yet compare the job profile against a resume profile.

Future improvements:

- Add LLM-powered extraction for messy descriptions.
- Add confidence scores and missing-field warnings.
- Compare required skills against parsed resume skills.
- Store parsed job descriptions in the database.
- Add support for pasted job links and scraped descriptions.

## Match Scoring Agent

Purpose: Compare a parsed resume profile and parsed job profile, then calculate a deterministic internship fit score.

Input:

```json
{
  "resume_profile": {
    "skills": [],
    "projects": [],
    "education": [],
    "experience": [],
    "certifications": []
  },
  "job_profile": {
    "role_title": "",
    "required_skills": [],
    "preferred_skills": [],
    "responsibilities": [],
    "eligibility": [],
    "keywords": []
  }
}
```

Output:

```json
{
  "match_score": 78,
  "match_level": "Strong Fit",
  "matched_skills": [],
  "missing_skills": [],
  "project_relevance_notes": [],
  "recommendation": ""
}
```

Scoring formula:

- Required skill match: 50 points
- Preferred skill match: 15 points
- Project relevance: 20 points
- Education and role relevance: 10 points
- Experience and certifications: 5 points

Internal logic:

- Normalizes resume skills and job skills for case-insensitive comparison.
- Awards required skill points in proportion to matched required skills.
- Awards preferred skill points in proportion to matched preferred skills.
- Checks resume project text against job skills, keywords, role terms, and responsibilities.
- Checks whether education terms overlap with role or eligibility terms.
- Awards a small score for experience or certifications, with more weight when they overlap with job terms.
- Generates a recommendation based on missing required skills and project relevance.

Current limitations:

- The score is deterministic and transparent, but not yet based on learned hiring outcomes.
- Project relevance uses keyword overlap, so it may miss deeper semantic similarity.
- Missing skills are based on the resume `skills` list, even when a skill appears only inside a project description.

Future improvements:

- Add configurable scoring weights.
- Add semantic similarity for projects and responsibilities.
- Add role-specific scoring profiles.
- Store score history for application planning.

## Profile Agent

Purpose: Understand the user's academic background, skills, projects, interests, target roles, location preferences, and availability.

Planned responsibilities:

- Build and update the user's internship profile.
- Identify skill gaps for target roles.
- Provide structured context to other agents.

## Opportunity Agent

Purpose: Discover and rank internship opportunities based on the user's profile.

Planned responsibilities:

- Search or ingest internship listings.
- Score opportunities against user preferences.
- Explain why an opportunity is a good or poor fit.

## Resume Agent

Purpose: Help tailor resumes and application materials for specific internships.

Planned responsibilities:

- Suggest resume improvements.
- Match project experience to job requirements.
- Draft role-specific bullet points and cover letter material.

## Application Agent

Purpose: Manage the application pipeline.

Planned responsibilities:

- Track saved, applied, interviewing, rejected, and accepted statuses.
- Surface upcoming deadlines and follow-ups.
- Recommend the next best action.

## Interview Agent

Purpose: Support interview preparation.

Planned responsibilities:

- Generate practice questions.
- Create role-specific preparation plans.
- Capture mock interview feedback.

## Orchestration Placeholder

The future orchestrator will decide which agent should act, how agents share state, and when human confirmation is required before taking action.
