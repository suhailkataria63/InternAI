"use client";

import { useEffect, useState } from "react";
import { saveApplicationAnalysis } from "../lib/api";
import type { AnalysisResponse, MatchResult } from "../lib/types";
import ApplicationAnswerCard from "./ApplicationAnswerCard";
import CoverLetterCard from "./CoverLetterCard";
import MatchScoreCard from "./MatchScoreCard";
import PipelineSummaryCard from "./PipelineSummaryCard";
import SkillBadge from "./SkillBadge";
import SkillGapCard from "./SkillGapCard";

type ResultsDashboardProps = {
  result: AnalysisResponse | null;
  onSaved?: () => void;
};

type SkillGroupProps = {
  title: string;
  skills?: string[];
  tone: "positive" | "missing" | "neutral";
};

const breakdownLabels: Array<[keyof NonNullable<MatchResult["score_breakdown"]>, string]> = [
  ["required_skills", "Required skills"],
  ["preferred_skills", "Preferred skills"],
  ["project_relevance", "Project relevance"],
  ["education_relevance", "Education relevance"],
  ["experience_certifications", "Experience/certifications"],
];

function ScoreBreakdown({ match }: { match: MatchResult }) {
  const breakdown = match.score_breakdown || {};

  return (
    <section className="premium-card rounded-[1.75rem] p-5">
      <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500">
        Score Breakdown
      </p>
      <h3 className="mt-1 text-lg font-black text-slate-950">
        Where the score came from
      </h3>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {breakdownLabels.map(([key, label]) => {
          const value = breakdown[key];
          return (
            <div key={key} className="rounded-2xl bg-slate-50/90 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                {label}
              </p>
              <p className="mt-2 text-2xl font-semibold text-slate-950">
                {typeof value === "number" ? value : "Not available"}
              </p>
            </div>
          );
        })}
      </div>
      {(breakdown.education_note || breakdown.experience_note) ? (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {typeof breakdown.education_note === "string" ? (
            <p className="rounded-2xl bg-slate-50/90 p-3 text-sm leading-6 text-slate-700">
              {breakdown.education_note}
            </p>
          ) : null}
          {typeof breakdown.experience_note === "string" ? (
            <p className="rounded-2xl bg-slate-50/90 p-3 text-sm leading-6 text-slate-700">
              {breakdown.experience_note}
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function SkillGroup({ title, skills, tone }: SkillGroupProps) {
  const list = skills || [];

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-slate-50/80 p-4">
      <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500">
        {title}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {list.length ? (
          list.map((skill) => <SkillBadge key={`${title}-${skill}`} label={skill} tone={tone} />)
        ) : (
          <span className="text-sm text-slate-500">None found</span>
        )}
      </div>
    </div>
  );
}

function SkillsOverview({ match }: { match: MatchResult }) {
  return (
    <section className="premium-card rounded-[1.75rem] p-5">
      <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500">
        Skills Overview
      </p>
      <h3 className="mt-1 text-lg font-black text-slate-950">
        Matched and missing skills
      </h3>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <SkillGroup title="Matched required skills" skills={match.matched_required_skills} tone="positive" />
        <SkillGroup title="Missing required skills" skills={match.missing_required_skills} tone="missing" />
        <SkillGroup title="Matched preferred skills" skills={match.matched_preferred_skills} tone="positive" />
        <SkillGroup title="Missing preferred skills" skills={match.missing_preferred_skills} tone="missing" />
        <SkillGroup title="General matched skills" skills={match.matched_skills} tone="neutral" />
        <SkillGroup title="General missing skills" skills={match.missing_skills} tone="neutral" />
      </div>
    </section>
  );
}

export default function ResultsDashboard({ result, onSaved }: ResultsDashboardProps) {
  const [saveMessage, setSaveMessage] = useState("");
  const [saveError, setSaveError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [hasSaved, setHasSaved] = useState(false);

  useEffect(() => {
    setSaveMessage("");
    setSaveError("");
    setIsSaving(false);
    setHasSaved(false);
  }, [result]);

  if (!result) {
    return (
      <section className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center shadow-soft">
        <h2 className="text-lg font-black text-slate-950">Results Dashboard</h2>
        <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          Run an analysis to see your internship match report.
        </p>
      </section>
    );
  }

  const saveCurrentApplication = async () => {
    if (hasSaved || isSaving) return;

    setIsSaving(true);
    setSaveMessage("");
    setSaveError("");
    try {
      await saveApplicationAnalysis(result);
      setHasSaved(true);
      setSaveMessage("Application saved successfully");
      onSaved?.();
    } catch (error) {
      setSaveError(
        error instanceof Error ? error.message : "Failed to save application",
      );
    } finally {
      setIsSaving(false);
    }
  };

  const saveButtonLabel = isSaving
    ? "Saving..."
    : hasSaved
      ? "Application saved successfully"
      : "Save Application";
  const candidateName =
    result.pipeline_summary?.candidate_name ||
    result.resume_profile?.name ||
    "Candidate name not detected";
  const targetRole =
    result.pipeline_summary?.target_role ||
    result.job_profile?.role_title ||
    "Target role not detected";
  const companyName =
    result.pipeline_summary?.company_name ||
    result.job_profile?.company_name ||
    "Company not detected";
  const matchScore =
    result.pipeline_summary?.match_score ??
    result.match_result?.match_score;
  const matchLevel =
    result.pipeline_summary?.match_level ||
    result.match_result?.match_level ||
    "Not available";
  const hydratedSummary = {
    ...(result.pipeline_summary || {}),
    candidate_name: candidateName,
    target_role: targetRole,
    company_name: companyName,
    match_score: matchScore,
    match_level: matchLevel,
  };

  return (
    <div className="space-y-5">
      <PipelineSummaryCard summary={hydratedSummary} />
      <MatchScoreCard
        match={result.match_result || {}}
        summary={hydratedSummary}
      />
      <ScoreBreakdown match={result.match_result || {}} />
      <SkillsOverview match={result.match_result || {}} />
      <SkillGapCard skillGap={result.skill_gap_result || {}} />
      <ApplicationAnswerCard answer={result.application_answer || {}} />
      <CoverLetterCard coverLetter={result.cover_letter || {}} />

      <section className="premium-card rounded-[1.75rem] p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500">
              Tracker
            </p>
            <h3 className="mt-1 text-lg font-black text-slate-950">
              Save this application
            </h3>
            <p className="mt-1 text-sm text-slate-600">
              Store this analysis in the SQLite tracker for follow-up.
            </p>
          </div>
          <button
            type="button"
            onClick={saveCurrentApplication}
            disabled={isSaving || hasSaved}
            className="rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {saveButtonLabel}
          </button>
        </div>
        {saveMessage ? (
          <p className="mt-3 rounded-2xl bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            {saveMessage}
          </p>
        ) : null}
        {saveError ? (
          <p className="mt-3 rounded-2xl bg-red-50 px-3 py-2 text-sm text-red-700">
            Failed to save application: {saveError}
          </p>
        ) : null}
      </section>
    </div>
  );
}
