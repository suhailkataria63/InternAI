# InternAI Workflow

## Planned User Workflow

1. User creates or imports an internship profile.
2. InternAI identifies target roles, skills, preferences, and constraints.
3. User uploads a resume PDF, and the backend extracts raw text.
4. Resume Analyzer Agent converts resume text into a structured profile.
5. User pastes an internship or job description.
6. JD Analyzer Agent converts the description into a structured job profile.
7. Match Scoring Agent compares both profiles and returns a fit score, missing skills, project relevance notes, and a recommendation.
8. Skill Gap Agent turns missing skills into priorities, a learning roadmap, resume suggestions, and mini-projects.
9. Application Writer Agent drafts customized answers for internship application questions.
10. User saves strong opportunities into an application pipeline.
11. Resume Agent helps tailor materials for selected opportunities.
12. Application Agent tracks statuses, deadlines, and follow-ups.
13. Interview Agent prepares the user for technical and behavioral interviews.
14. The system keeps a history of decisions, outputs, and progress.

## Initial Workflow

The current backend supports the first analysis chain: resume PDF upload, resume analysis, job description analysis, match scoring, skill gap planning, and application answer drafting. The frontend and database will be added around this workflow later.

## Current API Workflow

1. `POST /api/resume/upload` extracts text from a resume PDF.
2. `POST /api/resume/analyze` converts extracted text into `resume_profile`.
3. `POST /api/jobs/analyze` converts pasted job text into `job_profile`.
4. `POST /api/match/score` compares both profiles and returns the fit score.
5. `POST /api/skill-gap/analyze` turns missing skills into a roadmap and project plan.
6. `POST /api/application/write` generates a tailored answer for a specific application question.

## Future Workflow Questions

- Should users manually add opportunities, import them, or both?
- Which agent actions require explicit user approval?
- How should generated resumes and cover letters be versioned?
- What application statuses should be supported in the first usable version?
- How should agent activity be displayed in the frontend?
- Should match score weights be user-configurable for different internship types?
