# InternAI

InternAI is a full-stack AI project for building a multi-agent internship assistant. The platform will help students and early-career candidates discover internship opportunities, prepare application materials, track progress, and get guided support through each stage of the internship search.

## Project Overview

InternAI is planned as a web application with a FastAPI backend, a Next.js frontend, SQLite for early local development, and a future AI workflow layer powered by LangChain or LangGraph. The first milestone is a clean foundation that can grow into a coordinated multi-agent system.

## Problem Statement

Finding and applying for internships is often fragmented. Students need to search across many sources, tailor resumes and cover letters, manage deadlines, prepare for interviews, and track communication. Without a structured system, important opportunities and follow-ups can easily be missed.

## Solution

InternAI will provide a guided assistant that organizes the internship process into clear workflows. Planned AI agents will help with opportunity discovery, profile analysis, resume tailoring, application planning, interview preparation, and progress tracking.

## Current Features

- Backend health check endpoint for local API verification.
- Resume PDF upload endpoint that extracts raw text with PyMuPDF.
- Resume Analyzer Agent that converts resume text into a structured profile without requiring an external LLM API key.
- JD Analyzer Agent that converts internship or job descriptions into structured job profiles without requiring an external LLM API key.
- Match Scoring Agent that compares resume and job profiles to calculate an internship fit score.
- Skill Gap Agent that turns missing skills into a practical learning roadmap, resume suggestions, and mini-project ideas.
- Application Writer Agent that drafts customized internship application answers without requiring an external LLM API key.
- Cover Letter Agent that generates customized internship cover letters without requiring an external LLM API key.
- Multi-Agent Orchestrator endpoint that runs the complete resume-to-application pipeline in one request.
- LLM service layer preparation with default mock mode and Groq-ready configuration for future AI upgrades.
- Next.js frontend UI for running the full orchestrator workflow from a browser.
- SQLite-backed Application Tracker for saving analyzed internships and tracking status.

## Tech Stack

- Backend: FastAPI
- Frontend: Next.js with Tailwind CSS
- Database: SQLite during initial development
- AI workflow: rule-based agents today, with an LLM provider layer prepared for future Groq, Gemini, OpenAI-compatible, LangChain, or LangGraph integration
- Documentation: Markdown files in `docs/`

## Planned Multi-Agent Architecture

InternAI will eventually use specialized agents that collaborate around the user's internship goals. Initial planned agents include:

- Profile Agent: Understands the user's skills, education, preferences, and career goals.
- JD Analyzer Agent: Understands internship descriptions, required skills, responsibilities, eligibility, and work details.
- Match Scoring Agent: Compares parsed resume and job profiles to explain fit, matched skills, and missing skills.
- Skill Gap Agent: Converts match gaps into prioritized learning actions and resume improvements.
- Application Writer Agent: Generates tailored application answers from resume, job, match, and skill-gap context.
- Cover Letter Agent: Generates role-specific cover letters from the same grounded application context.
- Multi-Agent Orchestrator: Runs all completed agents in sequence and returns one combined analysis package.
- Opportunity Agent: Finds and ranks internship opportunities.
- Resume Agent: Helps tailor resumes and application materials.
- Application Agent: Tracks applications, deadlines, and next steps.
- Interview Agent: Supports interview preparation and feedback.

See [docs/agents.md](docs/agents.md) for the working agent plan.

## Project Structure

```text
internai/
  backend/
    app/
      main.py
      config.py
      api/
      agents/
      services/
      database/
      schemas/
      utils/
    requirements.txt
    .env.example
  frontend/
    app/
    components/
    lib/
    .env.example
  docs/
    architecture.md
    agents.md
    workflow.md
    api-reference.md
  README.md
  .gitignore
```

## Setup Instructions

### Backend

```bash
cd internai/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

The backend should be available at `http://127.0.0.1:8000`.

LLM configuration is optional. By default, the backend runs in mock mode and does not require any real API key:

```env
LLM_PROVIDER=mock
LLM_MODEL=mock-model
GROQ_API_KEY=
GEMINI_API_KEY=
OPENAI_API_KEY=
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=600
```

To prepare Groq later, set `LLM_PROVIDER=groq`, choose a Groq model in `LLM_MODEL`, and add `GROQ_API_KEY`. If the key is missing or the provider request fails, InternAI returns a mock fallback response instead of crashing.

To use Gemini's free-tier-friendly API later, update `.env` like this:

```env
LLM_PROVIDER=gemini
LLM_MODEL=gemini-1.5-flash
GEMINI_API_KEY=your_gemini_api_key_here
```

If `LLM_PROVIDER=gemini` is set but `GEMINI_API_KEY` is empty, the backend still starts and `POST /api/llm/test` returns a safe fallback response.

Check the health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

Check the LLM provider layer:

```bash
curl http://127.0.0.1:8000/api/llm/status
```

Expected default response:

```json
{
  "provider": "mock",
  "model": "mock-model",
  "configured": true,
  "available": true
}
```

Test mock generation:

```bash
curl -X POST http://127.0.0.1:8000/api/llm/test \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write one sentence about InternAI."}'
```

Expected response shape:

```json
{
  "provider": "mock",
  "model": "mock-model",
  "text": "Mock LLM response: provider is not configured yet.",
  "used_fallback": true
}
```

Expected response:

```json
{
  "status": "ok",
  "project": "InternAI",
  "message": "Backend is running"
}
```

Upload a resume PDF and extract text:

```bash
curl -X POST http://127.0.0.1:8000/api/resume/upload \
  -F "file=@/path/to/resume.pdf;type=application/pdf"
```

Expected response shape:

```json
{
  "filename": "Resume.pdf",
  "text_length": 2878,
  "extracted_text": "..."
}
```

Non-PDF uploads return a clear `400 Bad Request` error.

Analyze extracted resume text:

```bash
curl -X POST http://127.0.0.1:8000/api/resume/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "resume_text": "Jane Doe\njane@example.com\n+1 555 123 4567\nSkills\nPython, FastAPI, React\nProjects\nInternship tracker app\nEducation\nB.S. Computer Science"
  }'
```

Expected response shape:

```json
{
  "profile": {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "+1 555 123 4567",
    "education": ["B.S. Computer Science"],
    "skills": ["Python", "React", "FastAPI"],
    "projects": [
      {
        "name": "Internship tracker app",
        "description": "Internship tracker app",
        "technologies": []
      }
    ],
    "experience": [],
    "certifications": [],
    "strengths": [
      "Includes a clear skills section.",
      "Highlights project experience.",
      "Includes education details."
    ],
    "improvement_areas": [
      "Add internship, work, volunteer, or leadership experience."
    ]
  }
}
```

## Resume Analyzer Agent

The Resume Analyzer Agent receives raw text, usually from the resume PDF upload endpoint, and converts it into structured JSON for future internship matching workflows.

Input: raw resume text in the `resume_text` field.

Processing: the current implementation uses improved rule-based extraction for labels, section headings, and paragraph-style text. It detects names from `Name:` labels, first meaningful lines, and phrases such as `Suhail Kataria is pursuing...`; detects resume sections such as `SUMMARY`, `RELEVANT PROJECT EXPERIENCE`, `TECHNICAL SKILLS`, `EDUCATION`, and `CERTIFICATIONS`; cleans education entries so summary paragraphs and skills categories do not flow into downstream writing; normalizes skills such as `React.js` to `React`, `Scikit-Learn` to `Scikit-learn`, `TensorFlow/Keras` to `TensorFlow` and `Keras`, `Natural Language Processing` to `NLP`, and `Exploratory Data Analysis (EDA)` to `EDA`; and returns projects as structured objects with `name`, `description`, and `technologies`.

Project extraction now prefers the projects section, ignores section headings such as `RELEVANT PROJECT EXPERIENCE`, avoids treating summary paragraphs as projects, and can attach opening PDF-extracted project bullets to the matching project title when PDF layout order places descriptions before the header. Experience extraction is intentionally conservative: if no `EXPERIENCE` or `WORK EXPERIENCE` section exists, it does not create fake work experience from project bullets.

Output: a normalized `profile` object that can be reused by future Profile, Opportunity, Resume, and Interview agents.

Example extracted resume profile:

```json
{
  "name": "Suhail Kataria",
  "education": [
    "B.Tech — Artificial Intelligence & Data Science, Chandigarh Group of Colleges (CGC), Landran Currently Pursuing",
    "Diploma — Computer Science & Engineering, PSBTE",
    "Class X — CBSE"
  ],
  "skills": ["Python", "React", "Next.js", "Machine Learning", "NLP", "EDA", "SQL"],
  "projects": [
    {
      "name": "Hybrid Phishing Detection System",
      "description": "Developed a phishing detection model (94% accuracy) using hybrid AI and ML approaches. Built a frontend dashboard using Next.js, React, TypeScript, and Tailwind CSS.",
      "technologies": ["Python", "Machine Learning", "AI", "Next.js", "React", "TypeScript", "Tailwind CSS"]
    },
    {
      "name": "Demand Forecasting using Time Series Analysis",
      "description": "Built a time-series forecasting model to predict future demand trends.",
      "technologies": ["Python", "Time-Series Forecasting", "Machine Learning", "EDA", "Feature Engineering"]
    }
  ],
  "experience": [],
  "certifications": ["AI Agent Developer - Vanderbilt University", "Generative AI Leader - Google"]
}
```

Analyze an internship or job description:

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "job_description": "Role: Software Engineering Intern\nCompany: Acme Labs\nLocation: Bengaluru\nWork mode: Hybrid\nDuration: 6 months\nStipend: INR 25000 per month\nRequired Skills\nPython, FastAPI, SQL\nResponsibilities\nBuild backend APIs\nWrite clean documentation"
  }'
```

Expected response shape:

```json
{
  "job_profile": {
    "role_title": "Software Engineering Intern",
    "company_name": "Acme Labs",
    "required_skills": ["Python", "SQL", "FastAPI"],
    "preferred_skills": [],
    "responsibilities": ["Build backend APIs", "Write clean documentation"],
    "eligibility": [],
    "stipend": "INR 25000 per month",
    "duration": "6 months",
    "location": "Bengaluru",
    "work_mode": "Hybrid",
    "keywords": ["Python", "SQL", "FastAPI", "Software Engineering Intern", "Acme Labs", "Bengaluru", "Hybrid"]
  }
}
```

## JD Analyzer Agent

The JD Analyzer Agent receives pasted internship or job description text and converts it into structured JSON for matching and recommendation workflows.

Input: raw job description text in the `job_description` field.

Processing: the current implementation uses improved rule-based extraction for role title, company, required skills, preferred skills, responsibilities, eligibility, stipend, duration, location, work mode, and keywords. It prioritizes clean role patterns such as `As an Artificial Intelligence (AI) Intern at COMPANY`, `hiring an AI/ML Intern`, and `role: AI/ML Intern`, rejects noisy phrases such as `deployment experience` or `selected intern`, extracts company names from `Company:`, `About COMPANY`, uppercase company blocks, and common suffixes like `PVT LTD`, and separates required skills from preferred skills by looking for phrases such as `required skills`, `must have`, and `candidate should have` versus `preferred skills`, `good to have`, `nice to have`, and `familiarity with`.

Strict JD skill parsing: the analyzer now reads heading-bounded blocks such as `Skill(s) required` until `Who can apply`, `Other requirements`, `Perks`, or similar stop headings. It preserves explicit skill order, normalizes display names such as `Natural Language Processing (NLP)` to `NLP`, `HTML5` to `HTML`, `CSS3` to `CSS`, and `RESTful API integration` to `REST API`, and merges additional skills from `Other requirements` into `required_skills`.

Backend output polish: company extraction supports `About SubSpace` style sections anywhere in the JD, eligibility output removes section headings, skill-gap displays use canonical casing such as `Express.js`, `REST API`, `WebSockets`, and `JavaScript`, and generated writing uses cleaner education and project summaries before returning results to the frontend.

Output: a normalized `job_profile` object that future matching agents can compare against the parsed resume profile.

Example parsed JD output:

```json
{
  "role_title": "AI/ML Intern",
  "company_name": "Example AI Startup",
  "required_skills": ["Python", "FastAPI", "Machine Learning", "SQL"],
  "preferred_skills": ["React", "Next.js", "LangChain", "Docker"],
  "responsibilities": [
    "building REST APIs",
    "training ML models, and creating dashboards"
  ],
  "eligibility": ["Candidates can apply who are B.Tech students available for 6 months"],
  "stipend": "INR 15,000 per month",
  "duration": "6 months",
  "location": "Remote",
  "work_mode": "Remote",
  "keywords": ["AI", "ML", "Python", "FastAPI", "Machine Learning", "SQL"]
}
```

Score a resume profile against a job profile:

```bash
curl -X POST http://127.0.0.1:8000/api/match/score \
  -H "Content-Type: application/json" \
  -d '{
    "resume_profile": {
      "name": "Jane Doe",
      "email": "jane@example.com",
      "skills": ["Python", "FastAPI", "React"],
      "projects": ["Built a FastAPI internship tracker with SQL database"],
      "education": ["B.S. Computer Science"],
      "experience": [],
      "certifications": []
    },
    "job_profile": {
      "role_title": "Software Engineering Intern",
      "required_skills": ["Python", "FastAPI", "SQL"],
      "preferred_skills": ["React"],
      "responsibilities": ["Build backend APIs", "Write SQL queries"],
      "eligibility": ["Computer Science students preferred"],
      "keywords": ["Python", "FastAPI", "SQL", "Backend"]
    }
  }'
```

Expected response shape:

```json
{
  "match_score": 78,
  "match_level": "Strong Fit",
  "matched_skills": ["Python", "FastAPI", "React"],
  "missing_skills": ["SQL"],
  "project_relevance_notes": [
    "Project 'Built a FastAPI internship tracker with SQL database' matches job terms: FastAPI, SQL, Intern."
  ],
  "recommendation": "Improve the match by adding evidence for these required skills: SQL."
}
```

## Match Scoring Agent

The Match Scoring Agent compares a parsed resume profile with a parsed job profile and returns a deterministic internship fit score.

Scoring formula:

| Category | Weight | Notes |
| --- | ---: | --- |
| Required skill match | 45 | Compares resume skills to `job_profile.required_skills`; missing required skills have the biggest impact. |
| Preferred skill match | 15 | Compares resume skills to `job_profile.preferred_skills`; missing preferred skills are lower priority. |
| Project relevance | 20 | Checks project names, descriptions, and technologies against skills, role title, and responsibilities. |
| Education relevance | 10 | Rewards relevant degree, engineering, CS, AI, data science, ML, year, and semester signals. |
| Experience/certifications | 10 | Rewards internship, AI/ML, software/development experience, and relevant certifications. |

Match levels:

| Score | Level |
| --- | --- |
| 85-100 | Excellent Fit |
| 70-84 | Strong Fit |
| 50-69 | Good Fit |
| 30-49 | Partial Fit |
| 0-29 | Weak Fit |

Input: a `resume_profile` object from the Resume Analyzer Agent and a `job_profile` object from the JD Analyzer Agent.

Processing: the agent normalizes skills into canonical display names, applies synonym matching such as `AI` to `Artificial Intelligence`, `NLP` to `Natural Language Processing`, `React.js` to `React`, `Scikit-Learn` to `Scikit-learn`, and `REST APIs` to `REST API`, calculates separate required and preferred skill overlap, checks project text against job keywords and responsibilities, and scores education, experience, and certifications with explainable notes.

Skill matching is intentionally conservative for exact required-skill credit: `TypeScript` does not automatically satisfy `JavaScript`, `GitHub` does not automatically satisfy `Git`, and `FastAPI` does not automatically satisfy `REST API`. Those relationships can still appear as related project evidence, for example `Project shows related backend API evidence through FastAPI.`

Output: a score, match level, matched skills, missing skills, project relevance notes, a practical recommendation, and a `score_breakdown` with separate required/preferred match percentages.

Example match output:

```json
{
  "match_score": 76,
  "match_level": "Strong Fit",
  "matched_skills": ["Python", "Machine Learning", "Backend Development"],
  "missing_skills": ["REST API", "Next.js", "Docker"],
  "project_relevance_notes": [
    "Project 'Hybrid Phishing Detection System' is relevant because it uses required skills: Python, Machine Learning, REST API, shows relevant domain signals: AI, Dashboard."
  ],
  "recommendation": "Good match; strengthen minor required gaps before applying: REST API.",
  "score_breakdown": {
    "required_skills": 34,
    "preferred_skills": 5,
    "project_relevance": 18,
    "education_relevance": 10,
    "experience_certifications": 9
  },
  "required_skill_match_percentage": 75,
  "preferred_skill_match_percentage": 33,
  "matched_required_skills": ["Python", "Machine Learning", "Backend Development"],
  "missing_required_skills": ["REST API"],
  "matched_preferred_skills": ["Frontend Development"],
  "missing_preferred_skills": ["Next.js", "Docker"]
}
```

Analyze skill gaps and generate a learning plan:

```bash
curl -X POST http://127.0.0.1:8000/api/skill-gap/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "resume_profile": {
      "name": "Jane Doe",
      "skills": ["Python", "FastAPI"],
      "projects": [
        "FastAPI internship tracker",
        {
          "name": "Hybrid Phishing Detection System",
          "description": "Detected phishing URLs with machine learning and a React dashboard.",
          "technologies": ["Python", "Machine Learning", "React"]
        }
      ],
      "education": ["B.S. Computer Science"],
      "experience": [],
      "certifications": []
    },
    "job_profile": {
      "role_title": "Software Engineering Intern",
      "required_skills": ["Python", "FastAPI", "SQL"],
      "preferred_skills": ["Docker"],
      "responsibilities": ["Build backend APIs"],
      "keywords": ["Backend", "SQL", "Docker"]
    },
    "match_result": {
      "match_score": 72,
      "match_level": "Good Fit",
      "matched_skills": ["Python", "FastAPI"],
      "missing_skills": ["SQL", "Docker"],
      "project_relevance_notes": ["Project matches FastAPI."],
      "recommendation": "Add SQL and Docker evidence."
    }
  }'
```

Expected response shape:

```json
{
  "target_role": "Software Engineering Intern",
  "priority_skills": [
    {
      "skill": "SQL",
      "priority": "High",
      "reason": "SQL is listed as a required skill for Software Engineering Intern.",
      "estimated_learning_time": "2-3 weeks",
      "learning_tasks": ["Practice SELECT, WHERE, JOIN, GROUP BY, and ORDER BY queries."]
    }
  ],
  "learning_roadmap": [
    {
      "week": 1,
      "focus": "High priority: SQL",
      "skills": ["SQL"],
      "tasks": ["Practice SELECT, WHERE, JOIN, GROUP BY, and ORDER BY queries."],
      "outcome": "Show practical evidence of SQL in a project or resume bullet."
    }
  ],
  "resume_improvement_suggestions": ["Add evidence for required skills: SQL."],
  "recommended_projects": [
    {
      "title": "Software Engineering Intern mini-project",
      "description": "Build a small project that demonstrates SQL, Docker in a realistic workflow.",
      "skills_practiced": ["SQL", "Docker"],
      "expected_outcome": "A resume-ready project with a short README, screenshots, and clear technical bullets."
    }
  ],
  "overall_advice": "Your current match score is 72. Start with the High priority skills first, then add a project that proves those skills in context."
}
```

## Skill Gap Agent

The Skill Gap Agent receives `resume_profile`, `job_profile`, and `match_result`, then turns missing skills into an actionable learning plan.

Input: parsed resume profile, parsed job profile, and match score output.

The `resume_profile.projects` field accepts either simple strings or structured project objects:

```json
[
  "FastAPI internship tracker",
  {
    "name": "Hybrid Phishing Detection System",
    "description": "Detected phishing URLs with machine learning and a React dashboard.",
    "technologies": ["Python", "Machine Learning", "React"]
  }
]
```

Processing: the agent reads `missing_skills`, compares them against required and preferred job skills, assigns High, Medium, or Low priority, estimates learning time, generates learning tasks, builds a week-by-week roadmap, and suggests resume improvements and mini-projects.

Output: `target_role`, `priority_skills`, `learning_roadmap`, `resume_improvement_suggestions`, `recommended_projects`, and `overall_advice`.

Generate a customized application answer:

```bash
curl -X POST http://127.0.0.1:8000/api/application/write \
  -H "Content-Type: application/json" \
  -d '{
    "resume_profile": {
      "name": "Jane Doe",
      "education": ["B.S. Computer Science"],
      "skills": ["Python", "FastAPI", "React"],
      "projects": [
        {
          "name": "Hybrid Phishing Detection System",
          "description": "Detected phishing URLs with machine learning and a React dashboard",
          "technologies": ["Python", "Machine Learning", "React"]
        }
      ]
    },
    "job_profile": {
      "role_title": "Software Engineering Intern",
      "company_name": "Acme Labs"
    },
    "match_result": {
      "matched_skills": ["Python", "FastAPI", "React"],
      "missing_skills": ["SQL", "Docker"]
    },
    "skill_gap_result": {
      "priority_skills": [{"skill": "SQL"}, {"skill": "Docker"}],
      "overall_advice": "Start with SQL, then Docker."
    },
    "application_question": "Why should we hire you?",
    "tone": "professional",
    "word_limit": 180
  }'
```

Expected response shape:

```json
{
  "question": "Why should we hire you?",
  "generated_answer": "I am a candidate with education in B.S. Computer Science...",
  "key_points_used": [
    "Education: B.S. Computer Science",
    "Target role: Software Engineering Intern",
    "Matched skills: Python, FastAPI, React"
  ],
  "tone": "professional",
  "word_count": 81,
  "improvement_note": "Review the answer after adding stronger evidence for: SQL, Docker."
}
```

## Application Writer Agent

The Application Writer Agent creates customized internship application answers using the parsed resume profile, parsed job profile, match result, skill gap result, and a specific application question.

Input: `resume_profile`, `job_profile`, `match_result`, `skill_gap_result`, `application_question`, optional `tone`, and optional `word_limit`.

Processing: the current implementation detects the question type, selects a template, chooses the strongest education entry instead of blindly using the shortest item, inserts a clean target role, highlights top matched skills, summarizes the top two projects, and frames missing skills as active learning goals. It avoids suspicious role titles, handles missing company names gracefully, avoids claiming missing skills as already mastered, and trims to the requested word limit.

Writing quality improvements: the agent prefers higher education such as `B.Tech`, `Bachelor`, engineering, AI, data science, or computer science over `Class X`; converts long project objects into concise evidence such as `Hybrid Phishing Detection System`; keeps `key_points_used` short; and limits learning focus to the most important missing skills.

The writer also removes noisy phrases such as `Projects include...`, repeated project titles, third-person fragments such as `where he worked`, and broken project fragments before using cleaner sentences such as `In my Hybrid Phishing Detection System project, I built...`. When a project description is still messy, it falls back to a safe project-specific summary.

Output: the original question, generated answer, key points used, tone, word count, and an improvement note.

Generate a customized cover letter:

```bash
curl -X POST http://127.0.0.1:8000/api/cover-letter/generate \
  -H "Content-Type: application/json" \
  -d '{
    "resume_profile": {
      "name": "Jane Doe",
      "education": ["B.S. Computer Science"],
      "skills": ["Python", "FastAPI", "React"],
      "projects": [
        {
          "name": "Hybrid Phishing Detection System",
          "description": "Detected phishing URLs with machine learning and a React dashboard",
          "technologies": ["Python", "Machine Learning", "React"]
        }
      ],
      "experience": ["Open source backend documentation contributor"]
    },
    "job_profile": {
      "role_title": "Software Engineering Intern",
      "company_name": "Acme Labs",
      "responsibilities": ["Build backend APIs", "Write SQL queries"]
    },
    "match_result": {
      "match_level": "Strong Fit",
      "matched_skills": ["Python", "FastAPI", "React"],
      "missing_skills": ["SQL", "Docker"]
    },
    "skill_gap_result": {
      "priority_skills": [{"skill": "SQL"}, {"skill": "Docker"}]
    },
    "tone": "professional",
    "length": "short"
  }'
```

Expected response shape:

```json
{
  "cover_letter": "Dear Hiring Team,\n\nI am writing to apply for the Software Engineering Intern role at Acme Labs...",
  "subject_line": "Application for Software Engineering Intern at Acme Labs",
  "opening_summary": "Candidate pursuing B.S. Computer Science and applying for Software Engineering Intern.",
  "key_points_used": [
    "Target role: Software Engineering Intern",
    "Company: Acme Labs",
    "Education: B.S. Computer Science"
  ],
  "tone": "professional",
  "word_count": 128
}
```

## Cover Letter Agent

The Cover Letter Agent generates a customized internship cover letter using the parsed resume profile, parsed job profile, match result, and skill gap result.

Input: `resume_profile`, `job_profile`, `match_result`, `skill_gap_result`, optional `tone`, and optional `length`.

Processing: the current implementation builds a subject line, opening summary, role-specific body, best education summary, matched skill evidence, concise project highlights, and a learning-gap sentence. It starts with `Dear Hiring Team,`, handles missing company names without awkward `at` text, uses clean role-title fallbacks, ends politely, and avoids presenting missing skills as already mastered.

Cover letter quality improvements: the agent avoids treating `Class X` as current education when a stronger degree exists, keeps project evidence short, uses one background paragraph, one project-relevance paragraph, and a closing section, and keeps `key_points_used` focused on education, role, company, matched skills, project names, and learning focus.

The cover letter uses the same backend cleanup as application answers, so education does not end in awkward fragments such as `at background`, and project summaries avoid repeated titles, `where I Projects include...`, `I Strategic Classification System`, and similar broken phrasing.

Output: `cover_letter`, `subject_line`, `opening_summary`, `key_points_used`, `tone`, and `word_count`.

Run the full multi-agent pipeline:

```bash
curl -X POST http://127.0.0.1:8000/api/orchestrator/analyze-application \
  -H "Content-Type: application/json" \
  -d '{
    "resume_text": "Jane Doe\nEducation\nB.S. Computer Science\nSkills\nPython, FastAPI, React\nProjects\nHybrid Phishing Detection System using Python and React",
    "job_description": "Role: Software Engineering Intern\nCompany: Acme Labs\nRequired Skills\nPython, FastAPI, SQL\nPreferred Skills\nDocker\nResponsibilities\nBuild backend APIs",
    "application_question": "Why should we hire you?",
    "tone": "professional",
    "word_limit": 180,
    "cover_letter_length": "short"
  }'
```

Expected response shape:

```json
{
  "resume_profile": {},
  "job_profile": {},
  "match_result": {},
  "skill_gap_result": {},
  "application_answer": {},
  "cover_letter": {},
  "pipeline_summary": {
    "candidate_name": "Jane Doe",
    "target_role": "Software Engineering Intern",
    "company_name": "Acme Labs",
    "match_score": 57,
    "match_level": "Partial Fit",
    "top_matched_skills": ["Python", "FastAPI"],
    "top_missing_skills": ["SQL"],
    "highest_priority_skills": ["SQL"],
    "recommended_next_step": "Start with the highest priority missing skills: SQL."
  }
}
```

## Multi-Agent Orchestrator

The Multi-Agent Orchestrator is the main endpoint for full application analysis. It accepts raw resume text and a pasted internship or job description, then runs the completed agents in sequence.

Agent communication flow:

1. Resume Analyzer creates `resume_profile`.
2. JD Analyzer creates `job_profile`.
3. Match Scoring compares both profiles and creates `match_result`.
4. Skill Gap Agent uses both profiles plus `match_result` to create `skill_gap_result`.
5. Application Writer uses all previous outputs to create `application_answer`.
6. Cover Letter Agent uses the same context to create `cover_letter`.
7. Orchestrator builds `pipeline_summary` for quick review.

This endpoint works without any external LLM API key and reuses the existing rule-based and template-based agents.

The final writing agents use cleaned profile data from earlier phases: best education selection, concise project summaries, matched skill highlighting, and learning-gap framing produce more natural answers and cover letters while staying grounded in the extracted resume and job profile.

## LLM Service Layer

InternAI now includes a backend LLM provider layer for future real-model integration. The current agents still use deterministic rule-based and template-based logic, so existing endpoints work without API keys.

The service exposes:

- `GET /api/llm/status` to show the active provider, model, and availability.
- `POST /api/llm/test` to test text generation through the configured provider.

Default behavior is `mock`, which returns a safe fallback response. Gemini support is available through the REST `generateContent` API and only runs when `LLM_PROVIDER=gemini` and `GEMINI_API_KEY` are set. Groq support is prepared through an OpenAI-compatible HTTP path and only runs when `LLM_PROVIDER=groq` and `GROQ_API_KEY` are set. Future phases can call `LLMService.generate_text(...)` from agents without changing frontend API contracts.

### Frontend

The frontend is a Next.js and Tailwind CSS app for running the full orchestrator workflow.

```bash
cd internai/frontend
npm install
cp .env.example .env.local
npm run dev
```

The frontend should be available at `http://localhost:3000`.

### Run Backend And Frontend Together

Terminal 1:

```bash
cd internai/backend
uvicorn app.main:app --reload
```

Terminal 2:

```bash
cd internai/frontend
npm run dev
```

The frontend calls the FastAPI orchestrator endpoint configured by `NEXT_PUBLIC_API_URL`. By default, it uses `http://127.0.0.1:8000`.

## Frontend Workflow

The frontend page lets a user:

1. Upload a resume PDF or paste resume text manually.
2. Review and edit the extracted resume text if needed.
3. Paste an internship or job description.
4. Set the application question, tone, answer word limit, and cover letter length.
5. Click `Analyze`.
6. Review the pipeline summary, large match score, score breakdown, grouped matched/missing skills, learning roadmap, application answer, and cover letter.
7. Copy the generated application answer or cover letter from the dashboard.
8. Save the analysis to the application tracker with clear saving, success, and failure states.
9. Avoid duplicate saves for the same result session after the analysis is saved.
10. Track saved applications by company, role, match score, match level, and status.

The `Use Sample Data` button fills the form with a tested resume and job description so the full workflow can be tried quickly.

The resume PDF upload uses the backend `POST /api/resume/upload` endpoint. The frontend sends the selected PDF as `multipart/form-data` with the field name `file`, receives `filename`, `text_length`, and `extracted_text`, and fills the resume textarea automatically. Non-PDF files are rejected in the browser, and upload failures show a clear message so the user can paste resume text manually.

Typical resume upload workflow:

1. Upload PDF.
2. Backend extracts text with PyMuPDF.
3. Frontend shows the uploaded filename and extracted character count.
4. Frontend fills the resume text area.
5. User edits the extracted text if needed.
6. User runs the orchestrator analysis.

PDF text extraction may not preserve the exact visual order of complex resume layouts, but the analyzer still uses the extracted content to identify useful profile details.

The results dashboard is organized for portfolio demos:

- Pipeline summary with candidate, role, company, score, level, and next step.
- Match score card with required and preferred skill percentages.
- Score breakdown for required skills, preferred skills, project relevance, education relevance, and experience/certifications.
- Skills overview grouped by matched required, missing required, matched preferred, missing preferred, general matched, and general missing skills.
- Skill gap roadmap with priorities, reasons, estimated learning time, week-wise tasks, and mini-project recommendations.
- Copy buttons for generated application answers and cover letters.
- Tracker save UX that shows `Save Application`, `Saving...`, `Application saved successfully`, or a failure message.

## Application Tracker

InternAI stores saved application analyses in a local SQLite database at `backend/internai.db`. The database is created automatically when the FastAPI app starts.

Supported statuses:

- `Saved`
- `Applied`
- `Interview`
- `Rejected`
- `Selected`

The tracker saves the full orchestrator output as JSON strings, including resume profile, job profile, match result, skill gap result, application answer, cover letter, and pipeline summary.

Save an orchestrator result:

```bash
curl -X POST http://127.0.0.1:8000/api/tracker/applications \
  -H "Content-Type: application/json" \
  -d '{
    "resume_profile": {"name": "Jane Doe"},
    "job_profile": {"role_title": "Software Engineering Intern", "company_name": "Acme Labs"},
    "match_result": {"match_score": 82, "match_level": "Strong Fit"},
    "skill_gap_result": {},
    "application_answer": {},
    "cover_letter": {},
    "pipeline_summary": {
      "candidate_name": "Jane Doe",
      "target_role": "Software Engineering Intern",
      "company_name": "Acme Labs",
      "match_score": 82,
      "match_level": "Strong Fit"
    },
    "status": "Saved",
    "notes": "Promising backend internship"
  }'
```

List saved applications:

```bash
curl http://127.0.0.1:8000/api/tracker/applications
```

Update status:

```bash
curl -X PATCH http://127.0.0.1:8000/api/tracker/applications/1/status \
  -H "Content-Type: application/json" \
  -d '{"status": "Applied"}'
```

The frontend tracker calls these APIs after the user saves an orchestrator analysis.

## Screenshot Placeholder

Add screenshots here after the UI is run locally:

- Full analysis form
- Results dashboard
- Application answer and cover letter sections

## Development Roadmap

1. Scaffold the FastAPI backend and documentation foundation.
2. Initialize the Next.js frontend with Tailwind CSS.
3. Add resume PDF upload and text extraction.
4. Add Resume Analyzer Agent for structured resume parsing.
5. Add JD Analyzer Agent for structured internship description parsing.
6. Add Match Scoring Agent for deterministic internship fit scoring.
7. Add Skill Gap Agent for learning roadmap and improvement planning.
8. Add Application Writer Agent for customized internship answers.
9. Add Cover Letter Agent for customized internship cover letters.
10. Add Multi-Agent Orchestrator for end-to-end analysis.
11. Add frontend UI for running the orchestrator workflow.
12. Add SQLite Application Tracker for saved analyses.
13. Build core API routes for user profile and opportunity search.
14. Add the first LLM-powered agent workflow.
15. Add authentication and user-specific data.
16. Improve agent orchestration with LangChain or LangGraph.
17. Add tests, deployment configuration, and production documentation.

## Documentation

- [Architecture](docs/architecture.md)
- [Agents](docs/agents.md)
- [Workflow](docs/workflow.md)
- [API Reference](docs/api-reference.md)
