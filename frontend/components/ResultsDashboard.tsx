import type { AnalysisResponse } from "../lib/types";
import ApplicationAnswerCard from "./ApplicationAnswerCard";
import CoverLetterCard from "./CoverLetterCard";
import MatchScoreCard from "./MatchScoreCard";
import PipelineSummaryCard from "./PipelineSummaryCard";
import SkillGapCard from "./SkillGapCard";

type ResultsDashboardProps = {
  result: AnalysisResponse | null;
};

export default function ResultsDashboard({ result }: ResultsDashboardProps) {
  if (!result) {
    return (
      <section className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center shadow-soft">
        <h2 className="text-lg font-semibold text-slate-950">Results Dashboard</h2>
        <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          Run an analysis to see the pipeline summary, match score, skill gaps,
          application answer, and cover letter in separate sections.
        </p>
      </section>
    );
  }

  return (
    <div className="space-y-5">
      <PipelineSummaryCard summary={result.pipeline_summary} />
      <MatchScoreCard
        match={result.match_result}
        summary={result.pipeline_summary}
      />
      <SkillGapCard skillGap={result.skill_gap_result} />
      <ApplicationAnswerCard answer={result.application_answer} />
      <CoverLetterCard coverLetter={result.cover_letter} />
    </div>
  );
}
