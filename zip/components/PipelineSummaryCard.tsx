import type { PipelineSummary } from "../lib/types";

type PipelineSummaryCardProps = {
  summary: PipelineSummary;
};

export default function PipelineSummaryCard({ summary }: PipelineSummaryCardProps) {
  const candidateName = summary.candidate_name || "Candidate name not detected";
  const targetRole = summary.target_role || "Target role not detected";
  const companyName = summary.company_name || "Company not detected";
  const roleLine =
    targetRole === "Target role not detected"
      ? targetRole
      : summary.company_name
        ? `${targetRole} at ${companyName}`
        : targetRole;
  const matchScore =
    typeof summary.match_score === "number" ? `${summary.match_score}/100` : "Not scored";
  const matchLevel = summary.match_level || "Not available";
  const facts = [
    ["Candidate", candidateName],
    ["Target role", targetRole],
    ["Company", companyName],
    ["Match score", matchScore],
    ["Match level", matchLevel],
  ];

  return (
    <section className="premium-card rounded-[1.75rem] p-5">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500">
            Pipeline Summary
          </p>
          <h3 className="mt-1 text-2xl font-black text-slate-950">
            {candidateName}
          </h3>
          <p className="mt-1 text-sm font-semibold text-slate-600">{roleLine}</p>
        </div>
        <span className="rounded-full bg-slate-950 shadow-sm px-3 py-1 text-xs font-semibold text-white">
          {matchLevel}
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
