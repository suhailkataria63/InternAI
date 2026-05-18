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
- Next.js frontend UI for running the full orchestrator workflow from a browser.
- SQLite-backed Application Tracker for saving analyzed internships and tracking status.

## Tech Stack

- Backend: FastAPI
- Frontend: Next.js with Tailwind CSS
- Database: SQLite during initial development
- AI workflow: LangChain or LangGraph, to be added later
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

Check the health endpoint:

```bash
curl http://127.0.0.1:8000/health
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
  "filename": "resume.pdf",
  "text_length": 1234,
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

Processing: the current implementation uses improved rule-based extraction for labels, section headings, and paragraph-style text. It detects names from `Name:` labels, first meaningful lines, and phrases such as `Suhail Kataria is pursuing...`; detects education keywords like `B.Tech`, `AI&DS`, `CGC Landran`, and `IKGPTU`; extracts expanded technical skills; detects projects from bullet lines and phrases like `Projects include...`; and returns projects as structured objects with `name`, `description`, and `technologies`.

Output: a normalized `profile` object that can be reused by future Profile, Opportunity, Resume, and Interview agents.

Example extracted resume profile:

```json
{
  "name": "Suhail Kataria",
  "education": [
    "B.Tech in Artificial Intelligence and Data Science at CGC Landran under IKGPTU"
  ],
  "skills": ["Python", "React", "FastAPI", "Machine Learning", "SQL"],
  "projects": [
    {
      "name": "Hybrid Phishing Detection System",
      "description": "Hybrid Phishing Detection System using Python, Machine Learning and React",
      "technologies": ["Python", "React", "Machine Learning"]
    }
  ],
  "experience": ["AI Intern at Unified Mentor"],
  "certifications": ["Google Data Analytics Certificate from Coursera"]
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

Processing: the current implementation uses rule-based extraction for role title, company, skills, responsibilities, eligibility, stipend, duration, location, work mode, and keywords. A prompt template is stored in the agent file for future LLM integration.

Output: a normalized `job_profile` object that future matching agents can compare against the parsed resume profile.

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

- Required skill match: 50 points
- Preferred skill match: 15 points
- Project relevance: 20 points
- Education and role relevance: 10 points
- Experience and certifications: 5 points

Input: a `resume_profile` object from the Resume Analyzer Agent and a `job_profile` object from the JD Analyzer Agent.

Processing: the agent normalizes skills, calculates weighted overlap, checks project text against job keywords and responsibilities, and adds small relevance scores for education, experience, and certifications.

Output: a score, match level, matched skills, missing required skills, project relevance notes, and a recommendation.

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

Processing: the current implementation detects the question type, selects a template, inserts education, target role, matched skills, relevant projects, and learning focus, then applies tone and trims to the requested word limit. It avoids claiming missing skills as already mastered.

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
  "cover_letter": "Dear Hiring Team,\n\nI am interested in the Software Engineering Intern role at Acme Labs...",
  "subject_line": "Application for Software Engineering Intern at Acme Labs",
  "opening_summary": "Candidate with education in B.S. Computer Science applying for Software Engineering Intern.",
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

Processing: the current implementation builds a subject line, opening summary, role-specific body, matched skill evidence, project and experience highlights, and a learning-gap sentence. It starts with `Dear Hiring Team,`, ends politely, and avoids presenting missing skills as already mastered.

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

1. Paste resume text.
2. Paste an internship or job description.
3. Set the application question, tone, answer word limit, and cover letter length.
4. Click `Analyze`.
5. Review the pipeline summary, match score, missing skills, learning roadmap, application answer, and cover letter.
6. Save the analysis to the application tracker.
7. Track saved applications by company, role, match score, match level, and status.

The `Use Sample Data` button fills the form with a tested resume and job description so the full workflow can be tried quickly.

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
