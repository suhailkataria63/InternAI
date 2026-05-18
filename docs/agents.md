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
- Detects resume sections including `SUMMARY`, `SUMMARY OF QUALIFICATIONS`, `PROJECTS`, `RELEVANT PROJECT EXPERIENCE`, `TECHNICAL SKILLS`, `EDUCATION`, and `CERTIFICATIONS`.
- Extracts email and phone with regular expressions.
- Extracts candidate name from `Name:` labels, first meaningful lines, and phrases such as `I am...`, `My name is...`, and `Suhail Kataria is pursuing...`.
- Avoids using degree names, project names, section headings, and skill names as candidate names.
- Detects education from section headings and paragraph keywords such as `B.Tech`, `Bachelor`, `Artificial Intelligence`, `Data Science`, `AI&DS`, `3rd Year`, `6th Semester`, `CGC Landran`, `Chandigarh Group of Colleges`, and `IKGPTU`.
- Cleans education entries by reading the `EDUCATION` section first and stopping before resume-content phrases such as `Skills include`, `Projects include`, `Another project`, `Experience includes`, `TECHNICAL SKILLS`, and `SUMMARY OF QUALIFICATIONS`, then caps long education entries before they reach writer agents.
- Detects expanded technical skills including Python, JavaScript, TypeScript, React, Next.js, Node.js, FastAPI, Django, Flask, Machine Learning, Deep Learning, NLP, SQL, PostgreSQL, SQLite, Pandas, NumPy, Scikit-learn, TensorFlow, PyTorch, LangChain, LangGraph, CrewAI, RAG, AI Agents, Docker, Git, GitHub, REST API, Tailwind CSS, HTML, and CSS.
- Normalizes common skill variants such as `React.js` to `React`, `Scikit-Learn` to `Scikit-learn`, `TensorFlow/Keras` to `TensorFlow` and `Keras`, `Exploratory Data Analysis (EDA)` to `EDA`, and `Natural Language Processing` to `NLP`.
- Extracts projects from `PROJECTS` and `RELEVANT PROJECT EXPERIENCE` sections while ignoring section headings, dates, skills categories, education lines, contact lines, and summary paragraphs.
- Uses project-title heuristics so short title-like lines such as `Hybrid Phishing Detection System`, `Demand Forecasting using Time Series Analysis`, `YouTube View Prediction Model`, and `Deep Learning Sentiment Analysis Model` become project names.
- Associates following bullet or description lines with the best matching project using project keywords and title overlap.
- Handles PDF extraction order issues by attaching opening project-like lines to a matching project title when the PDF text begins with project bullets before the candidate header.
- Returns projects as structured objects with `name`, `description`, and `technologies`.
- Extracts experience only from explicit `EXPERIENCE`, `WORK EXPERIENCE`, `INTERNSHIP`, or `INTERNSHIPS` sections so project bullets do not become fake work experience.
- Extracts certifications from certification-related keywords and providers such as Coursera, Udemy, Google, Microsoft, IBM, AWS, and EC-Council.
- Builds strengths and improvement areas based on actual extracted profile evidence.
- Stores an LLM-ready prompt template for future LangChain or LangGraph integration.

Current limitations:

- The agent is rule-based and does not deeply understand resume context yet.
- Name detection works best when the candidate name appears near the top of the resume.
- Skills are detected from a curated keyword list and may miss uncommon tools.
- Section-aware extraction is stronger than before, but unusual resume layouts can still produce partial results.
- Project descriptions are inferred from nearby text and may need human cleanup.
- PDF extraction order can vary by resume design; the analyzer applies cleanup heuristics, but users may still edit extracted text before analysis.
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
- Extracts clean role titles from labels such as `Role` and `Position`, and from phrases such as `As an Artificial Intelligence (AI) Intern at COMPANY`, `hiring an AI/ML Intern`, `hiring for AI/ML Intern`, `applying for the X role`, and `AI/ML Intern for 6 months`.
- Cleans role titles by removing trailing work-mode/duration/context phrases and rejecting noisy matches such as `deployment experience`, `the internship`, `required skills`, `responsibilities`, `candidate should`, and `selected intern`.
- Extracts company name from labels such as `Company`, from `About HEXACARE PHARMACEUTICALS PVT LTD`, uppercase company blocks, common suffixes such as `PVT LTD`, `Private Limited`, `Ltd`, `LLP`, `Inc`, and from `at Example AI Startup`.
- Uses a centralized skill dictionary covering frontend, backend, AI/ML, data, API, Git, Docker, and soft-skill terms.
- Treats skills as required only when they appear near required phrases such as `required skills`, `must have`, `mandatory`, `candidate should have`, `should know`, `need experience in`, or `strong knowledge of`.
- Treats skills as preferred only when they appear near preferred phrases such as `preferred skills`, `good to have`, `nice to have`, `bonus`, `plus`, `preferred qualifications`, `additional skills`, or `familiarity with`.
- Keeps skills that appear only in preferred sections out of `required_skills`; when a skill appears in both places, it remains required and is removed from preferred.
- Falls back to whole-description skill extraction only when no explicit required skill context exists.
- Extracts responsibilities from sections and phrases such as `responsibilities include`, `selected intern's day-to-day responsibilities include`, `you will`, `work on`, and `tasks include`.
- Extracts eligibility from lines mentioning students, candidates, degree, year, semester, availability, relevant skills, or interests.
- Keeps responsibilities, eligibility, and perks separated where recognizable section headings are present.
- Extracts stipend, duration, and location from labeled fields or common inline patterns, including unpaid roles and rupee/INR stipends.
- Detects work mode as `Remote`, `Work From Home`, `Hybrid`, `On-site`, or `Not specified`.
- Builds keywords from role title tokens, required skills, preferred skills, work mode, and responsibility terms.
- Stores an LLM-ready prompt template for future LangChain or LangGraph integration.

Current limitations:

- The agent is rule-based and works best with reasonably formatted job descriptions.
- Company and role extraction may be incomplete when descriptions use unusual formatting.
- Skills are detected from a curated keyword dictionary and may miss uncommon tools.
- Required and preferred separation depends on recognizable wording around skill lists.
- Responsibilities and eligibility may need cleanup for very long paragraph-style descriptions.
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
  "recommendation": "",
  "score_breakdown": {},
  "required_skill_match_percentage": 0,
  "preferred_skill_match_percentage": 0,
  "matched_required_skills": [],
  "missing_required_skills": [],
  "matched_preferred_skills": [],
  "missing_preferred_skills": []
}
```

Scoring formula:

- Required skill match: 45 points
- Preferred skill match: 15 points
- Project relevance: 20 points
- Education and role relevance: 10 points
- Experience and certifications: 10 points

Match levels:

- 85-100: Excellent Fit
- 70-84: Strong Fit
- 50-69: Good Fit
- 30-49: Partial Fit
- 0-29: Weak Fit

Internal logic:

- Normalizes resume skills and job skills for case-insensitive comparison.
- Normalizes resume skills and job skills into canonical display names before scoring.
- Supports synonym matching such as `AI` and `Artificial Intelligence`, `ML` and `Machine Learning`, `NLP` and `Natural Language Processing`, `React.js` and `React`, `NextJS` and `Next.js`, `REST APIs` and `REST API`, `Scikit-Learn` and `Scikit-learn`, plus common casing fixes such as `JavaScript`, `TypeScript`, `LangChain`, and `REST API`.
- Keeps exact required-skill matching conservative: `TypeScript` does not automatically satisfy `JavaScript`, `GitHub` does not automatically satisfy `Git`, and `FastAPI` does not automatically satisfy `REST API`.
- Uses related evidence only for project relevance notes, such as treating FastAPI as backend API evidence when the JD asks for REST API experience.
- Treats frontend/backend category skills as relevant to concrete skills such as React, Next.js, FastAPI, Django, and Flask.
- Scores required skills separately from preferred skills and returns separate matched/missing lists for each group.
- Preserves JD skill order in matched and missing required/preferred lists while removing duplicates.
- Gives a neutral 25/45 required-skill score when the job description has no explicit required skills.
- Gives full preferred-skill points when no preferred skills are listed because preferred skills are optional.
- Checks resume project names, descriptions, and technologies against required skills, preferred skills, responsibilities, role title, and domain terms such as AI, ML, backend, frontend, API, dashboard, data, model, NLP, RAG, agent, and deployment.
- Scores education using B.Tech, Bachelor, Computer Science, AI, Data Science, Machine Learning, Engineering, degree/year, and eligibility overlap.
- Scores experience and certifications using internship, AI/ML, data, software/development, and certification evidence.
- Generates practical recommendations based on score level, missing required skills, missing preferred skills, and project evidence.

Current limitations:

- The score is deterministic and transparent, but not yet based on learned hiring outcomes.
- Project relevance uses keyword overlap, so it may miss deeper semantic similarity.
- Missing skills are based on the resume `skills` list, even when a skill appears only inside a project description.
- Alias matching is intentionally conservative; for example, `DB` does not automatically match SQL.

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
- Selects the best education entry, preferring `B.Tech`, `BTech`, `Bachelor`, `B.E`, engineering, AI, data science, computer science, degree, and currently pursuing signals over `Diploma` or `Class X`.
- Extracts a clean target role, matched skills, relevant projects, and learning focus.
- Converts structured project objects into concise writing summaries using the project name, the strongest evidence sentence, and the top technologies.
- Uses the top two projects and top four to five matched skills so answers stay readable.
- Frames missing skills as active learning or improvement areas instead of mastered skills.
- Keeps `key_points_used` concise with education, target role, company when available, matched skills, project names, and learning focus.
- Falls back to `this internship` when the role title is empty or suspicious.
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
- Mentions target role, company when available, best education summary, matched skills, relevant projects, and experience when available.
- Handles missing company names gracefully in the subject line and opening sentence.
- Avoids treating `Class X` as current education when a stronger degree such as `B.Tech` or `Bachelor` is present.
- Converts long project descriptions into concise evidence and keeps project names in `key_points_used`.
- Uses a clean professional format: opening/background paragraph, project-relevance paragraph, learning-gap paragraph, and polite closing.
- Falls back to `the internship role` when the role title is empty or suspicious.
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
