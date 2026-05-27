export type Tone = "professional" | "confident" | "friendly" | "concise";
export type CoverLetterLength = "short" | "medium" | "long";

export type AnalysisRequest = {
  resume_text: string;
  job_description: string;
  application_question: string;
  tone: Tone;
  word_limit: number;
  cover_letter_length: CoverLetterLength;
};

export interface ResumeUploadResponse {
  filename: string;
  text_length: number;
  extracted_text: string;
  content_type?: string;
  message?: string;
}

export type PipelineSummary = {
  candidate_name?: string;
  target_role?: string;
  company_name?: string;
  match_score?: number;
  match_level?: string;
  top_matched_skills?: string[];
  top_missing_skills?: string[];
  highest_priority_skills?: string[];
  recommended_next_step?: string;
};

export type ResumeProfile = {
  name?: string;
  email?: string;
  phone?: string;
  education?: string[];
  skills?: string[];
  projects?: any[];
  [key: string]: unknown;
};

export type JobProfile = {
  role_title?: string;
  company_name?: string;
  required_skills?: string[];
  preferred_skills?: string[];
  work_mode?: string;
  stipend?: string;
  duration?: string;
  location?: string;
  [key: string]: unknown;
};

export type MatchResult = {
  match_score?: number;
  match_level?: string;
  matched_skills?: string[];
  missing_skills?: string[];
  project_relevance_notes?: string[];
  recommendation?: string;
  score_breakdown?: {
    required_skills?: number;
    preferred_skills?: number;
    project_relevance?: number;
    education_relevance?: number;
    experience_certifications?: number;
    education_note?: string;
    experience_note?: string;
    [key: string]: unknown;
  };
  required_skill_match_percentage?: number;
  preferred_skill_match_percentage?: number;
  matched_required_skills?: string[];
  missing_required_skills?: string[];
  matched_preferred_skills?: string[];
  missing_preferred_skills?: string[];
};

export type PrioritySkill = {
  skill: string;
  priority: "High" | "Medium" | "Low" | string;
  reason?: string;
  estimated_learning_time?: string;
  learning_tasks?: string[];
};

export type RoadmapWeek = {
  week: number;
  focus: string;
  skills?: string[];
  tasks?: string[];
  outcome?: string;
};

export type RecommendedProject = {
  title: string;
  description: string;
  skills_practiced?: string[];
  expected_outcome?: string;
};

export type SkillGapResult = {
  target_role?: string;
  priority_skills?: PrioritySkill[];
  learning_roadmap?: RoadmapWeek[];
  resume_improvement_suggestions?: string[];
  recommended_projects?: RecommendedProject[];
  overall_advice?: string;
};

export type ApplicationAnswer = {
  question?: string;
  generated_answer?: string;
  key_points_used?: string[];
  tone?: string;
  word_count?: number;
  improvement_note?: string;
};

export type CoverLetterResult = {
  cover_letter?: string;
  subject_line?: string;
  opening_summary?: string;
  key_points_used?: string[];
  tone?: string;
  word_count?: number;
};

export type AnalysisResponse = {
  resume_profile?: ResumeProfile;
  job_profile?: JobProfile;
  match_result?: MatchResult;
  skill_gap_result?: SkillGapResult;
  application_answer?: ApplicationAnswer;
  cover_letter?: CoverLetterResult;
  pipeline_summary?: PipelineSummary;
};

export type ApplicationStatus =
  | "Saved"
  | "Applied"
  | "Interview"
  | "Rejected"
  | "Selected";

export type ApplicationListItem = {
  id: number;
  candidate_name?: string | null;
  company_name?: string | null;
  role_title?: string | null;
  match_score?: number | null;
  match_level?: string | null;
  status: ApplicationStatus;
  notes?: string | null;
  created_at: string;
  updated_at: string;
};

export type ApplicationDetail = ApplicationListItem & {
  resume_text?: string | null;
  job_description?: string | null;
  resume_profile: Record<string, unknown>;
  job_profile: Record<string, unknown>;
  match_result: MatchResult;
  skill_gap_result: SkillGapResult;
  application_answer: ApplicationAnswer;
  cover_letter: CoverLetterResult;
  pipeline_summary: PipelineSummary;
};
