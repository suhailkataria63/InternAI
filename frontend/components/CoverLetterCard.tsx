import type { CoverLetterResult } from "../lib/types";

type CoverLetterCardProps = {
  coverLetter: CoverLetterResult;
};

export default function CoverLetterCard({ coverLetter }: CoverLetterCardProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="text-base font-semibold text-slate-950">Cover Letter</h3>
        <span className="text-sm text-slate-500">
          {coverLetter.word_count || 0} words
        </span>
      </div>
      <p className="mt-3 rounded-xl bg-indigo-50 p-3 text-sm font-semibold text-indigo-950">
        {coverLetter.subject_line || "Subject line will appear here"}
      </p>
      <p className="mt-4 whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-800">
        {coverLetter.cover_letter || "No cover letter generated yet."}
      </p>
      <div className="mt-4">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Key points used
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
          {(coverLetter.key_points_used || []).map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
