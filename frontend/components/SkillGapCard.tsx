import type { SkillGapResult } from "../lib/types";

type SkillGapCardProps = {
  skillGap: SkillGapResult;
};

export default function SkillGapCard({ skillGap }: SkillGapCardProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
      <h3 className="text-base font-semibold text-slate-950">Skill Gap Plan</h3>
      <div className="mt-4 flex flex-wrap gap-2">
        {(skillGap.priority_skills || []).map((item) => (
          <span
            key={`${item.skill}-${item.priority}`}
            className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-900"
          >
            {item.skill} · {item.priority}
          </span>
        ))}
      </div>
      <div className="mt-5 space-y-3">
        {(skillGap.learning_roadmap || []).map((week) => (
          <div key={`${week.week}-${week.focus}`} className="rounded-xl bg-slate-50 p-4">
            <p className="text-sm font-semibold text-slate-900">
              Week {week.week}: {week.focus}
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
              {(week.tasks || []).map((task) => (
                <li key={task}>{task}</li>
              ))}
            </ul>
            {week.outcome ? (
              <p className="mt-2 text-sm font-medium text-slate-800">
                Outcome: {week.outcome}
              </p>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}
