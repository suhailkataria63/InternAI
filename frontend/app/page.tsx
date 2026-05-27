"use client";

import { ChangeEvent, useMemo, useState } from "react";
import ApplicationTracker from "../components/ApplicationTracker";
import {
  analyzeApplication,
  saveApplicationAnalysis,
  uploadResumePdf,
} from "../lib/api";
import type {
  AnalysisRequest,
  AnalysisResponse,
  CoverLetterLength,
  Tone,
} from "../lib/types";

const toneOptions: Tone[] = ["professional", "friendly", "confident"];
const lengthOptions: CoverLetterLength[] = ["short", "medium", "long"];

const sampleResume = `Suhail Kataria
suhail.kataria63@gmail.com
B.Tech in Artificial Intelligence and Data Science
Skills: Python, React, Next.js, Machine Learning, NLP, SQL
Projects: Hybrid Phishing Detection System using Python, Machine Learning, React, Next.js, and Tailwind CSS
Demand Forecasting using Time Series Analysis`;

const sampleJobDescription = `About SubSpace
Role: Web Development Intern
Skill(s) required
Natural Language Processing (NLP)
CSS
HTML
JavaScript
Next.js
Node.js
Python
React
SQL
Tailwind CSS
Who can apply
Candidates available for full time internship for duration of 6 months.`;

function getStringArray(source: unknown, key?: string): string[] {
  const value =
    key && source && typeof source === "object"
      ? (source as Record<string, unknown>)[key]
      : source;

  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => (typeof item === "string" ? item : ""))
    .filter(Boolean);
}

function getStringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function getArrayLength(source: unknown, key: string): number {
  if (!source || typeof source !== "object") {
    return 0;
  }
  const value = (source as Record<string, unknown>)[key];
  return Array.isArray(value) ? value.length : 0;
}

function readablePrioritySkills(result: AnalysisResponse | null): string[] {
  const summarySkills = result?.pipeline_summary?.highest_priority_skills || [];
  const gapSkills =
    result?.skill_gap_result?.priority_skills
      ?.map((item) => item.skill)
      .filter(Boolean) || [];

  return (summarySkills.length ? summarySkills : gapSkills).slice(0, 8);
}

export default function Home() {
  const [resumeText, setResumeText] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [applicationQuestion, setApplicationQuestion] = useState(
    "Why should we hire you for this internship?",
  );
  const [tone, setTone] = useState<Tone>("professional");
  const [wordLimit, setWordLimit] = useState(180);
  const [coverLetterLength, setCoverLetterLength] =
    useState<CoverLetterLength>("short");

  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [trackerRefreshKey, setTrackerRefreshKey] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [saveError, setSaveError] = useState("");
  const [hasSavedCurrentResult, setHasSavedCurrentResult] = useState(false);
  const [copiedTarget, setCopiedTarget] = useState<"answer" | "cover" | "">("");

  const matchedRequired =
    result?.match_result?.matched_required_skills?.length
      ? result.match_result.matched_required_skills
      : result?.match_result?.matched_skills || [];
  const missingRequired = result?.match_result?.missing_required_skills || [];
  const requiredSkills = getStringArray(result?.job_profile, "required_skills");
  const skillCoverageTotal =
    requiredSkills.length || matchedRequired.length + missingRequired.length;
  const roadmap = result?.skill_gap_result?.learning_roadmap || [];
  const matchedSkills = matchedRequired.length
    ? matchedRequired
    : result?.match_result?.matched_skills || [];
  const missingSkills = missingRequired.length
    ? missingRequired
    : result?.match_result?.missing_skills || [];
  const coverLetter = result?.cover_letter?.cover_letter || "";
  const applicationAnswer = result?.application_answer?.generated_answer || "";
  const prioritySkills = readablePrioritySkills(result);
  const candidateName =
    getStringValue(result?.pipeline_summary?.candidate_name) ||
    getStringValue(result?.resume_profile?.name) ||
    "Candidate name not detected";
  const rawTargetRole =
    getStringValue(result?.pipeline_summary?.target_role) ||
    getStringValue(result?.job_profile?.role_title);
  const targetRole = rawTargetRole || "Target role not detected";
  const rawCompanyName =
    getStringValue(result?.pipeline_summary?.company_name) ||
    getStringValue(result?.job_profile?.company_name);
  const companyName = rawCompanyName || "Company not detected";
  const roleCompanyLine = rawTargetRole
    ? rawCompanyName
      ? `${rawTargetRole} at ${rawCompanyName}`
      : rawTargetRole
    : "Target role not detected";
  const matchScore =
    result?.pipeline_summary?.match_score ??
    result?.match_result?.match_score;
  const matchLevel =
    result?.pipeline_summary?.match_level ||
    result?.match_result?.match_level ||
    "Not available";

  const stats = useMemo(
    () => [
      {
        label: "Match Score",
        value:
          typeof matchScore === "number"
            ? `${matchScore}/100`
            : "--",
      },
      {
        label: "Skill Coverage",
        value: result ? `${matchedRequired.length}/${skillCoverageTotal}` : "0/0",
      },
      {
        label: "Projects",
        value: String(getArrayLength(result?.resume_profile, "projects")),
      },
      {
        label: "Roadmap Weeks",
        value: String(roadmap.length),
      },
    ],
    [matchedRequired.length, matchScore, roadmap.length, result, skillCoverageTotal],
  );

  const handleResumeUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) {
      return;
    }

    const isPdf =
      file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

    setUploadMessage("");
    setUploadError("");

    if (!isPdf) {
      setUploadError("Please upload a PDF resume file.");
      return;
    }

    setIsUploading(true);
    try {
      const uploaded = await uploadResumePdf(file);
      if (!uploaded.extracted_text?.trim()) {
        setUploadError("PDF uploaded, but no text could be extracted.");
        return;
      }

      setResumeText(uploaded.extracted_text);
      setUploadMessage(
        `Uploaded ${uploaded.filename} successfully. Extracted ${uploaded.text_length} characters.`,
      );
    } catch (caughtError) {
      setUploadError(
        caughtError instanceof Error
          ? caughtError.message
          : "Failed to extract resume text. Please paste resume text manually.",
      );
    } finally {
      setIsUploading(false);
    }
  };

  const handleAnalyze = async () => {
    setAnalysisError("");
    setSaveMessage("");
    setSaveError("");

    if (!resumeText.trim()) {
      setAnalysisError("Add resume text or upload a resume PDF before analyzing.");
      return;
    }

    if (!jobDescription.trim()) {
      setAnalysisError("Paste an internship or job description before analyzing.");
      return;
    }

    const payload: AnalysisRequest = {
      resume_text: resumeText,
      job_description: jobDescription,
      application_question: applicationQuestion.trim()
        || "Why should we hire you for this internship?",
      tone,
      word_limit: Number(wordLimit) || 180,
      cover_letter_length: coverLetterLength,
    };

    setIsAnalyzing(true);
    try {
      const analysis = await analyzeApplication(payload);
      setResult(analysis);
      setHasSavedCurrentResult(false);
    } catch (caughtError) {
      setAnalysisError(
        caughtError instanceof Error
          ? caughtError.message
          : "Analysis failed. Make sure the FastAPI backend is running.",
      );
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleSaveApplication = async () => {
    if (!result || hasSavedCurrentResult) {
      return;
    }

    setIsSaving(true);
    setSaveMessage("");
    setSaveError("");
    try {
      await saveApplicationAnalysis(result);
      setHasSavedCurrentResult(true);
      setSaveMessage("Application saved successfully.");
      setTrackerRefreshKey((current) => current + 1);
    } catch (caughtError) {
      setSaveError(
        caughtError instanceof Error
          ? caughtError.message
          : "Failed to save application.",
      );
    } finally {
      setIsSaving(false);
    }
  };

  const copyText = async (target: "answer" | "cover", text: string) => {
    if (!text) {
      return;
    }

    try {
      await navigator.clipboard.writeText(text);
      setCopiedTarget(target);
      window.setTimeout(() => setCopiedTarget(""), 1800);
    } catch {
      setCopiedTarget("");
    }
  };

  const useSampleData = () => {
    setResumeText(sampleResume);
    setJobDescription(sampleJobDescription);
    setAnalysisError("");
    setUploadError("");
    setUploadMessage("Sample resume and job description loaded.");
  };

  return (
    <main className="page-shell">
      <div className="background-grid" aria-hidden="true" />
      <div className="background-glow glow-1" aria-hidden="true" />
      <div className="background-glow glow-2" aria-hidden="true" />

      <aside className="sidebar glass">
        <div className="brand">
          <div className="brand-badge">I.AI</div>
          <div>
            <h1>InternAI</h1>
            <p>AI Internship Copilot</p>
          </div>
        </div>

        <div className="glass section-card floating">
          <span className="eyebrow">Resume Upload</span>
          <h2>Load Your Resume</h2>

          <label className="upload-box">
            <input
              type="file"
              accept=".pdf,application/pdf"
              hidden
              onChange={handleResumeUpload}
              disabled={isUploading || isAnalyzing}
            />
            <div className="upload-icon">{isUploading ? "..." : "↑"}</div>
            <p>{isUploading ? "Uploading resume..." : "Drop your resume or click to upload"}</p>
            <span>PDF supported. You can edit extracted text below.</span>
          </label>

          {uploadMessage ? <p className="state-message success">{uploadMessage}</p> : null}
          {uploadError ? <p className="state-message error">{uploadError}</p> : null}

          <label className="field-label" htmlFor="resume-text">
            Resume Text
          </label>
          <textarea
            id="resume-text"
            className="input-box tall"
            value={resumeText}
            onChange={(event) => setResumeText(event.target.value)}
            placeholder="Paste resume text or upload a PDF"
          />

          <label className="field-label" htmlFor="job-description">
            Job Description
          </label>
          <textarea
            id="job-description"
            className="input-box tall"
            value={jobDescription}
            onChange={(event) => setJobDescription(event.target.value)}
            placeholder="Paste internship/job description here"
          />

          <div className="settings-grid">
            <label className="settings-field">
              <span>Application question</span>
              <input
                value={applicationQuestion}
                onChange={(event) => setApplicationQuestion(event.target.value)}
                placeholder="Why should we hire you?"
              />
            </label>

            <label className="settings-field">
              <span>Tone</span>
              <select
                value={tone}
                onChange={(event) => setTone(event.target.value as Tone)}
              >
                {toneOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            <label className="settings-field">
              <span>Word limit</span>
              <input
                type="number"
                min={80}
                max={500}
                value={wordLimit}
                onChange={(event) => setWordLimit(Number(event.target.value))}
              />
            </label>

            <label className="settings-field">
              <span>Cover letter</span>
              <select
                value={coverLetterLength}
                onChange={(event) =>
                  setCoverLetterLength(event.target.value as CoverLetterLength)
                }
              >
                {lengthOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {analysisError ? <p className="state-message error">{analysisError}</p> : null}

          <button
            className="primary-btn full"
            type="button"
            onClick={handleAnalyze}
            disabled={isAnalyzing || isUploading}
          >
            {isAnalyzing ? "Analyzing..." : "Analyze Resume"}
          </button>
        </div>

        <div className="glass section-card">
          <span className="eyebrow">Quick Actions</span>

          <div className="quick-grid">
            <button className="glass mini-card" type="button" onClick={useSampleData}>
              Use Sample Data
            </button>
            <button className="glass mini-card" type="button" onClick={handleAnalyze}>
              Run Orchestrator
            </button>
            <button
              className="glass mini-card"
              type="button"
              onClick={() => copyText("answer", applicationAnswer)}
              disabled={!applicationAnswer}
            >
              Copy Application
            </button>
            <button
              className="glass mini-card"
              type="button"
              onClick={() => copyText("cover", coverLetter)}
              disabled={!coverLetter}
            >
              Copy Cover
            </button>
          </div>
        </div>
      </aside>

      <section className="dashboard">
        <div className="hero glass">
          <div className="hero-copy">
            <span className="status-pill">
              {result ? "Live Backend Analysis Complete" : "AI Powered Career Intelligence"}
            </span>

            <h2>
              Tailored insights to land your next internship
            </h2>

            <p>
              Upload a resume, paste a job description, run the FastAPI
              orchestrator, review dynamic recommendations, copy generated
              cover letters, and save applications into the SQLite tracker.
            </p>

            <div className="hero-actions">
              <button
                className="primary-btn"
                type="button"
                onClick={handleAnalyze}
                disabled={isAnalyzing || isUploading}
              >
                {isAnalyzing ? "Generating Insights..." : "Generate Insights"}
              </button>
              <button className="secondary-btn" type="button" onClick={useSampleData}>
                View Demo
              </button>
            </div>
          </div>

          <div className="hero-orb">
            <div className="orb-ring" />
            <div className="orb-core">
              <span>
                {typeof matchScore === "number"
                  ? `${matchScore}%`
                  : "--"}
              </span>
              <p>{result ? matchLevel : "Waiting..."}</p>
            </div>
          </div>
        </div>

        <section className="glass profile-summary-card">
          <div className="profile-main">
            <span className="eyebrow">Candidate Profile</span>
            <h3>{result ? candidateName : "Run an analysis to detect the candidate"}</h3>
            <p>{result ? roleCompanyLine : "Candidate, role, and company details will appear here."}</p>
          </div>

          <div className="profile-facts">
            <div>
              <span>Candidate</span>
              <strong>{result ? candidateName : "Not analyzed"}</strong>
            </div>
            <div>
              <span>Target Role</span>
              <strong>{result ? targetRole : "Not analyzed"}</strong>
            </div>
            <div>
              <span>Company</span>
              <strong>{result ? companyName : "Not analyzed"}</strong>
            </div>
            <div>
              <span>Match Score</span>
              <strong>{typeof matchScore === "number" ? `${matchScore}/100` : "--"}</strong>
            </div>
            <div>
              <span>Match Level</span>
              <strong>{result ? matchLevel : "--"}</strong>
            </div>
          </div>
        </section>

        <div className="stats-grid">
          {stats.map((item) => (
            <div className="glass stat-card" key={item.label}>
              <span>{item.label}</span>
              <h3>{item.value}</h3>
            </div>
          ))}
        </div>

        <section className="glass analytics-card">
          <div className="card-head">
            <div>
              <span className="eyebrow">Skill Intelligence</span>
              <h3>Matched and Missing Technologies</h3>
            </div>
            <button className="tag-btn" type="button">
              {result ? "Live Analysis" : "Waiting"}
            </button>
          </div>

          <div className="skill-intelligence-grid">
            <div className="skill-panel">
              <span className="eyebrow">Matched</span>
              <h4>Technologies you already show</h4>
              <div className="skills-wrap">
                {matchedSkills.length ? (
                  matchedSkills.map((skill) => (
                    <span key={`matched-${skill}`} className="skill-pill">
                      {skill}
                    </span>
                  ))
                ) : (
                  <p className="empty-copy">Run an analysis to see matched skills.</p>
                )}
              </div>
            </div>

            <div className="skill-panel">
              <span className="eyebrow">Missing</span>
              <h4>Skills to strengthen next</h4>
              <div className="skills-wrap">
                {missingSkills.length ? (
                  missingSkills.slice(0, 12).map((skill) => (
                    <span key={`missing-${skill}`} className="skill-pill missing">
                      {skill}
                    </span>
                  ))
                ) : (
                  <p className="empty-copy">No missing skills to show yet.</p>
                )}
              </div>
            </div>
          </div>

          {result?.match_result?.score_breakdown ? (
            <div className="score-breakdown-grid">
              {[
                ["Required", result.match_result.score_breakdown.required_skills],
                ["Preferred", result.match_result.score_breakdown.preferred_skills],
                ["Projects", result.match_result.score_breakdown.project_relevance],
                ["Education", result.match_result.score_breakdown.education_relevance],
                [
                  "Experience",
                  result.match_result.score_breakdown.experience_certifications,
                ],
              ].map(([label, value]) => (
                <div className="score-chip" key={String(label)}>
                  <span>{label}</span>
                  <strong>{typeof value === "number" ? value : "--"}</strong>
                </div>
              ))}
            </div>
          ) : null}
        </section>

        <section className="glass roadmap-card wide-section">
          <div className="card-head">
            <div>
              <span className="eyebrow">Learning Path</span>
              <h3>AI Generated Roadmap</h3>
              <p className="section-subtitle">
                Prioritized learning path based on your missing skills.
              </p>
            </div>
          </div>

          {prioritySkills.length ? (
            <div className="skills-wrap compact">
              {prioritySkills.map((skill) => (
                <span key={`roadmap-priority-${skill}`} className="skill-pill">
                  {skill}
                </span>
              ))}
            </div>
          ) : null}

          <div className="roadmap-grid">
            {roadmap.length ? (
              roadmap.map((item) => (
                <article key={`${item.week}-${item.focus}`} className="roadmap-card-item">
                  <span className="roadmap-week">Week {item.week}</span>
                  <h4>{item.focus}</h4>
                  {item.skills?.length ? (
                    <div className="roadmap-skills">
                      {item.skills.slice(0, 4).map((skill) => (
                        <span key={`${item.week}-${skill}`}>{skill}</span>
                      ))}
                    </div>
                  ) : null}
                  {item.tasks?.length ? (
                    <ul>
                      {item.tasks.slice(0, 3).map((task) => (
                        <li key={`${item.week}-${task}`}>{task}</li>
                      ))}
                    </ul>
                  ) : null}
                  {item.outcome ? <p>{item.outcome}</p> : null}
                </article>
              ))
            ) : (
              <p className="empty-copy">Run an analysis to generate a roadmap.</p>
            )}
          </div>
        </section>

        <section className="generated-content-grid">
          <div className="glass lower-panel">
            <div className="card-head">
              <div>
                <span className="eyebrow">Generated Content</span>
                <h3>Application Answer</h3>
              </div>
              <button
                className="primary-btn small"
                type="button"
                onClick={() => copyText("answer", applicationAnswer)}
                disabled={!applicationAnswer}
              >
                {copiedTarget === "answer" ? "Copied!" : "Copy Answer"}
              </button>
            </div>

            <div className="cover-preview generated-preview">
              {applicationAnswer ? (
                <p>{applicationAnswer}</p>
              ) : (
                <p>Run an analysis to generate a tailored application answer.</p>
              )}
            </div>
          </div>

          <div className="glass lower-panel">
            <div className="card-head">
              <div>
                <span className="eyebrow">Generated Content</span>
                <h3>Cover Letter Preview</h3>
              </div>
              <button
                className="primary-btn small"
                type="button"
                onClick={() => copyText("cover", coverLetter)}
                disabled={!coverLetter}
              >
                {copiedTarget === "cover" ? "Copied!" : "Copy Content"}
              </button>
            </div>

            <div className="cover-preview generated-preview">
              {coverLetter ? (
                coverLetter.split("\n").map((paragraph, index) =>
                  paragraph.trim() ? <p key={`${paragraph}-${index}`}>{paragraph}</p> : null,
                )
              ) : (
                <p>Run an analysis to generate a cover letter preview.</p>
              )}
            </div>
          </div>
        </section>

        <section className="glass lower-panel tracker-section">
          <div className="card-head">
            <div>
              <span className="eyebrow">Application Tracker</span>
              <h3>Application Tracker</h3>
              <p className="section-subtitle">
                Saved applications from the orchestrator pipeline.
              </p>
            </div>
            <button
              className="primary-btn small"
              type="button"
              onClick={handleSaveApplication}
              disabled={!result || isSaving || hasSavedCurrentResult}
            >
              {isSaving
                ? "Saving..."
                : hasSavedCurrentResult
                  ? "Saved"
                  : "Save Application"}
            </button>
          </div>

          {prioritySkills.length ? (
            <div className="skills-wrap compact">
              {prioritySkills.map((skill) => (
                <span key={`priority-${skill}`} className="skill-pill">
                  {skill}
                </span>
              ))}
            </div>
          ) : null}

          {saveMessage ? <p className="state-message success">{saveMessage}</p> : null}
          {saveError ? <p className="state-message error">{saveError}</p> : null}

          <ApplicationTracker refreshKey={trackerRefreshKey} />
        </section>
      </section>
    </main>
  );
}
