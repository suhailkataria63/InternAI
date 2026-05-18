# InternAI Workflow

## Planned User Workflow

1. User creates or imports an internship profile.
2. InternAI identifies target roles, skills, preferences, and constraints.
3. User uploads a resume PDF, and the backend extracts raw text.
4. Resume Analyzer Agent converts resume text into a structured profile, including improved paragraph-style extraction for name, education, skills, projects, experience, and certifications.
5. User pastes an internship or job description.
6. JD Analyzer Agent converts the description into a structured job profile with clearer required/preferred skill separation.
7. Match Scoring Agent compares both profiles and returns a weighted fit score, score breakdown, missing required/preferred skills, project relevance notes, and a recommendation.
8. Skill Gap Agent turns missing skills into priorities, a learning roadmap, resume suggestions, and mini-projects.
9. Application Writer Agent drafts customized answers for internship application questions.
10. Cover Letter Agent generates a role-specific internship cover letter.
11. Multi-Agent Orchestrator can run steps 4-10 from one endpoint.
12. User saves strong opportunities into the SQLite Application Tracker.
13. User updates application status as `Saved`, `Applied`, `Interview`, `Rejected`, or `Selected`.
14. Resume Agent helps tailor materials for selected opportunities.
15. Application Agent tracks statuses, deadlines, and follow-ups.
16. Interview Agent prepares the user for technical and behavioral interviews.
17. The system keeps a history of decisions, outputs, and progress.

## Initial Workflow

The current application supports the first analysis chain: resume text input, job description input, resume analysis, job description analysis, match scoring, skill gap planning, application answer drafting, cover letter generation, full orchestration from the frontend UI, and saving analyses to SQLite.

## Current API Workflow

1. `POST /api/resume/upload` extracts text from a resume PDF.
2. `POST /api/resume/analyze` converts extracted text into `resume_profile`.
3. `POST /api/jobs/analyze` converts pasted job text into `job_profile`.
4. `POST /api/match/score` compares both profiles and returns the fit score.
5. `POST /api/skill-gap/analyze` turns missing skills into a roadmap and project plan.
6. `POST /api/application/write` generates a tailored answer for a specific application question.
7. `POST /api/cover-letter/generate` generates a customized internship cover letter.
8. `POST /api/orchestrator/analyze-application` runs the full analysis pipeline in one request.
9. `POST /api/tracker/applications` saves a full application analysis.
10. `GET /api/tracker/applications` lists saved applications.

## Orchestrator Workflow

The orchestrator endpoint accepts raw `resume_text` and `job_description`, then passes structured output from one agent into the next.

| Step | Agent | Input | Output |
| --- | --- | --- | --- |
| 1 | Resume Analyzer Agent | `resume_text` | `resume_profile` |
| 2 | JD Analyzer Agent | `job_description` | `job_profile` |
| 3 | Match Scoring Agent | `resume_profile`, `job_profile` | `match_result` |
| 4 | Skill Gap Agent | `resume_profile`, `job_profile`, `match_result` | `skill_gap_result` |
| 5 | Application Writer Agent | all previous outputs plus `application_question` | `application_answer` |
| 6 | Cover Letter Agent | `resume_profile`, `job_profile`, `match_result`, `skill_gap_result` | `cover_letter` |
| 7 | Orchestrator Service | core agent outputs | `pipeline_summary` |

Improved resume extraction strengthens every downstream agent because match scoring, skill-gap planning, application answers, cover letters, and tracker summaries all reuse `resume_profile`.

Improved JD parsing strengthens match scoring and skill-gap priority because required skills drive higher score weight and High-priority learning gaps, while preferred-only skills remain Medium priority.

Improved match scoring gives the Skill Gap Agent cleaner missing required and preferred skills, and gives the Application Tracker a more explainable score breakdown for saved opportunities.

## Frontend-To-Backend Workflow

The Next.js frontend uses the orchestrator endpoint as its main API.

| UI Step | Frontend Module | Backend API |
| --- | --- | --- |
| User enters resume, job description, tone, word limit, and cover letter length | `AnalysisForm` | None yet |
| User clicks `Analyze` | `frontend/lib/api.ts` | `POST /api/orchestrator/analyze-application` |
| Backend returns full pipeline output | `analyzeApplication` | Orchestrator response |
| UI renders summary and score | `PipelineSummaryCard`, `MatchScoreCard` | Uses `pipeline_summary`, `match_result` |
| UI renders score evidence | `ResultsDashboard` | Uses `match_result.score_breakdown` |
| UI renders skill groups | `ResultsDashboard`, `SkillBadge` | Uses required/preferred matched and missing skills |
| UI renders roadmap | `SkillGapCard` | Uses priority skills, roadmap weeks, and recommended projects |
| UI renders generated writing | `ApplicationAnswerCard`, `CoverLetterCard` | Uses generated text, tone, word count, key points, and copy buttons |
| User clicks `Save Application` | `ResultsDashboard` | `POST /api/tracker/applications` |
| UI loads saved applications | `ApplicationTracker` | `GET /api/tracker/applications` |
| User changes status | `ApplicationTracker` | `PATCH /api/tracker/applications/{id}/status` |
| User deletes a row | `ApplicationTracker` | `DELETE /api/tracker/applications/{id}` |

If the backend is not running, the frontend displays a clear connection error from the API client.

After an orchestrator response, the results dashboard displays sections in this order: pipeline summary, match score, score breakdown, skills overview, skill gap roadmap, application answer, cover letter, and tracker save controls. Missing fields are rendered with fallback text so partial backend responses do not crash the UI.

## Save-To-Tracker Workflow

1. User runs the orchestrator analysis from the frontend.
2. Frontend receives `resume_profile`, `job_profile`, `match_result`, `skill_gap_result`, `application_answer`, `cover_letter`, and `pipeline_summary`.
3. User clicks `Save Application`.
4. Frontend sends the full analysis output to `POST /api/tracker/applications`.
5. Backend extracts compact fields such as company, role, score, level, and candidate name.
6. Backend stores nested agent outputs as JSON strings in SQLite.
7. Frontend refreshes the tracker table.

## Future Workflow Questions

- Should users manually add opportunities, import them, or both?
- Which agent actions require explicit user approval?
- How should generated resumes and cover letters be versioned?
- What application statuses should be supported in the first usable version?
- How should agent activity be displayed in the frontend?
- Should match score weights be user-configurable for different internship types?
