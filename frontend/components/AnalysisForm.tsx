"use client";

import { useState } from "react";
import { analyzeApplication, uploadResumePdf } from "../lib/api";
import type {
  AnalysisRequest,
  AnalysisResponse,
  CoverLetterLength,
  Tone,
} from "../lib/types";

const sampleResume = `Jane Doe
jane@example.com
Education
B.S. Computer Science
Skills
Python, FastAPI, React
Projects
Hybrid Phishing Detection System using Python, Machine Learning, and React
Experience
Open source backend documentation contributor`;

const sampleJobDescription = `Role: Software Engineering Intern
Company: Acme Labs
Location: Bengaluru
Work mode: Hybrid
Duration: 6 months
Required Skills
Python, FastAPI, SQL
Preferred Skills
Docker
Responsibilities
Build backend APIs
Write SQL queries`;

const defaultForm: AnalysisRequest = {
  resume_text: "",
  job_description: "",
  application_question: "Why should we hire you?",
  tone: "professional",
  word_limit: 180,
  cover_letter_length: "short",
};

type AnalysisFormProps = {
  onResult: (result: AnalysisResponse) => void;
};

function FieldLabel({
  title,
  helper,
}: {
  title: string;
  helper?: string;
}) {
  return (
    <span className="block">
      <span className="block text-sm font-black text-slate-900">{title}</span>
      {helper ? <span className="mt-1 block text-xs leading-5 text-slate-500">{helper}</span> : null}
    </span>
  );
}

export default function AnalysisForm({ onResult }: AnalysisFormProps) {
  const [form, setForm] = useState<AnalysisRequest>(defaultForm);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploadingResume, setIsUploadingResume] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [error, setError] = useState("");

  const updateField = <K extends keyof AnalysisRequest>(
    key: K,
    value: AnalysisRequest[K],
  ) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const useSampleData = () => {
    setForm({
      resume_text: sampleResume,
      job_description: sampleJobDescription,
      application_question: "Why should we hire you?",
      tone: "professional",
      word_limit: 180,
      cover_letter_length: "short",
    });
    setError("");
    setUploadMessage("");
    setUploadError("");
  };

  const handleResumeUpload = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];
    setUploadMessage("");
    setUploadError("");

    if (!file) return;

    const isPdf =
      file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

    if (!isPdf) {
      setUploadError("Please upload a PDF resume or paste the resume text manually.");
      event.target.value = "";
      return;
    }

    setIsUploadingResume(true);
    try {
      const uploaded = await uploadResumePdf(file);
      const extractedText = uploaded.extracted_text || "";

      if (!extractedText.trim()) {
        setUploadError("PDF uploaded, but no text could be extracted.");
        return;
      }

      updateField("resume_text", extractedText);
      setUploadMessage(
        `Uploaded ${uploaded.filename || file.name}. Extracted ${uploaded.text_length ?? extractedText.length} characters.`,
      );
    } catch (caughtError) {
      const message =
        caughtError instanceof Error
          ? caughtError.message
          : "Failed to extract resume text. Please paste resume text manually.";

      setUploadError(
        message.includes("Could not reach")
          ? message
          : "Failed to extract resume text. Please paste resume text manually.",
      );
    } finally {
      setIsUploadingResume(false);
      event.target.value = "";
    }
  };

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const result = await analyzeApplication(form);
      onResult(result);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Something went wrong while running the analysis.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="premium-card reveal rounded-[2rem] p-5 sm:p-6">
      <div className="flex flex-col gap-4 border-b border-slate-200/80 pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.22em] text-blue-700">
            Analysis input
          </p>
          <h2 className="mt-2 text-2xl font-black text-slate-950">
            Run full application analysis
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Upload a resume or paste text, add a job description, then generate a complete match report and application assets.
          </p>
        </div>
        <button
          type="button"
          onClick={useSampleData}
          className="inline-flex items-center justify-center rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 shadow-sm transition hover:-translate-y-0.5 hover:border-blue-200 hover:text-blue-700"
        >
          Use sample data
        </button>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div className="space-y-5">
          <div className="rounded-2xl border border-blue-100 bg-blue-50/70 p-4">
            <label className="block">
              <FieldLabel
                title="Upload resume PDF"
                helper="PDF extraction is fastest. You can still edit the extracted text before analysis."
              />
              <input
                type="file"
                accept=".pdf,application/pdf"
                onChange={handleResumeUpload}
                disabled={isUploadingResume}
                className="mt-4 block w-full rounded-xl border border-blue-100 bg-white px-3 py-2 text-sm text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-950 file:px-3 file:py-1.5 file:text-sm file:font-bold file:text-white hover:file:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-70"
              />
            </label>

            {isUploadingResume ? (
              <p className="mt-3 rounded-xl bg-white px-3 py-2 text-sm font-medium text-slate-700">
                Extracting resume text...
              </p>
            ) : null}
            {uploadMessage ? (
              <p className="mt-3 rounded-xl bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800">
                {uploadMessage}
              </p>
            ) : null}
            {uploadError ? (
              <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">
                {uploadError}
              </p>
            ) : null}
          </div>

          <label className="block">
            <FieldLabel title="Resume text" helper="Keep education, skills, projects, and experience sections intact." />
            <div className="field-shell mt-2 rounded-2xl">
              <textarea
                value={form.resume_text}
                onChange={(event) => updateField("resume_text", event.target.value)}
                className="h-72 w-full resize-y rounded-2xl bg-transparent p-4 text-sm leading-6 text-slate-800 outline-none placeholder:text-slate-400"
                placeholder="Paste extracted resume text here, or upload a PDF above..."
              />
            </div>
          </label>
        </div>

        <label className="block">
          <FieldLabel title="Job description" helper="Paste the full role description, requirements, company, and location if available." />
          <div className="field-shell mt-2 rounded-2xl">
            <textarea
              value={form.job_description}
              onChange={(event) =>
                updateField("job_description", event.target.value)
              }
              className="h-[27.5rem] w-full resize-y rounded-2xl bg-transparent p-4 text-sm leading-6 text-slate-800 outline-none placeholder:text-slate-400"
              placeholder="Paste internship or job description here..."
            />
          </div>
        </label>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <label className="block md:col-span-2">
          <FieldLabel title="Application question" />
          <div className="field-shell mt-2 rounded-2xl">
            <input
              value={form.application_question}
              onChange={(event) =>
                updateField("application_question", event.target.value)
              }
              className="w-full rounded-2xl bg-transparent px-4 py-3 text-sm text-slate-800 outline-none"
            />
          </div>
        </label>

        <label className="block">
          <FieldLabel title="Tone" />
          <div className="field-shell mt-2 rounded-2xl">
            <select
              value={form.tone}
              onChange={(event) => updateField("tone", event.target.value as Tone)}
              className="w-full rounded-2xl bg-transparent px-4 py-3 text-sm text-slate-800 outline-none"
            >
              <option value="professional">professional</option>
              <option value="confident">confident</option>
              <option value="friendly">friendly</option>
              <option value="concise">concise</option>
            </select>
          </div>
        </label>

        <label className="block">
          <FieldLabel title="Word limit" />
          <div className="field-shell mt-2 rounded-2xl">
            <input
              type="number"
              min={40}
              max={500}
              value={form.word_limit}
              onChange={(event) =>
                updateField("word_limit", Number(event.target.value))
              }
              className="w-full rounded-2xl bg-transparent px-4 py-3 text-sm text-slate-800 outline-none"
            />
          </div>
        </label>

        <label className="block md:col-span-2 xl:col-span-1">
          <FieldLabel title="Cover letter length" />
          <div className="field-shell mt-2 rounded-2xl">
            <select
              value={form.cover_letter_length}
              onChange={(event) =>
                updateField(
                  "cover_letter_length",
                  event.target.value as CoverLetterLength,
                )
              }
              className="w-full rounded-2xl bg-transparent px-4 py-3 text-sm text-slate-800 outline-none"
            >
              <option value="short">short</option>
              <option value="medium">medium</option>
            </select>
          </div>
        </label>
      </div>

      {error ? (
        <div className="mt-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
          {error}
        </div>
      ) : null}

      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs leading-5 text-slate-500">
          Your backend handles the analysis. This frontend keeps the workflow clear, accessible, and responsive.
        </p>
        <button
          type="submit"
          disabled={isLoading}
          className="inline-flex min-w-40 items-center justify-center rounded-2xl bg-blue-600 px-5 py-3 text-sm font-black text-white shadow-glow transition hover:-translate-y-0.5 hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400 disabled:shadow-none"
        >
          {isLoading ? "Analyzing..." : "Analyze now"}
        </button>
      </div>
    </form>
  );
}
