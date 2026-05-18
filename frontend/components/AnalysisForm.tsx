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

    if (!file) {
      return;
    }

    const isPdf =
      file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      setUploadError("Failed to extract resume text. Please paste resume text manually.");
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
        `Uploaded ${uploaded.filename || file.name} successfully. Extracted ${uploaded.text_length ?? extractedText.length} characters.`,
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
    <form
      onSubmit={submit}
      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">
            Run Full Analysis
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Paste a resume and job description to run the orchestrator pipeline.
          </p>
        </div>
        <button
          type="button"
          onClick={useSampleData}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
        >
          Use Sample Data
        </button>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <label className="block">
              <span className="text-sm font-medium text-slate-800">
                Upload resume PDF
              </span>
              <span className="mt-1 block text-sm text-slate-600">
                Upload a PDF to automatically extract resume text.
              </span>
              <span className="mt-1 block text-xs leading-5 text-slate-500">
                PDF text extraction may not preserve exact visual order, but the
                analyzer will still use the extracted content.
              </span>
              <input
                type="file"
                accept=".pdf,application/pdf"
                onChange={handleResumeUpload}
                disabled={isUploadingResume}
                className="mt-3 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-slate-950 file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-white hover:file:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70"
              />
            </label>
            {isUploadingResume ? (
              <p className="mt-3 rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-700">
                Extracting resume text...
              </p>
            ) : null}
            {uploadMessage ? (
              <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                {uploadMessage}
              </p>
            ) : null}
            {uploadError ? (
              <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                {uploadError}
              </p>
            ) : null}
          </div>

          <label className="block">
            <span className="text-sm font-medium text-slate-800">Resume text</span>
            <textarea
              value={form.resume_text}
              onChange={(event) => updateField("resume_text", event.target.value)}
              className="mt-2 h-72 w-full resize-y rounded-xl border border-slate-300 bg-slate-50 p-3 text-sm leading-6 outline-none transition focus:border-slate-500 focus:bg-white focus:ring-4 focus:ring-slate-100"
              placeholder="Paste extracted resume text here, or upload a PDF above..."
            />
          </label>
        </div>

        <label className="block">
          <span className="text-sm font-medium text-slate-800">
            Job description
          </span>
          <textarea
            value={form.job_description}
            onChange={(event) =>
              updateField("job_description", event.target.value)
            }
            className="mt-2 h-72 w-full resize-y rounded-xl border border-slate-300 bg-slate-50 p-3 text-sm leading-6 outline-none transition focus:border-slate-500 focus:bg-white focus:ring-4 focus:ring-slate-100"
            placeholder="Paste internship or job description here..."
          />
        </label>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <label className="block md:col-span-2">
          <span className="text-sm font-medium text-slate-800">
            Application question
          </span>
          <input
            value={form.application_question}
            onChange={(event) =>
              updateField("application_question", event.target.value)
            }
            className="mt-2 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm outline-none transition focus:border-slate-500 focus:bg-white focus:ring-4 focus:ring-slate-100"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium text-slate-800">Tone</span>
          <select
            value={form.tone}
            onChange={(event) => updateField("tone", event.target.value as Tone)}
            className="mt-2 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm outline-none transition focus:border-slate-500 focus:bg-white focus:ring-4 focus:ring-slate-100"
          >
            <option value="professional">professional</option>
            <option value="confident">confident</option>
            <option value="friendly">friendly</option>
            <option value="concise">concise</option>
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-medium text-slate-800">Word limit</span>
          <input
            type="number"
            min={40}
            max={500}
            value={form.word_limit}
            onChange={(event) =>
              updateField("word_limit", Number(event.target.value))
            }
            className="mt-2 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm outline-none transition focus:border-slate-500 focus:bg-white focus:ring-4 focus:ring-slate-100"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium text-slate-800">
            Cover letter length
          </span>
          <select
            value={form.cover_letter_length}
            onChange={(event) =>
              updateField(
                "cover_letter_length",
                event.target.value as CoverLetterLength,
              )
            }
            className="mt-2 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm outline-none transition focus:border-slate-500 focus:bg-white focus:ring-4 focus:ring-slate-100"
          >
            <option value="short">short</option>
            <option value="medium">medium</option>
          </select>
        </label>
      </div>

      {error ? (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <button
        type="submit"
        disabled={isLoading}
        className="mt-5 w-full rounded-xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400 sm:w-auto"
      >
        {isLoading ? "Analyzing..." : "Analyze"}
      </button>
    </form>
  );
}
