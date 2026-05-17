import type { PipelineSummary } from "../lib/types";

type PipelineSummaryCardProps = {
  summary: PipelineSummary;
};

export default function PipelineSummaryCard({ summary }: PipelineSummaryCardProps) {
  const facts = [
    ["Candidate", summary.candidate_name || "Unknown"],
    ["Target role", summary.target_role || "Not detected"],
    ["Company", summary.company_name || "Not detected"],
    ["Match level", summary.match_level || "Pending"],
  ];

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
      <h3 className="text-base font-semibold text-slate-950">Pipeline Summary</h3>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {facts.map(([label, value]) => (
          <div key={label} className="rounded-xl bg-slate-50 p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              {label}
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
          </div>
        ))}
      </div>
      <p className="mt-4 rounded-xl bg-emerald-50 p-3 text-sm leading-6 text-emerald-900">
        {summary.recommended_next_step || "Run an analysis to see the next step."}
      </p>
    </section>
  );
}
