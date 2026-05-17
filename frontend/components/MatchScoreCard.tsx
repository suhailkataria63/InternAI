import type { MatchResult, PipelineSummary } from "../lib/types";

type MatchScoreCardProps = {
  match: MatchResult;
  summary: PipelineSummary;
};

function SkillList({ title, skills }: { title: string; skills?: string[] }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {title}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {(skills || []).length ? (
          skills?.map((skill) => (
            <span
              key={skill}
              className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
            >
              {skill}
            </span>
          ))
        ) : (
          <span className="text-sm text-slate-500">None found</span>
        )}
      </div>
    </div>
  );
}

export default function MatchScoreCard({ match, summary }: MatchScoreCardProps) {
  const score = match.match_score ?? summary.match_score ?? 0;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-slate-950">Match Score</h3>
          <p className="mt-1 text-sm text-slate-600">
            {match.match_level || summary.match_level || "Not scored"}
          </p>
        </div>
        <div className="flex h-24 w-24 items-center justify-center rounded-full bg-slate-950 text-3xl font-bold text-white">
          {score}
        </div>
      </div>
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <SkillList title="Matched skills" skills={match.matched_skills} />
        <SkillList title="Missing skills" skills={match.missing_skills} />
      </div>
      {match.recommendation ? (
        <p className="mt-4 rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-700">
          {match.recommendation}
        </p>
      ) : null}
    </section>
  );
}
