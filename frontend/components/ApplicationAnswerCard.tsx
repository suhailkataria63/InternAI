"use client";

import { useState } from "react";
import type { ApplicationAnswer } from "../lib/types";

type ApplicationAnswerCardProps = {
  answer: ApplicationAnswer;
};

export default function ApplicationAnswerCard({ answer }: ApplicationAnswerCardProps) {
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "error">("idle");
  const generatedAnswer = answer.generated_answer || "";

  const copyAnswer = async () => {
    try {
      await navigator.clipboard.writeText(generatedAnswer);
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
            Application Answer
          </p>
          <h3 className="mt-1 text-lg font-semibold text-slate-950">
            {answer.question || "Application question"}
          </h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
            {answer.word_count ?? 0} words
          </span>
          <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-800">
            {answer.tone || "professional"}
          </span>
          <button
            type="button"
            onClick={copyAnswer}
            disabled={!generatedAnswer}
            className="rounded-lg bg-slate-950 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {copyStatus === "copied" ? "Copied!" : "Copy answer"}
          </button>
        </div>
      </div>

      {copyStatus === "error" ? (
        <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
          Could not copy. Please select the text manually.
        </p>
      ) : null}

      <p className="mt-4 whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-800">
        {generatedAnswer || "No answer generated yet."}
      </p>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Key points used
          </p>
          {(answer.key_points_used || []).length ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
              {answer.key_points_used?.map((point) => <li key={point}>{point}</li>)}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-slate-500">No key points returned.</p>
          )}
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Improvement note
          </p>
          <p className="mt-2 rounded-xl bg-amber-50 p-3 text-sm leading-6 text-amber-950">
            {answer.improvement_note || "Review the answer for company-specific details before submitting."}
          </p>
        </div>
      </div>
    </section>
  );
}
