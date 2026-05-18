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
- Extracts candidate name from `Name:` labels, first meaningful lines, and phrases such as `I am...`, `My name is...`, and `Suhail Kataria is pursuing...`.
- Avoids using degree names, project names, section headings, and skill names as candidate names.
- Detects education from section headings and paragraph keywords such as `B.Tech`, `Bachelor`, `Artificial Intelligence`, `Data Science`, `AI&DS`, `3rd Year`, `6th Semester`, `CGC Landran`, `Chandigarh Group of Colleges`, and `IKGPTU`.
- Detects expanded technical skills including Python, JavaScript, TypeScript, React, Next.js, Node.js, FastAPI, Django, Flask, Machine Learning, Deep Learning, NLP, SQL, PostgreSQL, SQLite, Pandas, NumPy, Scikit-learn, TensorFlow, PyTorch, LangChain, LangGraph, CrewAI, RAG, AI Agents, Docker, Git, GitHub, REST API, Tailwind CSS, HTML, and CSS.
- Extracts projects from sections, bullet-style lines, and paragraph phrases such as `Projects include...`, `Project: ...`, and `Another project is...`.
- Returns projects as structured objects with `name`, `description`, and `technologies`.
- Extracts experience from phrases like `Experience includes AI Intern at Unified Mentor`, `AI Intern at...`, `Internship at...`, and `Worked as...`.
- Extracts certifications from certification-related keywords and providers such as Coursera, Udemy, Google, Microsoft, IBM, AWS, and EC-Council.
- Builds strengths and improvement areas based on actual extracted profile evidence.
- Stores an LLM-ready prompt template for future LangChain or LangGraph integration.

Current limitations:

- The agent is rule-based and does not deeply understand resume context yet.
- Name detection works best when the candidate name appears near the top of the resume.
- Skills are detected from a curated keyword list and may miss uncommon tools.
- Paragraph extraction is stronger than before, but unusual grammar can still produce partial results.
- Project descriptions are inferred from nearby text and may need human cleanup.
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

## Skill Gap Agent

Purpose: Convert the match result into a prioritized learning roadmap, resume improvement suggestions, and recommended mini-projects.

Input:

```json
{
  "resume_profile": {},
  "job_profile": {},
  "match_result": {
    "match_score": 72,
    "match_level": "Good Fit",
    "matched_skills": [],
    "missing_skills": ["SQL", "Docker"],
    "project_relevance_notes": [],
    "recommendation": ""
  }
}
```

Output:

```json
{
  "target_role": "",
  "priority_skills": [],
  "learning_roadmap": [],
  "resume_improvement_suggestions": [],
  "recommended_projects": [],
  "overall_advice": ""
}
```

Internal logic:

- Reads `missing_skills` from the Match Scoring Agent output.
- Compares each missing skill against `job_profile.required_skills` and `job_profile.preferred_skills`.
- Marks required missing skills as `High` priority.
- Marks preferred missing skills as `Medium` priority.
- Marks uncategorized missing skills as `Low` priority.
- Generates learning tasks and estimated learning time for each skill.
- Builds a week-by-week roadmap ordered by priority.
- Suggests resume improvements based on missing skills, project evidence, experience, and target role.
- Recommends mini-projects that can prove missing skills in a recruiter-friendly way.

Current limitations:

- The agent is rule-based and does not yet personalize based on user schedule or learning style.
- Learning time estimates are simple defaults by priority.
- Mini-project recommendations are generated from skill gaps and role title, not from a full project catalog.

Future LLM upgrade:

- Use an LLM to create more personalized learning plans.
- Generate role-specific project briefs with milestones.
- Convert roadmap items into calendar tasks.
- Suggest exact resume bullet rewrites after the project is completed.

## Application Writer Agent

Purpose: Generate customized internship application answers from the candidate profile, job profile, match result, skill gap result, and a specific application question.

Input:

```json
{
  "resume_profile": {},
  "job_profile": {},
  "match_result": {},
  "skill_gap_result": {},
  "application_question": "Why should we hire you?",
  "tone": "professional",
  "word_limit": 180
}
```

Output:

```json
{
  "question": "",
  "generated_answer": "",
  "key_points_used": [],
  "tone": "",
  "word_count": 0,
  "improvement_note": ""
}
```

Question types:

- `why_hire`
- `why_interested`
- `relevant_experience`
- `cover_message`
- `general`

Tone options:

- `professional`
- `confident`
- `friendly`
- `concise`

Internal logic:

- Detects the application question type from simple keyword patterns.
- Extracts candidate education, target role, matched skills, relevant projects, and learning focus.
- Selects a template based on the question type.
- Mentions missing skills only as learning goals, not mastered skills.
- Applies a simple tone transformation.
- Trims the answer to the requested word limit when possible.
- Returns the answer with key points used, word count, and an improvement note.

Current limitations:

- The agent is template-based and may sound repetitive across many applications.
- Tone control is intentionally simple.
- Company-specific personalization depends on the details included in `job_profile`.
- It does not yet rewrite the answer based on recruiter feedback.

Future LLM upgrade:

- Use an LLM to generate more natural and varied application answers.
- Add stricter factual grounding checks.
- Support multiple answer drafts for the same question.
- Generate cover letters and short recruiter messages from the same context.

## Cover Letter Agent

Purpose: Generate a customized internship cover letter using resume, job, match, and skill-gap context.

Input:

```json
{
  "resume_profile": {},
  "job_profile": {},
  "match_result": {},
  "skill_gap_result": {},
  "tone": "professional",
  "length": "short"
}
```

Output:

```json
{
  "cover_letter": "",
  "subject_line": "",
  "opening_summary": "",
  "key_points_used": [],
  "tone": "",
  "word_count": 0
}
```

Supported tones:

- `professional`
- `confident`
- `friendly`
- `concise`

Supported lengths:

- `short`: approximately 120-180 words
- `medium`: approximately 180-260 words

Internal logic:

- Builds a subject line from the target role and company.
- Starts the letter with `Dear Hiring Team,`.
- Mentions target role, company, education, matched skills, relevant projects, and experience when available.
- Mentions missing skills only as active learning areas.
- Adds a polite closing.
- Applies simple tone transformations.
- Keeps the output inside the selected length range when possible.
- Returns key points used and word count for review.

Current limitations:

- The agent is template-based and may need human editing before final submission.
- Medium length depends on the amount of available resume and job context.
- Tone options are simple transformations, not full stylistic rewrites.
- It does not yet deeply personalize for company mission or team-specific details.

Future LLM upgrade:

- Use an LLM to create more natural, varied cover letters.
- Add factual grounding checks against source profiles.
- Generate multiple cover letter versions by tone and length.
- Add company-specific personalization from richer job or company context.

## Multi-Agent Orchestrator

Purpose: Run the completed InternAI agents in sequence and return one end-to-end application analysis response.

Input:

```json
{
  "resume_text": "...",
  "job_description": "...",
  "application_question": "Why should we hire you?",
  "tone": "professional",
  "word_limit": 180,
  "cover_letter_length": "short"
}
```

Output:

```json
{
  "resume_profile": {},
  "job_profile": {},
  "match_result": {},
  "skill_gap_result": {},
  "application_answer": {},
  "cover_letter": {},
  "pipeline_summary": {}
}
```

Agent communication:

- Resume Analyzer receives raw resume text and returns `resume_profile`.
- JD Analyzer receives raw job description text and returns `job_profile`.
- Match Scoring receives `resume_profile` and `job_profile`.
- Skill Gap receives `resume_profile`, `job_profile`, and `match_result`.
- Application Writer receives all previous outputs plus the application question.
- Cover Letter receives `resume_profile`, `job_profile`, `match_result`, and `skill_gap_result`.
- Orchestrator Service builds `pipeline_summary` from the major outputs.

Internal logic:

- Runs agents in a fixed deterministic order.
- Reuses the existing rule-based and template-based agents.
- Validates empty resume text and job description before running the pipeline.
- Reports the failing step if an agent raises an error.

Current limitations:

- The orchestrator currently runs synchronously in one request.
- It does not yet persist pipeline runs to a database.
- It does not yet support optional skipping of individual agents.

Future LLM upgrade:

- Add LangGraph orchestration for stateful agent coordination.
- Persist each pipeline run and intermediate output.
- Add retry policies and richer observability per agent step.

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
