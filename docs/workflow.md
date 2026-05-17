# InternAI Workflow

## Planned User Workflow

1. User creates or imports an internship profile.
2. InternAI identifies target roles, skills, preferences, and constraints.
3. User uploads a resume PDF, and the backend extracts raw text.
4. Resume Analyzer Agent converts resume text into a structured profile.
5. User pastes an internship or job description.
6. JD Analyzer Agent converts the description into a structured job profile.
7. Match Scoring Agent compares both profiles and returns a fit score, missing skills, project relevance notes, and a recommendation.
8. User saves strong opportunities into an application pipeline.
9. Resume Agent helps tailor materials for selected opportunities.
10. Application Agent tracks statuses, deadlines, and follow-ups.
11. Interview Agent prepares the user for technical and behavioral interviews.
12. The system keeps a history of decisions, outputs, and progress.

## Initial Workflow

The current backend supports the first analysis chain: resume PDF upload, resume analysis, job description analysis, and match scoring. The frontend and database will be added around this workflow later.

## Current API Workflow

1. `POST /api/resume/upload` extracts text from a resume PDF.
2. `POST /api/resume/analyze` converts extracted text into `resume_profile`.
3. `POST /api/jobs/analyze` converts pasted job text into `job_profile`.
4. `POST /api/match/score` compares both profiles and returns the fit score.

## Future Workflow Questions

- Should users manually add opportunities, import them, or both?
- Which agent actions require explicit user approval?
- How should generated resumes and cover letters be versioned?
- What application statuses should be supported in the first usable version?
- How should agent activity be displayed in the frontend?
- Should match score weights be user-configurable for different internship types?
