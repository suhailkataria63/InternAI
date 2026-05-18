"use client";

import { useState } from "react";
import AnalysisForm from "../components/AnalysisForm";
import ApplicationTracker from "../components/ApplicationTracker";
import ResultsDashboard from "../components/ResultsDashboard";
import type { AnalysisResponse } from "../lib/types";

export default function Home() {
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [trackerRefreshKey, setTrackerRefreshKey] = useState(0);

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-8">
          <p className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            InternAI
          </p>
          <div className="mt-3 grid gap-4 lg:grid-cols-[1fr_420px] lg:items-end">
            <div>
              <h1 className="max-w-4xl text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
                Multi-agent internship application assistant
              </h1>
              <p className="mt-3 max-w-3xl text-base leading-7 text-slate-600">
                Run resume analysis, JD analysis, match scoring, skill-gap
                planning, application writing, and cover letter generation from
                one orchestrator workflow.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-soft">
              <p className="text-sm font-semibold text-slate-900">
                Backend endpoint
              </p>
              <p className="mt-1 break-all text-sm text-slate-600">
                /api/orchestrator/analyze-application
              </p>
            </div>
          </div>
        </header>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_520px] xl:items-start">
          <AnalysisForm onResult={setResult} />
          <ResultsDashboard
            result={result}
            onSaved={() => setTrackerRefreshKey((current) => current + 1)}
          />
        </div>
        <ApplicationTracker refreshKey={trackerRefreshKey} />
      </div>
    </main>
  );
}
