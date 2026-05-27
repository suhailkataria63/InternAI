type SkillBadgeProps = {
  label: string;
  tone?: "positive" | "missing" | "neutral" | "priority";
};

const toneClasses = {
  positive: "border-emerald-200 bg-emerald-50 text-emerald-800",
  missing: "border-rose-200 bg-rose-50 text-rose-800",
  neutral: "border-slate-200 bg-slate-50 text-slate-700",
  priority: "border-amber-200 bg-amber-50 text-amber-900",
};

export default function SkillBadge({ label, tone = "neutral" }: SkillBadgeProps) {
  return (
    <span
      className={`inline-flex min-h-7 items-center rounded-full border px-3 py-1 text-xs font-semibold ${toneClasses[tone]}`}
    >
      {label}
    </span>
  );
}
