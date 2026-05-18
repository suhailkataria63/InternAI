import type { PrioritySkill, RecommendedProject, RoadmapWeek, SkillGapResult } from "../lib/types";
import SkillBadge from "./SkillBadge";

type SkillGapCardProps = {
  skillGap: SkillGapResult;
};

function priorityTone(priority?: string): "priority" | "missing" | "neutral" {
  if (priority === "High") return "missing";
  if (priority === "Medium") return "priority";
  return "neutral";
}

function PrioritySkillCard({ item }: { item: PrioritySkill }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-sm font-semibold text-slate-950">{item.skill}</h4>
        <SkillBadge label={item.priority || "Priority"} tone={priorityTone(item.priority)} />
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        {item.reason || "No reason provided."}
      </p>
      <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Estimated learning time
      </p>
      <p className="mt-1 text-sm font-medium text-slate-900">
        {item.estimated_learning_time || "Not available"}
      </p>
      {(item.learning_tasks || []).length ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
          {item.learning_tasks?.map((task) => <li key={task}>{task}</li>)}
        </ul>
      ) : null}
    </div>
  );
}

function RoadmapItem({ week }: { week: RoadmapWeek }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-slate-950 px-3 py-1 text-xs font-semibold text-white">
          Week {week.week}
        </span>
        <h4 className="text-sm font-semibold text-slate-950">
          {week.focus || "Learning focus"}
        </h4>
      </div>
      {(week.skills || []).length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {week.skills?.map((skill) => <SkillBadge key={skill} label={skill} />)}
        </div>
      ) : null}
      {(week.tasks || []).length ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
          {week.tasks?.map((task) => <li key={task}>{task}</li>)}
        </ul>
      ) : null}
      {week.outcome ? (
        <p className="mt-3 rounded-lg bg-white p-3 text-sm font-medium text-slate-800">
          Outcome: {week.outcome}
        </p>
      ) : null}
    </div>
  );
}

function ProjectCard({ project }: { project: RecommendedProject }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h4 className="text-sm font-semibold text-slate-950">
        {project.title || "Recommended mini-project"}
      </h4>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        {project.description || "No description available."}
      </p>
      {(project.skills_practiced || []).length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {project.skills_practiced?.map((skill) => (
            <SkillBadge key={skill} label={skill} tone="priority" />
          ))}
        </div>
      ) : null}
      {project.expected_outcome ? (
        <p className="mt-3 text-sm font-medium text-slate-800">
          Outcome: {project.expected_outcome}
        </p>
      ) : null}
    </div>
  );
}

export default function SkillGapCard({ skillGap }: SkillGapCardProps) {
  const prioritySkills = skillGap.priority_skills || [];
  const roadmap = skillGap.learning_roadmap || [];
  const projects = skillGap.recommended_projects || [];

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Skill Gap Roadmap
          </p>
          <h3 className="mt-1 text-lg font-semibold text-slate-950">
            {skillGap.target_role || "Learning plan"}
          </h3>
        </div>
      </div>

      {skillGap.overall_advice ? (
        <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm leading-6 text-amber-950">
          {skillGap.overall_advice}
        </p>
      ) : null}

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div>
          <h4 className="text-sm font-semibold text-slate-950">Priority skills</h4>
          <div className="mt-3 space-y-3">
            {prioritySkills.length ? (
              prioritySkills.map((item) => (
                <PrioritySkillCard key={`${item.skill}-${item.priority}`} item={item} />
              ))
            ) : (
              <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
                No priority skills returned.
              </p>
            )}
          </div>
        </div>
        <div>
          <h4 className="text-sm font-semibold text-slate-950">Recommended projects</h4>
          <div className="mt-3 space-y-3">
            {projects.length ? (
              projects.map((project) => (
                <ProjectCard key={`${project.title}-${project.expected_outcome}`} project={project} />
              ))
            ) : (
              <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
                No mini-projects returned.
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="mt-6">
        <h4 className="text-sm font-semibold text-slate-950">Week-wise roadmap</h4>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {roadmap.length ? (
            roadmap.map((week) => (
              <RoadmapItem key={`${week.week}-${week.focus}`} week={week} />
            ))
          ) : (
            <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
              No roadmap returned.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
