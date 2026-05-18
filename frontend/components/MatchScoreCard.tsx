import type { MatchResult, PipelineSummary } from "../lib/types";

type MatchScoreCardProps = {
  match: MatchResult;
  summary: PipelineSummary;
};

function percentageLabel(value?: number): string {
  return value == null ? "Not available" : `${value}%`;
}

export default function MatchScoreCard({ match, summary }: MatchScoreCardProps) {
  const score = match.match_score ?? summary.match_score;
  const scoreLabel = score == null ? "N/A" : `${score}/100`;
  const level = match.match_level || summary.match_level || "Not scored";

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
      <div className="grid gap-5 md:grid-cols-[150px_1fr] md:items-center">
        <div className="flex h-36 w-36 flex-col items-center justify-center rounded-full border border-slate-200 bg-slate-950 text-white shadow-sm">
          <span className="text-3xl font-bold">{scoreLabel}</span>
          <span className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-300">
            Match score
          </span>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Match Score
          </p>
          <h3 className="mt-1 text-xl font-semibold text-slate-950">{level}</h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl bg-slate-50 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Required skill match
              </p>
              <p className="mt-1 text-2xl font-semibold text-slate-950">
                {percentageLabel(match.required_skill_match_percentage)}
              </p>
            </div>
            <div className="rounded-xl bg-slate-50 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Preferred skill match
              </p>
              <p className="mt-1 text-2xl font-semibold text-slate-950">
                {percentageLabel(match.preferred_skill_match_percentage)}
              </p>
            </div>
          </div>
          <p className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700">
            {match.recommendation || "No recommendation available yet."}
          </p>
        </div>
      </div>
    </section>
  );
}
