"use client";

import { useState } from "react";
import { saveApplicationAnalysis } from "../lib/api";
import type { AnalysisResponse } from "../lib/types";
import ApplicationAnswerCard from "./ApplicationAnswerCard";
import CoverLetterCard from "./CoverLetterCard";
import MatchScoreCard from "./MatchScoreCard";
import PipelineSummaryCard from "./PipelineSummaryCard";
import SkillGapCard from "./SkillGapCard";

type ResultsDashboardProps = {
  result: AnalysisResponse | null;
  onSaved?: () => void;
};

export default function ResultsDashboard({ result, onSaved }: ResultsDashboardProps) {
  const [saveMessage, setSaveMessage] = useState("");
  const [saveError, setSaveError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  if (!result) {
    return (
      <section className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center shadow-soft">
        <h2 className="text-lg font-semibold text-slate-950">Results Dashboard</h2>
        <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          Run an analysis to see the pipeline summary, match score, skill gaps,
          application answer, and cover letter in separate sections.
        </p>
      </section>
    );
  }

  const saveCurrentApplication = async () => {
    setIsSaving(true);
    setSaveMessage("");
    setSaveError("");
    try {
      const saved = await saveApplicationAnalysis(result);
      setSaveMessage(`Saved application #${saved.id}.`);
      onSaved?.();
    } catch (error) {
      setSaveError(
        error instanceof Error ? error.message : "Could not save application.",
      );
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-950">
              Save This Analysis
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Store this application in the SQLite tracker.
            </p>
          </div>
          <button
            type="button"
            onClick={saveCurrentApplication}
            disabled={isSaving}
            className="rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {isSaving ? "Saving..." : "Save Application"}
          </button>
        </div>
        {saveMessage ? (
          <p className="mt-3 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            {saveMessage}
          </p>
        ) : null}
        {saveError ? (
          <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
            {saveError}
          </p>
        ) : null}
      </section>
      <PipelineSummaryCard summary={result.pipeline_summary} />
      <MatchScoreCard
        match={result.match_result}
        summary={result.pipeline_summary}
      />
      <SkillGapCard skillGap={result.skill_gap_result} />
      <ApplicationAnswerCard answer={result.application_answer} />
      <CoverLetterCard coverLetter={result.cover_letter} />
    </div>
  );
}
