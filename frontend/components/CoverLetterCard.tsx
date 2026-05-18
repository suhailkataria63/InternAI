"use client";

import { useState } from "react";
import type { CoverLetterResult } from "../lib/types";

type CoverLetterCardProps = {
  coverLetter: CoverLetterResult;
};

export default function CoverLetterCard({ coverLetter }: CoverLetterCardProps) {
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "error">("idle");
  const letter = coverLetter.cover_letter || "";

  const copyCoverLetter = async () => {
    try {
      await navigator.clipboard.writeText(letter);
      setCopyStatus("copied");
      window.setTimeout(() => setCopyStatus("idle"), 1800);
    } catch {
      setCopyStatus("error");
    }
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Cover Letter
          </p>
          <h3 className="mt-1 text-lg font-semibold text-slate-950">
            {coverLetter.subject_line || "Subject line will appear here"}
          </h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
            {coverLetter.word_count ?? 0} words
          </span>
          <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-800">
            {coverLetter.tone || "professional"}
          </span>
          <button
            type="button"
            onClick={copyCoverLetter}
            disabled={!letter}
            className="rounded-lg bg-slate-950 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {copyStatus === "copied" ? "Copied!" : "Copy cover letter"}
          </button>
        </div>
      </div>

      {copyStatus === "error" ? (
        <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
          Could not copy. Please select the text manually.
        </p>
      ) : null}

      {coverLetter.opening_summary ? (
        <p className="mt-4 rounded-xl bg-indigo-50 p-3 text-sm font-medium text-indigo-950">
          {coverLetter.opening_summary}
        </p>
      ) : null}

      <p className="mt-4 whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-800">
        {letter || "No cover letter generated yet."}
      </p>

      <div className="mt-4">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Key points used
        </p>
        {(coverLetter.key_points_used || []).length ? (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
            {coverLetter.key_points_used?.map((point) => <li key={point}>{point}</li>)}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-slate-500">No key points returned.</p>
        )}
      </div>
    </section>
  );
}
