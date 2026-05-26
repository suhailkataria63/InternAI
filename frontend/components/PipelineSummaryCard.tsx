import type { PipelineSummary } from "../lib/types";

type PipelineSummaryCardProps = {
  summary: PipelineSummary;
};

export default function PipelineSummaryCard({ summary }: PipelineSummaryCardProps) {
  const facts = [
    ["Candidate", summary.candidate_name || "Unknown"],
    ["Target role", summary.target_role || "Not detected"],
    ["Company", summary.company_name || "Not detected"],
    ["Match score", summary.match_score != null ? `${summary.match_score}/100` : "Not scored"],
    ["Match level", summary.match_level || "Pending"],
  ];

  return (
    <section className="premium-card rounded-[1.75rem] p-5">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500">
            Pipeline Summary
          </p>
          <h3 className="mt-1 text-lg font-black text-slate-950">
            Internship match report
          </h3>
        </div>
        <span className="rounded-full bg-slate-950 shadow-sm px-3 py-1 text-xs font-semibold text-white">
          {summary.match_level || "Pending"}
        </span>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {facts.map(([label, value]) => (
          <div key={label} className="rounded-2xl bg-slate-50/90 p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              {label}
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
        <p className="text-xs font-black uppercase tracking-[0.18em] text-emerald-700">
          Recommended next step
        </p>
        <p className="mt-1 text-sm leading-6 text-emerald-950">
          {summary.recommended_next_step || "Review the score breakdown and decide whether to apply or improve the resume first."}
        </p>
      </div>
    </section>
  );
}
