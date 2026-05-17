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
    "projects": ["Internship tracker app"],
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

Processing: the current implementation uses rule-based extraction for name, email, phone, resume sections, skills, strengths, and improvement areas. A prompt template is stored in the agent file so the same output format can later be powered by LangChain or LangGraph.

Output: a normalized `profile` object that can be reused by future Profile, Opportunity, Resume, and Interview agents.

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

### Frontend

The frontend folder is prepared for a future Next.js and Tailwind CSS app.

Planned setup:

```bash
cd internai/frontend
npm install
npm run dev
```

## Development Roadmap

1. Scaffold the FastAPI backend and documentation foundation.
2. Initialize the Next.js frontend with Tailwind CSS.
3. Add resume PDF upload and text extraction.
4. Add Resume Analyzer Agent for structured resume parsing.
5. Add JD Analyzer Agent for structured internship description parsing.
6. Add Match Scoring Agent for deterministic internship fit scoring.
7. Add SQLite database models and persistence.
8. Build core API routes for user profile, opportunities, and applications.
9. Add the first LLM-powered agent workflow.
10. Connect frontend screens to backend APIs.
11. Add authentication and user-specific data.
12. Improve agent orchestration with LangChain or LangGraph.
13. Add tests, deployment configuration, and production documentation.

## Documentation

- [Architecture](docs/architecture.md)
- [Agents](docs/agents.md)
- [Workflow](docs/workflow.md)
- [API Reference](docs/api-reference.md)
