"use client";

import { ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import ApplicationTracker from "../components/ApplicationTracker";
import WelcomeIntro from "../components/WelcomeIntro";
import WorkspaceNavigation, { type NavigationKey } from "@/components/WorkspaceNavigation";
import WritingEditor from "@/components/WritingEditor";
import type { CallChipStatus } from "@/components/CallChip";
import { SkeletonReveal } from "@/components/spectrumui/skeleton-reveal";
import { AnimatedCard } from "@/components/spectrumui/animated-card";
import ThoughtLine from "@/components/react-bits/ThoughtLine";
import { MorphButton } from "@/components/spectrumui/morph-button";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { StatusBadge } from "@/components/spectrumui/status-badge";
import { MessageSquareText } from "lucide-react";
import { HugeiconsIcon } from "@hugeicons/react";
import { File02Icon, PencilEdit01Icon } from "@hugeicons/core-free-icons";
import {
  Stepper,
  StepperDescription,
  StepperIndicator,
  StepperItem,
  StepperList,
  StepperSeparator,
  StepperTitle,
  StepperTrigger,
} from "@/components/control-ui/ui/stepper";
import { Skeleton } from "@/components/control-ui/ui/skeleton";
import { toast } from "@/components/control-ui/ui/toast";
import {
  analyzeApplication,
  analyzeJobDescription,
  analyzeResumeText,
  scoreResumeMatch,
  saveApplicationAnalysis,
  uploadResumePdf,
  writeApplicationAnswer,
  writeCoverLetter,
} from "../lib/api";
import type {
  ApplicationAnswer,
  AnalysisRequest,
  AnalysisResponse,
  CoverLetterResult,
  CoverLetterLength,
  Tone,
} from "../lib/types";

const toneOptions: Array<{ value: Tone; label: string }> = [
  { value: "professional", label: "Professional" },
  { value: "friendly", label: "Natural" },
  { value: "confident", label: "Confident" },
];
const lengthOptions: Array<{ value: CoverLetterLength; label: string }> = [
  { value: "short", label: "Short" },
  { value: "medium", label: "Standard" },
  { value: "long", label: "Detailed" },
];
const answerLengthOptions = [
  { value: 100, label: "Short" },
  { value: 180, label: "Standard" },
  { value: 300, label: "Detailed" },
];
type WorkflowView = "welcome" | "analyze" | "cover" | "answer" | "cover-result" | "answer-result" | "loading" | "results" | "studio" | "tracker";
type WritingScene = "upload" | "customize";
type StudioTab = "answer" | "cover" | "roadmap";
// The request starts immediately; this only keeps successful transitions
// perceptible when a mocked or cached response returns almost instantly.
const MIN_VISIBLE_OPERATION_MS = 4000;

function WritingProgress({ step }: { step: 0 | 1 | 2 }) {
  return (
    <Stepper value={step} onValueChange={() => undefined} orientation="horizontal" contentMode="current" className="writing-control-stepper">
      <StepperList aria-label="InternAI writing workflow">
        <StepperItem step={0}><StepperTrigger><StepperIndicator /><span><StepperTitle>Resume and role</StepperTitle><StepperDescription>Prepare the source context.</StepperDescription></span></StepperTrigger><StepperSeparator /></StepperItem>
        <StepperItem step={1}><StepperTrigger><StepperIndicator /><span><StepperTitle>Customize</StepperTitle><StepperDescription>Choose your question and preferences.</StepperDescription></span></StepperTrigger><StepperSeparator /></StepperItem>
        <StepperItem step={2}><StepperTrigger><StepperIndicator /><span><StepperTitle>Your draft</StepperTitle><StepperDescription>Review, edit and copy your writing.</StepperDescription></span></StepperTrigger></StepperItem>
      </StepperList>
    </Stepper>
  );
}

const sampleResume = `Jordan Lee — illustrative sample profile
B.S. Computer Science, Example State University (expected 2027)
Skills: TypeScript, React, Python, SQL
Project: Campus Events Board — built a React interface for browsing campus events with a small Python API and SQL-backed event data.
Coursework: Data Structures, Web Development, Database Systems`;

const sampleJobDescription = `Northstar Studio — illustrative opportunity
Role: Frontend Engineering Intern
Requirements: React, TypeScript, accessible UI, and clear communication.
Responsibilities: Help build and refine responsive product interfaces alongside a small engineering team.
Duration: 12 weeks.`;

function getStringArray(source: unknown, key?: string): string[] {
  const value =
    key && source && typeof source === "object"
      ? (source as Record<string, unknown>)[key]
      : source;

  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => (typeof item === "string" ? item : ""))
    .filter(Boolean);
}

function getStringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function getProjectDisplay(project: unknown, index: number): { title: string; description: string } | null {
  if (typeof project === "string") {
    const description = project.trim();
    return description ? { title: `Project ${index + 1}`, description } : null;
  }
  if (!project || typeof project !== "object" || Array.isArray(project)) return null;
  const fields = project as Record<string, unknown>;
  const rawTitle = getStringValue(fields.name) || getStringValue(fields.title);
  const rawDescription = getStringValue(fields.description);
  const normalize = (value: string) => value.toLowerCase().replace(/\s+/g, " ").replace(/[.!,:;]+$/g, "").trim();
  const duplicate = Boolean(rawTitle && rawDescription && normalize(rawTitle) === normalize(rawDescription));
  const titleLooksLikeDescription = rawTitle.length > 72 || /[.!?].{24,}/.test(rawTitle);
  const safeTitle = rawTitle && !titleLooksLikeDescription ? rawTitle : `Project ${index + 1}`;
  const description = duplicate
    ? (titleLooksLikeDescription ? rawTitle : "")
    : titleLooksLikeDescription
      ? [rawTitle, rawDescription].filter(Boolean).join("\n")
      : rawDescription || rawTitle;
  return description || safeTitle ? { title: safeTitle, description } : null;
}

function getPreparedRoleTitle(value: unknown): string {
  const title = getStringValue(value);
  return title && title.length <= 80 && !/[.!?].{24,}/.test(title) ? title : "Target opportunity";
}

function getArrayLength(source: unknown, key: string): number {
  if (!source || typeof source !== "object") {
    return 0;
  }
  const value = (source as Record<string, unknown>)[key];
  return Array.isArray(value) ? value.length : 0;
}

function readablePrioritySkills(result: AnalysisResponse | null): string[] {
  const summarySkills = result?.pipeline_summary?.highest_priority_skills || [];
  const gapSkills =
    result?.skill_gap_result?.priority_skills
      ?.map((item) => item.skill)
      .filter(Boolean) || [];

  return (summarySkills.length ? summarySkills : gapSkills).slice(0, 8);
}

function directInputKey(resume: string, jobDescription: string): string {
  return `${resume}\u0000${jobDescription}`;
}

function getDraftSource(writer: { used_fallback?: boolean; generation_source?: string; llm_provider?: string } | undefined): "ai" | "fallback" | "unknown" {
  if (writer?.used_fallback) return "fallback";
  const source = writer?.generation_source?.toLowerCase();
  if (writer?.llm_provider || source === "llm" || source === "groq" || source === "ai") return "ai";
  return "unknown";
}

async function runDirectWriting(
  prepared: AnalysisResponse,
  payload: AnalysisRequest,
  target: "cover" | "answer",
  signal: AbortSignal,
): Promise<AnalysisResponse> {
  const resumeProfile = prepared.resume_profile ?? {};
  const jobProfile = prepared.job_profile ?? {};
  const matchResult = prepared.match_result ?? {};
  // The skill-gap endpoint may call an LLM. Direct writing deliberately omits
  // that optional context so only the selected writer can call a model.
  const skillGapResult = prepared.skill_gap_result ?? {};
  if (target === "cover") {
    const coverLetter = await writeCoverLetter({
      resume_profile: resumeProfile,
      job_profile: jobProfile,
      match_result: matchResult,
      skill_gap_result: skillGapResult,
      tone: payload.tone,
      length: payload.cover_letter_length,
    }, signal);
    return { resume_profile: resumeProfile, job_profile: jobProfile, match_result: matchResult, skill_gap_result: skillGapResult, cover_letter: coverLetter };
  }
  const applicationAnswer = await writeApplicationAnswer({
    resume_profile: resumeProfile,
    job_profile: jobProfile,
    match_result: matchResult,
    skill_gap_result: skillGapResult,
    application_question: payload.application_question,
    tone: payload.tone,
    word_limit: payload.word_limit,
  }, signal);
  return { resume_profile: resumeProfile, job_profile: jobProfile, match_result: matchResult, skill_gap_result: skillGapResult, application_answer: applicationAnswer };
}

export default function Home() {
  const [resumeText, setResumeText] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [applicationQuestion, setApplicationQuestion] = useState(
    "Why should we hire you for this internship?",
  );
  const [tone, setTone] = useState<Tone>("professional");
  const [wordLimit, setWordLimit] = useState(180);
  const [coverLetterLength, setCoverLetterLength] =
    useState<CoverLetterLength>("short");

  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [writingResults, setWritingResults] = useState<{ cover?: CoverLetterResult; answer?: ApplicationAnswer }>({});
  const [studioTarget, setStudioTarget] = useState<"cover" | "answer" | null>(null);
  const [preparedWriting, setPreparedWriting] = useState<AnalysisResponse | null>(null);
  const [preparedWritingKey, setPreparedWritingKey] = useState("");
  const [writingScene, setWritingScene] = useState<WritingScene>("upload");
  const [isPreparingWriting, setIsPreparingWriting] = useState(false);
  const [writerCallStatus, setWriterCallStatus] = useState<CallChipStatus>("idle");
  const [studioTab, setStudioTab] = useState<StudioTab>("answer");
  const [resultFromFullAnalysis, setResultFromFullAnalysis] = useState(false);
  const [trackerRefreshKey, setTrackerRefreshKey] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [operationComplete, setOperationComplete] = useState(false);
  const [completedOperationSteps, setCompletedOperationSteps] = useState(1);
  const [operationOutcome, setOperationOutcome] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [saveError, setSaveError] = useState("");
  const [hasSavedCurrentResult, setHasSavedCurrentResult] = useState(false);
  const [savedApplicationId, setSavedApplicationId] = useState<number | null>(null);
  const [copiedTarget, setCopiedTarget] = useState<"answer" | "cover" | "">("");
  const [editableAnswer, setEditableAnswer] = useState("");
  const [editableCover, setEditableCover] = useState("");
  const [activeView, setActiveView] = useState<WorkflowView>("welcome");
  const [isBreakdownOpen, setIsBreakdownOpen] = useState(false);
  const uploadRequestId = useRef(0);
  const analyzeRequestId = useRef(0);
  const uploadAbortRef = useRef<AbortController | null>(null);
  const analyzeAbortRef = useRef<AbortController | null>(null);
  const operationStartedAtRef = useRef(0);
  const operationWaitRef = useRef<{ timer: number; resolve: (completed: boolean) => void } | null>(null);
  const outputIntent = useRef<"results" | "cover" | "answer">("results");
  const reduceMotion = useReducedMotion();

  const beginVisibleOperation = () => {
    if (operationWaitRef.current) {
      window.clearTimeout(operationWaitRef.current.timer);
      operationWaitRef.current.resolve(false);
      operationWaitRef.current = null;
    }
    operationStartedAtRef.current = performance.now();
    setOperationComplete(false);
    setCompletedOperationSteps(1);
    setOperationOutcome("");
  };

  const cancelVisibleOperation = () => {
    if (operationWaitRef.current) {
      window.clearTimeout(operationWaitRef.current.timer);
      operationWaitRef.current.resolve(false);
      operationWaitRef.current = null;
    }
    setOperationComplete(false);
  };

  const completeVisibleOperation = async (requestId: number, outcome: string) => {
    if (requestId !== analyzeRequestId.current) return false;
    setOperationOutcome(outcome);
    setOperationComplete(true);
    setCompletedOperationSteps(3);
    const remainingMs = Math.max(0, MIN_VISIBLE_OPERATION_MS - (performance.now() - operationStartedAtRef.current));
    if (remainingMs > 0) {
      const minimumDurationComplete = await new Promise<boolean>((resolve) => {
        const timer = window.setTimeout(() => {
          operationWaitRef.current = null;
          resolve(true);
        }, remainingMs);
        operationWaitRef.current = { timer, resolve };
      });
      if (!minimumDurationComplete || requestId !== analyzeRequestId.current) return false;
    }
    return true;
  };
  const inputsPrepared = Boolean(preparedWriting && preparedWritingKey === directInputKey(resumeText, jobDescription));
  const currentWriterTarget = studioTarget ?? (activeView === "cover" || activeView === "cover-result" ? "cover" : "answer");
  const activeWritingResult = currentWriterTarget === "cover"
    ? writingResults.cover ?? result?.cover_letter
    : writingResults.answer ?? result?.application_answer;
  const hasActiveWritingResult = Boolean(
    currentWriterTarget === "cover"
      ? activeWritingResult && "cover_letter" in activeWritingResult && activeWritingResult.cover_letter
      : activeWritingResult && "generated_answer" in activeWritingResult && activeWritingResult.generated_answer,
  );

  const navigateTo = useCallback((destination: NavigationKey, updateHistory = true) => {
    const view: Record<NavigationKey, WorkflowView> = {
      home: "welcome",
      analyze: "analyze",
      studio: "studio",
      tracker: "tracker",
    };
    const requestStillMatchesDestination = destination === "analyze" && outputIntent.current === "results";
    if (isAnalyzing && !requestStillMatchesDestination) {
      analyzeRequestId.current += 1;
      analyzeAbortRef.current?.abort();
      analyzeAbortRef.current = null;
      cancelVisibleOperation();
      setIsAnalyzing(false);
      setIsPreparingWriting(false);
      if (outputIntent.current === "cover" || outputIntent.current === "answer") {
        setWritingScene(inputsPrepared ? "customize" : "upload");
        setWriterCallStatus("idle");
      }
    }
    if (destination === "analyze") outputIntent.current = "results";
    if (destination === "studio") setStudioTarget(null);
    if (updateHistory && window.location.hash !== `#${destination}`) window.history.pushState(null, "", `#${destination}`);
    setAnalysisError("");
    setActiveView(view[destination]);
  }, [isAnalyzing, inputsPrepared]);

  const openWritingWorkflow = (target: "cover" | "answer", updateHistory = true) => {
    outputIntent.current = target;
    setStudioTarget(target);
    setWritingScene(inputsPrepared ? "customize" : "upload");
    setWriterCallStatus("idle");
    setAnalysisError("");
    setActiveView(target);
    if (updateHistory) {
      const inputHash = `#studio/${target}/inputs`;
      if (window.location.hash !== inputHash) window.history.pushState(null, "", inputHash);
      if (inputsPrepared) window.history.pushState(null, "", `#studio/${target}/customize`);
    }
  };

  const backToStudio = () => {
    setActiveView("studio");
    setStudioTarget(null);
    setAnalysisError("");
    if (window.location.hash.endsWith("/inputs") && window.history.length > 1) {
      window.history.back();
      return;
    }
    window.history.replaceState(null, "", "#studio");
  };

  const backToWriterInputs = () => {
    const target = studioTarget ?? (activeView === "cover" || activeView === "cover-result" ? "cover" : "answer");
    if (isAnalyzing) return;
    setStudioTarget(target);
    setWritingScene("upload");
    setAnalysisError("");
    setActiveView(target);
    if (window.location.hash === `#studio/${target}/customize` && window.history.length > 1) {
      window.history.back();
      return;
    }
    window.history.replaceState(null, "", `#studio/${target}/inputs`);
  };

  const navKey: NavigationKey = activeView === "welcome"
    ? "home"
    : activeView === "analyze" || activeView === "results" || (activeView === "loading" && outputIntent.current === "results")
      ? "analyze"
      : activeView === "tracker" ? "tracker" : "studio";

  useEffect(() => {
    return () => {
      uploadAbortRef.current?.abort();
      analyzeAbortRef.current?.abort();
      cancelVisibleOperation();
    };
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      const parts = window.location.hash.slice(1).split("/");
      const route = parts[0] === "" || parts[0] === "top" ? "home" : parts[0];
      const requestStillMatchesRoute = (route === "analyze" && outputIntent.current === "results")
        || (route === "studio" && parts[1] === outputIntent.current);
      if (isAnalyzing && !requestStillMatchesRoute) {
        analyzeRequestId.current += 1;
        analyzeAbortRef.current?.abort();
        analyzeAbortRef.current = null;
        setIsAnalyzing(false);
        setIsPreparingWriting(false);
        if (outputIntent.current === "cover" || outputIntent.current === "answer") {
          setWritingScene(inputsPrepared ? "customize" : "upload");
          setWriterCallStatus("idle");
        }
      }
      if (route === "studio" && (parts[1] === "cover" || parts[1] === "answer")) {
        const target = parts[1];
        outputIntent.current = target;
        setStudioTarget(target);
        if (parts[2] === "draft") setActiveView(target === "cover" ? "cover-result" : "answer-result");
        else {
          setWritingScene(parts[2] === "customize" ? "customize" : "upload");
          setActiveView(target);
        }
        setAnalysisError("");
        return;
      }
      if (route === "results" && resultFromFullAnalysis) { setActiveView("results"); return; }
      if (route === "analyze") outputIntent.current = "results";
      setAnalysisError("");
      setStudioTarget(null);
      const view: Record<string, WorkflowView> = { home: "welcome", analyze: "analyze", studio: "studio", tracker: "tracker" };
      if (view[route]) setActiveView(view[route]);
    };
    window.addEventListener("hashchange", onHashChange);
    window.addEventListener("popstate", onHashChange);
    return () => {
      window.removeEventListener("hashchange", onHashChange);
      window.removeEventListener("popstate", onHashChange);
    };
  }, [isAnalyzing, inputsPrepared, preparedWriting, resultFromFullAnalysis]);

  useEffect(() => {
    const parts = window.location.hash.slice(1).split("/");
    if (parts[0] === "studio" && (parts[1] === "cover" || parts[1] === "answer")) {
      const target = parts[1];
      setStudioTarget(target);
      setWritingScene(parts[2] === "customize" ? "customize" : "upload");
      setActiveView(parts[2] === "draft" ? target === "cover" ? "cover-result" : "answer-result" : target);
    } else {
      const initialView: Record<string, WorkflowView> = { analyze: "analyze", studio: "studio", tracker: "tracker", results: "results" };
      if (initialView[parts[0]]) setActiveView(initialView[parts[0]]);
    }
  }, []);

  const matchedRequired =
    result?.match_result?.matched_required_skills?.length
      ? result.match_result.matched_required_skills
      : result?.match_result?.matched_skills || [];
  const missingRequired = result?.match_result?.missing_required_skills || [];
  const requiredSkills = getStringArray(result?.job_profile, "required_skills");
  const skillCoverageTotal =
    requiredSkills.length || matchedRequired.length + missingRequired.length;
  const roadmap = result?.skill_gap_result?.learning_roadmap || [];
  const matchedSkills = matchedRequired.length
    ? matchedRequired
    : result?.match_result?.matched_skills || [];
  const missingSkills = missingRequired.length
    ? missingRequired
    : result?.match_result?.missing_skills || [];
  const coverLetter = result?.cover_letter?.cover_letter || "";
  const applicationAnswer = result?.application_answer?.generated_answer || "";
  const prioritySkills = readablePrioritySkills(result);
  const candidateName =
    getStringValue(result?.pipeline_summary?.candidate_name) ||
    getStringValue(result?.resume_profile?.name) ||
    "Candidate name not detected";
  const rawTargetRole =
    getStringValue(result?.pipeline_summary?.target_role) ||
    getStringValue(result?.job_profile?.role_title);
  const targetRole = rawTargetRole || "Target role not detected";
  const rawCompanyName =
    getStringValue(result?.pipeline_summary?.company_name) ||
    getStringValue(result?.job_profile?.company_name);
  const companyName = rawCompanyName || "Company not detected";
  const roleCompanyLine = rawTargetRole
    ? rawCompanyName
      ? `${rawTargetRole} at ${rawCompanyName}`
      : rawTargetRole
    : "Target role not detected";
  const matchScore =
    result?.pipeline_summary?.match_score ??
    result?.match_result?.match_score;
  const matchLevel =
    result?.pipeline_summary?.match_level ||
    result?.match_result?.match_level ||
    "Not available";

  const scoreBreakdownEntries = result?.match_result?.score_breakdown
    ? [
        ["Required skills", result.match_result.score_breakdown.required_skills],
        ["Preferred skills", result.match_result.score_breakdown.preferred_skills],
        ["Projects", result.match_result.score_breakdown.project_relevance],
        ["Education", result.match_result.score_breakdown.education_relevance],
        ["Experience", result.match_result.score_breakdown.experience_certifications],
      ]
    : [];

  const handleResumeFile = async (file?: File) => {
    if (!file) {
      return;
    }

    const isPdf =
      file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

    setUploadMessage("");
    setUploadError("");

    if (!isPdf) {
      setUploadError("Please upload a PDF resume file.");
      toast.error("Upload failed", { description: "Please choose a PDF resume." });
      return;
    }

    uploadAbortRef.current?.abort();
    const requestId = uploadRequestId.current + 1;
    uploadRequestId.current = requestId;
    const controller = new AbortController();
    uploadAbortRef.current = controller;

    setIsUploading(true);
    try {
      const uploaded = await uploadResumePdf(file, controller.signal);
      if (requestId !== uploadRequestId.current) {
        return;
      }
      if (!uploaded.extracted_text?.trim()) {
        setUploadError("PDF uploaded, but no text could be extracted.");
        toast.error("No resume text found", { description: "Try another PDF or paste the resume text." });
        return;
      }

      handleResumeTextChange(uploaded.extracted_text);
      setUploadMessage(
        `Uploaded ${uploaded.filename} successfully. Extracted ${uploaded.text_length} characters.`,
      );
      toast.success("Resume uploaded", { description: "Your file is ready for analysis." });
    } catch (caughtError) {
      if (requestId !== uploadRequestId.current) {
        return;
      }
      setUploadError(
        caughtError instanceof Error
          ? caughtError.message
          : "Failed to extract resume text. Please paste resume text manually.",
      );
      toast.error("Upload failed", { description: caughtError instanceof Error ? caughtError.message : "Check the file and try again." });
    } finally {
      if (requestId === uploadRequestId.current) {
        setIsUploading(false);
        uploadAbortRef.current = null;
      }
    }
  };

  const handleResumeUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    void handleResumeFile(file);
  };

  const invalidatePreparedWriting = () => {
    setPreparedWriting(null);
    setPreparedWritingKey("");
    setWritingScene("upload");
    setWriterCallStatus("idle");
    setResult(null);
    setResultFromFullAnalysis(false);
    setHasSavedCurrentResult(false);
    setAnalysisError("");
  };

  const handleResumeTextChange = (value: string) => {
    if (value !== resumeText) invalidatePreparedWriting();
    setResumeText(value);
  };

  const handleJobDescriptionChange = (value: string) => {
    if (value !== jobDescription) invalidatePreparedWriting();
    setJobDescription(value);
  };

  const handleAnalyze = async () => {
    if (isAnalyzing) {
      return;
    }

    setAnalysisError("");
    setSaveMessage("");
    setSaveError("");

    if (!resumeText.trim()) {
      setAnalysisError("Add resume text or upload a resume PDF before analyzing.");
      return;
    }

    if (!jobDescription.trim()) {
      setAnalysisError("Paste an internship or job description before analyzing.");
      return;
    }

    outputIntent.current = "results";

    const payload: AnalysisRequest = {
      resume_text: resumeText,
      job_description: jobDescription,
      application_question: "",
      tone: "professional",
      word_limit: 180,
      cover_letter_length: "short",
    };

    analyzeAbortRef.current?.abort();
    const requestId = analyzeRequestId.current + 1;
    analyzeRequestId.current = requestId;
    const controller = new AbortController();
    analyzeAbortRef.current = controller;

    beginVisibleOperation();
    setIsAnalyzing(true);
    try {
      const analysis = await analyzeApplication(payload, controller.signal);
      if (requestId !== analyzeRequestId.current) {
        return;
      }
      if (!(await completeVisibleOperation(requestId, "Skills analysis complete — opening results"))) return;
      setResult(analysis);
      setResultFromFullAnalysis(true);
      setPreparedWriting({
        resume_profile: analysis.resume_profile,
        job_profile: analysis.job_profile,
        match_result: analysis.match_result,
        skill_gap_result: analysis.skill_gap_result ?? { target_role: analysis.job_profile?.role_title, priority_skills: [], learning_roadmap: [] },
      });
      setPreparedWritingKey(directInputKey(resumeText, jobDescription));
      setWritingResults({});
      setEditableAnswer("");
      setEditableCover("");
      setWriterCallStatus("idle");
      setHasSavedCurrentResult(false);
      setSavedApplicationId(null);
      setActiveView("results");
      window.history.pushState({ internai: true }, "", "#results");
    } catch (caughtError) {
      if (requestId !== analyzeRequestId.current) {
        return;
      }
      setAnalysisError(
        caughtError instanceof Error
          ? caughtError.message
          : "Analysis failed. Make sure the FastAPI backend is running.",
      );
      setActiveView("analyze");
    } finally {
      if (requestId === analyzeRequestId.current) {
        setIsAnalyzing(false);
        analyzeAbortRef.current = null;
      }
    }
  };


  const handlePrepareWriting = async (target: "cover" | "answer") => {
    if (isAnalyzing) return;
    if (!resumeText.trim() || !jobDescription.trim()) {
      setAnalysisError(!resumeText.trim() ? "Add resume text or upload a resume PDF before analyzing." : "Paste the job description before analyzing.");
      return;
    }
    if (inputsPrepared) {
      outputIntent.current = target;
      setStudioTarget(target);
      setWritingScene("customize");
      setAnalysisError("");
      setActiveView(target);
      if (window.location.hash !== `#studio/${target}/customize`) {
        window.history.pushState({ internai: true }, "", `#studio/${target}/customize`);
      }
      return;
    }
    outputIntent.current = target;
    setAnalysisError("");
    const requestId = analyzeRequestId.current + 1;
    analyzeRequestId.current = requestId;
    const controller = new AbortController();
    analyzeAbortRef.current?.abort();
    analyzeAbortRef.current = controller;
    beginVisibleOperation();
    setIsAnalyzing(true);
    setIsPreparingWriting(true);
    setWriterCallStatus("idle");
    try {
      const [resumeProfile, jobProfile] = await Promise.all([
        analyzeResumeText(resumeText, controller.signal),
        analyzeJobDescription(jobDescription, controller.signal),
      ]);
      if (requestId !== analyzeRequestId.current) return;
      const matchResult = await scoreResumeMatch(resumeProfile, jobProfile, controller.signal);
      if (requestId !== analyzeRequestId.current) return;
      setPreparedWriting({
        resume_profile: resumeProfile,
        job_profile: jobProfile,
        match_result: matchResult,
        skill_gap_result: { target_role: jobProfile.role_title, priority_skills: [], learning_roadmap: [] },
      });
      setPreparedWritingKey(directInputKey(resumeText, jobDescription));
      setWritingScene("customize");
      setActiveView(target);
      if (!(await completeVisibleOperation(requestId, "Resume and job description ready"))) return;
      if (window.location.hash !== `#studio/${target}/customize`) {
        window.history.pushState({ internai: true }, "", `#studio/${target}/customize`);
      }
    } catch (caughtError) {
      if (requestId !== analyzeRequestId.current) return;
      setAnalysisError(caughtError instanceof Error ? caughtError.message : "Could not analyze these inputs.");
      setWritingScene("upload");
      setActiveView(target);
      toast.error("Input analysis failed", { description: "Review your resume and job description, then try again." });
    } finally {
      if (requestId === analyzeRequestId.current) {
        setIsAnalyzing(false);
        setIsPreparingWriting(false);
        analyzeAbortRef.current = null;
      }
    }
  };

  const handleGenerateWriting = async (target: "cover" | "answer") => {
    if (isAnalyzing) return;
    if (!inputsPrepared || writingScene !== "customize") {
      setAnalysisError("Analyze your resume and job description before generating.");
      return;
    }
    if (target === "answer" && !applicationQuestion.trim()) {
      setAnalysisError("Enter the exact application question before generating an answer.");
      return;
    }

    outputIntent.current = target;
    setAnalysisError("");
    const payload: AnalysisRequest = {
      resume_text: resumeText,
      job_description: jobDescription,
      application_question: applicationQuestion,
      tone,
      word_limit: Number(wordLimit) || 180,
      cover_letter_length: coverLetterLength,
    };
    const requestId = analyzeRequestId.current + 1;
    analyzeRequestId.current = requestId;
    const controller = new AbortController();
    analyzeAbortRef.current?.abort();
    analyzeAbortRef.current = controller;
    beginVisibleOperation();
    setIsAnalyzing(true);
    setWriterCallStatus("running");
    try {
      const writerContext = preparedWriting;
      if (requestId !== analyzeRequestId.current || !writerContext) return;
      const analysis = await runDirectWriting(writerContext, payload, target, controller.signal);
      if (requestId !== analyzeRequestId.current) return;
      const generatedText = target === "cover" ? analysis.cover_letter?.cover_letter : analysis.application_answer?.generated_answer;
      if (!generatedText?.trim()) throw new Error("The selected writer returned no draft text.");
      const usedFallback = target === "cover" ? analysis.cover_letter?.used_fallback : analysis.application_answer?.used_fallback;
      const outcome = usedFallback
        ? "Fallback draft ready — opening the editor"
        : "Draft ready — opening the editor";
      if (!(await completeVisibleOperation(requestId, outcome))) return;
      setWritingResults((current) => target === "cover"
        ? { ...current, cover: analysis.cover_letter }
        : { ...current, answer: analysis.application_answer });
      setWriterCallStatus("done");
      if (target === "cover") setEditableCover(analysis.cover_letter?.cover_letter || "");
      else setEditableAnswer(analysis.application_answer?.generated_answer || "");
      setActiveView(target === "cover" ? "cover-result" : "answer-result");
      if (window.location.hash === `#studio/${target}/inputs`) {
        window.history.pushState({ internai: true }, "", `#studio/${target}/customize`);
      }
      window.history.pushState({ internai: true }, "", `#studio/${target}/draft`);
    } catch (caughtError) {
      if (requestId !== analyzeRequestId.current) return;
      setAnalysisError(caughtError instanceof Error ? caughtError.message : "The selected writer could not complete the request.");
      toast.error("Draft generation failed", { description: "Your inputs are still here. Review the error and try again." });
      setWriterCallStatus("error");
      setActiveView(target);
      setWritingScene("customize");
    } finally {
      if (requestId === analyzeRequestId.current) {
        setIsAnalyzing(false);
        setIsPreparingWriting(false);
        analyzeAbortRef.current = null;
      }
    }
  };

  const generateFor = (target: "results" | "cover" | "answer") => {
    if (isAnalyzing) return;
    if (target === "results") void handleAnalyze();
    else void handleGenerateWriting(target);
  };



  const handleBackToCustomize = () => {
    const target = outputIntent.current === "answer" ? "answer" : "cover";
    setStudioTarget(target);
    setActiveView(target);
    setWritingScene("customize");
    setAnalysisError("");
    if (window.location.hash === `#studio/${target}/draft` && window.history.length > 1) {
      window.history.back();
      return;
    }
    if (!inputsPrepared) setWritingScene("upload");
    window.history.replaceState(null, "", `#studio/${target}/customize`);
  };


  const handleSaveApplication = async () => {
    if (!result || !resultFromFullAnalysis || hasSavedCurrentResult || isSaving) {
      return;
    }

    setIsSaving(true);
    setSaveMessage("");
    setSaveError("");
    try {
      const savedApplication = await saveApplicationAnalysis(result);
      setHasSavedCurrentResult(true);
      setSavedApplicationId(savedApplication.id ?? null);
      setSaveMessage("Application saved successfully.");
      setTrackerRefreshKey((current) => current + 1);
    } catch (caughtError) {
      setSaveError(
        caughtError instanceof Error
          ? caughtError.message
          : "Failed to save application.",
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleTrackerDelete = (deletedApplicationId: number) => {
    setTrackerRefreshKey((current) => current + 1);

    if (
      hasSavedCurrentResult &&
      (savedApplicationId === deletedApplicationId || savedApplicationId === null)
    ) {
      setHasSavedCurrentResult(false);
      setSavedApplicationId(null);
      setSaveMessage("");
      setSaveError("");
    }
  };

  const copyText = async (target: "answer" | "cover", text: string) => {
    if (!text) {
      return;
    }

    try {
      await navigator.clipboard.writeText(text);
      setCopiedTarget(target);
      toast.success("Copied", { description: "Draft copied to your clipboard." });
      window.setTimeout(() => setCopiedTarget(""), 1800);
    } catch {
      setCopiedTarget("");
    }
  };

  const useSampleData = () => {
    handleResumeTextChange(sampleResume);
    handleJobDescriptionChange(sampleJobDescription);
    setAnalysisError("");
    setUploadError("");
    setUploadMessage("Sample resume and job description loaded.");
    if (activeView === "cover" || activeView === "answer") {
      setWritingScene("upload");
    } else {
      navigateTo("analyze");
    }
  };

  const preparedProjectDisplays = (preparedWriting?.resume_profile?.projects || [])
    .slice(0, 3)
    .map((project: unknown, index: number) => getProjectDisplay(project, index))
    .filter((project): project is { title: string; description: string } => Boolean(project));

  return (
    <>
      <div className="nav-inert-wrapper" inert={isAnalyzing ? true : undefined} aria-hidden={isAnalyzing || undefined}>
        <WorkspaceNavigation activeKey={navKey} onNavigate={navigateTo} />
      </div>
      {activeView === "welcome" ? (
        <WelcomeIntro onNavigate={navigateTo} />
      ) : null}

      {activeView !== "welcome" ? (
        <main className="workflow-shell" inert={isAnalyzing ? true : undefined} aria-hidden={isAnalyzing || undefined}>
          {["analyze", "cover", "answer"].includes(activeView) ? (
            <section className={`workflow-panel analyze-panel${activeView === "analyze" ? "" : " writing-wizard"}`}>
              <header className="view-header">
                {activeView === "analyze" ? <div className="writing-entry-nav"><button type="button" className="secondary-btn small" onClick={() => { setAnalysisError(""); if (window.location.hash === "#analyze" && window.history.length > 1) { setActiveView("welcome"); window.history.back(); } else navigateTo("home"); }}>← Back to Home</button></div> : null}
                <span className="eyebrow">{activeView === "cover" ? "DIRECT COVER LETTER" : activeView === "answer" ? "DIRECT APPLICATION ANSWER" : "RESUME + JOB DESCRIPTION"}{activeView !== "analyze" ? ` · STEP ${writingScene === "upload" ? "01" : "02"} OF 03` : ""}</span>
                <h1>{activeView === "cover" ? writingScene === "upload" ? "Start with your resume and role." : "Shape the letter before it’s written." : activeView === "answer" ? writingScene === "upload" ? "Start with your resume and role." : "Set up your answer." : "Understand your fit."}</h1>
                <p>
                  {activeView === "analyze" ? "Compare your experience with a role and get a skills roadmap." : writingScene === "upload" ? "Add your resume and the job description, then shape your answer. Context is prepared only when you choose Generate." : "Review the parsed evidence, then choose how the selected writer should respond."}
                </p>
              </header>

              {activeView !== "analyze" && writingScene === "upload" ? <div className="writing-entry-nav"><button type="button" className="secondary-btn small" onClick={backToStudio}>← Back to AI Studio</button></div> : null}

              {(activeView === "analyze" || writingScene === "upload") ? <div className="analyze-grid">
                <section className="input-column">
                  <div className="input-column-head">
                    <div>
                      <h2>Resume</h2>
                      <p>PDF extraction stays editable.</p>
                    </div>
                    <label className="upload-inline upload-dropzone" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); void handleResumeFile(event.dataTransfer.files?.[0]); }}>
                      <input
                        className="file-input"
                        type="file"
                        accept=".pdf,application/pdf"
                        onChange={handleResumeUpload}
                        disabled={isUploading || isAnalyzing}
                      />
                      {isUploading ? "Extracting..." : "Upload PDF or drop here"}
                    </label>
                  </div>

                  {uploadMessage ? <p className="state-message success">{uploadMessage}</p> : null}
                  {uploadError ? <p className="state-message error">{uploadError}</p> : null}

                  <label className="field-label" htmlFor="resume-text">
                    Resume text
                  </label>
                  <textarea
                    id="resume-text"
                    className="input-box workflow-textarea"
                    value={resumeText}
                    onChange={(event) => handleResumeTextChange(event.target.value)}
                    placeholder="Paste resume text or upload a PDF"
                    disabled={isAnalyzing}
                  />
                </section>

                <section className="input-column">
                  <div className="input-column-head">
                    <div>
                      <h2>Job Description</h2>
                      <p>Paste the role exactly as posted.</p>
                    </div>
                    <button className="secondary-btn small" type="button" onClick={useSampleData} disabled={isAnalyzing}>
                      Sample
                    </button>
                  </div>

                  <label className="field-label" htmlFor="job-description">
                    Opportunity text
                  </label>
                  <textarea
                    id="job-description"
                    className="input-box workflow-textarea"
                    value={jobDescription}
                    onChange={(event) => handleJobDescriptionChange(event.target.value)}
                    placeholder="Paste internship/job description here"
                    disabled={isAnalyzing}
                  />
                </section>
              </div> : null}

              {activeView !== "analyze" && writingScene === "customize" ? (
                <div className="writing-customize-scene">
                  <div className="writing-scene-top-actions">
                    <button type="button" className="secondary-btn small" onClick={backToWriterInputs} disabled={isAnalyzing}>← Back to Step 1</button>
                    {inputsPrepared ? <StatusBadge status="success">Inputs analyzed</StatusBadge> : null}
                  </div>
                  <SkeletonReveal
                    loading={isPreparingWriting}
                    revealDuration={360}
                    skeleton={<div className="evidence-summary-skeleton"><Skeleton variant="shimmer" className="evidence-skeleton-block" /><Skeleton variant="shimmer" className="evidence-skeleton-block" /><Skeleton variant="shimmer" className="evidence-skeleton-block" /><Skeleton variant="shimmer" className="evidence-skeleton-block" /></div>}
                    className="evidence-summary-reveal"
                  >
                    <section className="evidence-summary" aria-label="Recognized resume evidence">
                      <div className="evidence-summary-heading"><div><span className="eyebrow">PREPARED CONTEXT</span><h2>{getPreparedRoleTitle(preparedWriting?.job_profile?.role_title)}{preparedWriting?.job_profile?.company_name ? ` · ${preparedWriting.job_profile.company_name}` : ""}</h2></div>{preparedWriting?.resume_profile?.name ? <span>Name detected: {preparedWriting.resume_profile.name}</span> : <span className="evidence-unknown-name">No name detected</span>}</div>
                      <div className="evidence-summary-grid">
                        <div><h3>Relevant skills</h3><div className="evidence-tags">{(preparedWriting?.match_result?.matched_skills || []).length ? preparedWriting!.match_result!.matched_skills!.map((skill) => <span key={`matched-${skill}`}>{skill}</span>) : <p>No direct skill matches were detected.</p>}</div></div>
                        <div><h3>Skills to build</h3><div className="evidence-tags evidence-tags-muted">{(preparedWriting?.match_result?.missing_skills || []).length ? preparedWriting!.match_result!.missing_skills!.slice(0, 6).map((skill) => <span key={`missing-${skill}`}>{skill}</span>) : <p>No skill gaps were identified.</p>}</div></div>
                      </div>
                      <div className="evidence-project-list"><h3>Projects in your resume</h3>{preparedProjectDisplays.length ? preparedProjectDisplays.map((project, index) => <article key={`${project.title}-${index}`}><strong>{project.title}</strong>{project.description ? <p>{project.description}</p> : null}</article>) : <p>No project details were detected in the resume text.</p>}</div>
                      {(preparedWriting?.resume_profile?.education || []).length ? <p className="evidence-education"><strong>Education:</strong> {preparedWriting!.resume_profile!.education!.join(" · ")}</p> : null}
                    </section>
                  </SkeletonReveal>
                  <section className={`writing-preferences-scene${activeView === "answer" ? " answer-preferences-scene" : ""}`} aria-label="Writing preferences">
                    {activeView === "cover" ? <div className="writing-preferences-heading"><span className="eyebrow">MAKE IT YOURS</span><h2>How should the letter read?</h2></div> : null}
                    {activeView === "answer" ? <section className="application-question-card" aria-labelledby="application-question-title">
                      <div className="question-card-heading">
                        <span className="question-card-icon" aria-hidden="true"><MessageSquareText size={22} strokeWidth={2} /></span>
                        <div>
                          <h3 id="application-question-title">What question are you answering?</h3>
                          <p>Paste the exact question from the application form. We'll use your resume to prepare an answer.</p>
                        </div>
                      </div>
                      <label className="question-field-label" htmlFor="application-question">Application question</label>
                      <textarea id="application-question" aria-describedby="application-question-help" className="input-box question-textarea" value={applicationQuestion} onChange={(event) => setApplicationQuestion(event.target.value)} placeholder="Paste the question from the application…" disabled={isAnalyzing} />
                      <p className="sr-only" id="application-question-help">Paste the exact question from the application form.</p>
                      <div className="question-examples" aria-label="Example questions">
                        <span>Or start with an example</span>
                        <div>{[{ label: "Why hire me?", question: "Why should we hire you for this internship?" }, { label: "Relevant experience", question: "Describe your relevant experience for this role." }, { label: "Why this role?", question: "Why are you interested in this role?" }].map((example) => <Button key={example.label} type="button" variant="outline" size="sm" className="question-example-chip" disabled={isAnalyzing} onClick={() => setApplicationQuestion(example.question)}>{example.label}</Button>)}</div>
                      </div>
                      <div className="question-preference-divider" />
                      <div className="question-preference-groups">
                        <fieldset className="preference-radio-fieldset">
                          <legend>Tone</legend>
                          <RadioGroup value={tone} onValueChange={(value) => setTone(value as Tone)} className="preference-radio-options" aria-label="Tone">
                            {toneOptions.map((option) => <div className="preference-radio-choice" key={option.value}><RadioGroupItem id={`answer-tone-${option.value}`} value={option.value} className="preference-radio-input" disabled={isAnalyzing} /><label htmlFor={`answer-tone-${option.value}`}>{option.label}</label></div>)}
                          </RadioGroup>
                        </fieldset>
                        <fieldset className="preference-radio-fieldset">
                          <legend>Answer length</legend>
                          <RadioGroup value={String(wordLimit)} onValueChange={(value) => setWordLimit(Number(value))} className="preference-radio-options" aria-label="Answer length">
                            {answerLengthOptions.map((option) => <div className="preference-radio-choice" key={option.value}><RadioGroupItem id={`answer-length-${option.value}`} value={String(option.value)} className="preference-radio-input" disabled={isAnalyzing} /><label htmlFor={`answer-length-${option.value}`}>{option.label}</label></div>)}
                          </RadioGroup>
                        </fieldset>
                      </div>
                    </section> : null}
                    {activeView === "cover" ? <div className="cover-preference-grid">
                      <fieldset className="preference-radio-fieldset">
                        <legend>Tone</legend>
                        <RadioGroup value={tone} onValueChange={(value) => setTone(value as Tone)} className="preference-radio-options" aria-label="Tone">
                          {toneOptions.map((option) => <div className="preference-radio-choice" key={option.value}><RadioGroupItem id={`cover-tone-${option.value}`} value={option.value} className="preference-radio-input" disabled={isAnalyzing} /><label htmlFor={`cover-tone-${option.value}`}>{option.label}</label></div>)}
                        </RadioGroup>
                      </fieldset>
                      <fieldset className="preference-radio-fieldset">
                        <legend>Letter length</legend>
                        <RadioGroup value={coverLetterLength} onValueChange={(value) => setCoverLetterLength(value as CoverLetterLength)} className="preference-radio-options" aria-label="Letter length">
                          {lengthOptions.map((option) => <div className="preference-radio-choice" key={option.value}><RadioGroupItem id={`cover-length-${option.value}`} value={option.value} className="preference-radio-input" disabled={isAnalyzing} /><label htmlFor={`cover-length-${option.value}`}>{option.label}</label></div>)}
                        </RadioGroup>
                      </fieldset>
                    </div> : null}
                  </section>
                </div>
              ) : null}

              {analysisError ? <p className="state-message error" role="alert">{analysisError}</p> : null}

              {activeView !== "analyze" && writingScene === "upload" ? <p className="backend-note">Analyze your resume and role context first. No writing model is called during preparation.</p> : null}

              {activeView !== "analyze" ? <WritingProgress step={writingScene === "upload" ? 0 : 1} /> : null}

              <div className="view-actions view-actions-centered">
                {activeView === "analyze" ? (
                  <MorphButton className="generate-morph-button" size="md" state={isAnalyzing ? "loading" : "idle"} loadingLabel="Analyzing opportunity…" disabled={isUploading || isAnalyzing} onClick={() => generateFor("results")}>Analyze Opportunity</MorphButton>
                ) : writingScene === "customize" ? (
                  <MorphButton className="generate-morph-button" size="md" state={isAnalyzing ? "loading" : "idle"} loadingLabel={activeView === "cover" ? "Generating cover letter…" : "Generating answer…"} disabled={isUploading || isAnalyzing || !resumeText.trim() || !jobDescription.trim() || (activeView === "answer" && !applicationQuestion.trim())} onClick={() => generateFor(activeView === "cover" ? "cover" : "answer")}>{activeView === "cover" ? "Generate Cover Letter" : "Generate Answer"}</MorphButton>
                ) : (
                  <MorphButton className="generate-morph-button" size="md" state={isAnalyzing ? "loading" : "idle"} loadingLabel="Analyzing your resume and job description…" disabled={isUploading || isAnalyzing || !resumeText.trim() || !jobDescription.trim()} onClick={() => handlePrepareWriting(activeView === "cover" ? "cover" : "answer")}>Analyze Resume</MorphButton>
                )}
              </div>
              {activeView !== "analyze" && writingScene === "customize" && writerCallStatus === "error" && analysisError ? <p className="state-message error" role="alert">{analysisError}</p> : null}
            </section>
          ) : null}


          {hasActiveWritingResult && (activeView === "cover-result" || activeView === "answer-result") ? (
            <motion.section
              className="workflow-panel direct-output-panel result-reveal"
              initial={reduceMotion ? false : { opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={reduceMotion ? { duration: 0 } : { duration: 0.34, ease: [0.22, 1, 0.36, 1] }}
            >
              <header className="view-header compact"><span className="eyebrow">{activeView === "cover-result" ? "YOUR COVER LETTER" : "YOUR APPLICATION ANSWER"}</span><h1>Make it sound like you.</h1><p>Edit freely. Changes stay on this page and do not trigger another generation.</p></header>
              <WritingEditor
                title={activeView === "cover-result" ? "Cover Letter" : "Application Answer"}
                value={activeView === "cover-result" ? editableCover : editableAnswer}
                onChange={activeView === "cover-result" ? setEditableCover : setEditableAnswer}
                source={getDraftSource(activeWritingResult)}
                sourceDetail={activeWritingResult?.used_fallback ? activeWritingResult.fallback_reason : activeWritingResult?.llm_provider}
                placeholder={activeView === "cover-result" ? "Your generated cover letter will appear here." : "Your generated answer will appear here."}
                disabled={isAnalyzing}
                onCopy={() => copyText(activeView === "cover-result" ? "cover" : "answer", activeView === "cover-result" ? editableCover : editableAnswer)}
                copied={copiedTarget === (activeView === "cover-result" ? "cover" : "answer")}
                onRegenerate={() => generateFor(activeView === "cover-result" ? "cover" : "answer")}
                onBack={handleBackToCustomize}
                backLabel="← Customize draft"
                isGenerating={isAnalyzing}
                reveal
              />
              <WritingProgress step={2} />
              {analysisError ? <p className="state-message error" role="alert">{analysisError}</p> : null}
            </motion.section>
          ) : null}

          {activeView === "results" ? (
            <motion.section
              className="workflow-panel results-panel"
              initial={reduceMotion ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={reduceMotion ? { duration: 0 } : { duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            >
              <header className="results-hero">
                <div>
                  <div className="writing-entry-nav"><button type="button" className="secondary-btn small" onClick={() => { setActiveView("analyze"); setAnalysisError(""); if (window.location.hash === "#results" && window.history.length > 1) window.history.back(); else window.history.replaceState({ internai: true }, "", "#analyze"); }}>← Back to Analyze</button></div>
                  <span className="eyebrow">Results</span>
                  <h1>{roleCompanyLine}</h1>
                  <p>
                    {result
                      ? `${candidateName} has ${matchedSkills.length} matched skills and ${missingSkills.length} priority gaps for this opportunity.`
                      : "Run an analysis to see match evidence."}
                  </p>
                </div>
                <div className="match-score-block">
                  <span>{typeof matchScore === "number" ? matchScore : "--"}</span>
                  <p>{result ? matchLevel : "Waiting"}</p>
                </div>
              </header>

              <div className="skills-focus-grid">
                <section>
                  <h2>Matched skills</h2>
                  <div className="skills-wrap">
                    {matchedSkills.length ? (
                      matchedSkills.map((skill) => (
                        <span key={`matched-${skill}`} className="skill-pill">
                          {skill}
                        </span>
                      ))
                    ) : (
                      <p className="empty-copy">No matched skills yet.</p>
                    )}
                  </div>
                </section>

                <section>
                  <h2>Missing skills</h2>
                  <div className="skills-wrap">
                    {missingSkills.length ? (
                      missingSkills.slice(0, 12).map((skill) => (
                        <span key={`missing-${skill}`} className="skill-pill missing">
                          {skill}
                        </span>
                      ))
                    ) : (
                      <p className="empty-copy">No missing skills to show.</p>
                    )}
                  </div>
                </section>
              </div>

              {scoreBreakdownEntries.length ? (
                <details
                  className="breakdown-panel"
                  open={isBreakdownOpen}
                  onToggle={(event) => setIsBreakdownOpen(event.currentTarget.open)}
                >
                  <summary>Score breakdown</summary>
                  <div className="score-breakdown-grid">
                    {scoreBreakdownEntries.map(([label, value]) => (
                      <div className="score-chip" key={String(label)}>
                        <span>{label}</span>
                        <strong>{typeof value === "number" ? value : "--"}</strong>
                      </div>
                    ))}
                  </div>
                </details>
              ) : null}

              <details className="results-roadmap">
                <summary>View learning roadmap</summary>
                {roadmap.length ? <div className="roadmap-grid">
                  {roadmap.map((item) => <article key={`${item.week}-${item.focus}`} className="roadmap-card-item">
                    <span className="roadmap-week">Week {item.week}</span><h4>{item.focus}</h4>
                    {item.skills?.length ? <div className="roadmap-skills">{item.skills.slice(0, 4).map((skill) => <span key={`${item.week}-${skill}`}>{skill}</span>)}</div> : null}
                    {item.tasks?.length ? <ul>{item.tasks.slice(0, 3).map((task) => <li key={task}>{task}</li>)}</ul> : null}
                    {item.outcome ? <p>{item.outcome}</p> : null}
                  </article>)}
                </div> : <p className="empty-copy">No learning roadmap is available for this result.</p>}
              </details>

              <section className="results-next-actions" aria-labelledby="results-next-title">
                <div><span className="eyebrow">NEXT STEP</span><h2 id="results-next-title">What would you like to create?</h2><p>Your resume and role context will be reused. No writing is generated until you choose Generate.</p></div>
                <div className="studio-choice-grid results-choice-grid">
                  <AnimatedCard icon={<HugeiconsIcon icon={File02Icon} size={24} />} title="Create a Cover Letter" description="Build an editable letter for this opportunity." hints={["Tone and length", "Editable draft"]} onSelect={() => openWritingWorkflow("cover")} />
                  <AnimatedCard icon={<HugeiconsIcon icon={PencilEdit01Icon} size={24} />} title="Answer Application Question" description="Respond to the exact question from the application." hints={["Question-aware", "Tone and length"]} onSelect={() => openWritingWorkflow("answer")} />
                </div>
              </section>

              <div className="view-actions results-actions">
                <button
                  className="secondary-btn"
                  type="button"
                  onClick={handleSaveApplication}
                  disabled={!result || !resultFromFullAnalysis || isSaving || hasSavedCurrentResult}
                >
                  {isSaving
                    ? "Saving..."
                    : hasSavedCurrentResult
                      ? "Saved"
                      : "Save to Tracker"}
                </button>
              </div>

              {saveMessage ? <p className="state-message success">{saveMessage}</p> : null}
              {saveError ? <p className="state-message error">{saveError}</p> : null}
            </motion.section>
          ) : null}

          {activeView === "studio" ? (
            <section className="workflow-panel studio-panel studio-landing">
              <header className="view-header compact">
                <span className="eyebrow">AI Studio</span>
                <h1>What would you like to create?</h1>
                <p>Choose a writing task. Nothing is generated until you choose Generate in that workflow.</p>
              </header>

              <div className="studio-choice-grid">
                <AnimatedCard icon={<HugeiconsIcon icon={File02Icon} size={26} />} title="Create a Cover Letter" description="Write a focused letter grounded in your resume and the role." hints={["Tone and length", "Editable draft"]} onSelect={() => openWritingWorkflow("cover")} />
                <AnimatedCard icon={<HugeiconsIcon icon={PencilEdit01Icon} size={26} />} title="Create an Application Answer" description="Answer the exact employer question with relevant evidence." hints={["Exact question", "Tone and length"]} onSelect={() => openWritingWorkflow("answer")} />
              </div>
              {resultFromFullAnalysis && result ? <button className="secondary-btn small studio-back-results" type="button" onClick={() => { setStudioTarget(null); setActiveView("results"); window.history.replaceState(null, "", "#results"); }}>← Back to Results</button> : null}

              <div className="studio-tabs" role="tablist" aria-label="AI Studio sections">
                {[
                  ["answer", "Application Answer"],
                  ["cover", "Cover Letter"],
                  ["roadmap", "Roadmap"],
                ].map(([tab, label]) => (
                  <button
                    key={tab}
                    type="button"
                    role="tab"
                    aria-selected={studioTab === tab}
                    className={studioTab === tab ? "is-active" : ""}
                    onClick={() => setStudioTab(tab as StudioTab)}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {studioTab === "answer" ? (
                <WritingEditor
                  title="Application Answer"
                  value={editableAnswer}
                  onChange={setEditableAnswer}
                  source={getDraftSource(result?.application_answer)}
                  sourceDetail={result?.application_answer?.used_fallback ? result.application_answer.fallback_reason : result?.application_answer?.llm_provider}
                  placeholder="Run an analysis to generate a tailored application answer."
                  onCopy={() => copyText("answer", editableAnswer || applicationAnswer)}
                  copied={copiedTarget === "answer"}
                  onEditInputs={() => openWritingWorkflow("answer")}
                  onRegenerate={() => generateFor("answer")}
                  onBack={backToStudio}
                  backLabel="← Back to results"
                  editInputsLabel="Edit inputs"
                  isGenerating={isAnalyzing}
                />
              ) : null}

              {studioTab === "cover" ? (
                <WritingEditor
                  title="Cover Letter"
                  value={editableCover}
                  onChange={setEditableCover}
                  source={getDraftSource(result?.cover_letter)}
                  sourceDetail={result?.cover_letter?.used_fallback ? result.cover_letter.fallback_reason : result?.cover_letter?.llm_provider}
                  placeholder="Run an analysis to generate a cover letter."
                  onCopy={() => copyText("cover", editableCover || coverLetter)}
                  copied={copiedTarget === "cover"}
                  onEditInputs={() => openWritingWorkflow("cover")}
                  onRegenerate={() => generateFor("cover")}
                  onBack={backToStudio}
                  backLabel="← Back to results"
                  editInputsLabel="Edit inputs"
                  isGenerating={isAnalyzing}
                />
              ) : null}

              {studioTab === "roadmap" ? (
                <section className="roadmap-focus">
                  {prioritySkills.length ? (
                    <div className="skills-wrap compact">
                      {prioritySkills.map((skill) => (
                        <span key={`roadmap-priority-${skill}`} className="skill-pill">
                          {skill}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  <div className="roadmap-grid">
                    {roadmap.length ? (
                      roadmap.map((item) => (
                        <article key={`${item.week}-${item.focus}`} className="roadmap-card-item">
                          <span className="roadmap-week">Week {item.week}</span>
                          <h4>{item.focus}</h4>
                          {item.skills?.length ? (
                            <div className="roadmap-skills">
                              {item.skills.slice(0, 4).map((skill) => (
                                <span key={`${item.week}-${skill}`}>{skill}</span>
                              ))}
                            </div>
                          ) : null}
                          {item.tasks?.length ? (
                            <ul>
                              {item.tasks.slice(0, 3).map((task) => (
                                <li key={`${item.week}-${task}`}>{task}</li>
                              ))}
                            </ul>
                          ) : null}
                          {item.outcome ? <p>{item.outcome}</p> : null}
                        </article>
                      ))
                    ) : (
                      <p className="empty-copy">Run an analysis to generate a roadmap.</p>
                    )}
                  </div>
                </section>
              ) : null}
            </section>
          ) : null}

          {activeView === "tracker" ? (
            <section className="workflow-panel tracker-focus">
              <header className="view-header compact">
                <span className="eyebrow">Application Tracker</span>
                <h1>Saved opportunities.</h1>
                <p>Review saved applications, update statuses, or remove opportunities from the local tracker.</p>
              </header>

              <div className="view-actions">
                <button
                  className="primary-btn"
                  type="button"
                  onClick={handleSaveApplication}
                  disabled={!result || !resultFromFullAnalysis || isSaving || hasSavedCurrentResult}
                >
                  {isSaving
                    ? "Saving..."
                    : hasSavedCurrentResult
                      ? "Current result saved"
                      : "Save Current Result"}
                </button>
              </div>

              {saveMessage ? <p className="state-message success">{saveMessage}</p> : null}
              {saveError ? <p className="state-message error">{saveError}</p> : null}

              <ApplicationTracker
                refreshKey={trackerRefreshKey}
                onDeleted={handleTrackerDelete}
              />
            </section>
          ) : null}
        </main>
      ) : null}

      {isAnalyzing ? (() => {
        const isAnalysis = outputIntent.current === "results";
        const isPreparation = isPreparingWriting;
        const target = outputIntent.current === "cover" ? "cover" : "answer";
        const title = isAnalysis
          ? "Analyzing your resume and job description…"
          : isPreparation
            ? "Analyzing your resume and job description…"
            : target === "cover"
              ? "Generating your cover letter"
              : "Generating your application answer";
        const label = isAnalysis
          ? "Analyzing your resume and job description…"
          : isPreparation
            ? "Analyzing your resume and job description…"
            : target === "cover"
              ? "Generating your cover letter…"
              : "Generating your application answer…";
        const steps = isAnalysis
          ? ["Resume and job description received", "Evidence prepared", "Analysis ready"]
          : isPreparation
            ? ["Resume and job description received", "Evidence prepared", "Inputs ready"]
            : ["Resume and role context ready", "Selected writer request in progress", "Draft returned"];
        const completedSteps = operationComplete ? completedOperationSteps : 1;
        const transitionLabel = operationComplete
          ? isAnalysis ? "Analysis ready, opening results…" : "Draft received, opening editor…"
          : label;
        const overlayDetail = operationComplete
          ? isAnalysis ? "Your skills analysis is ready." : "Your draft is ready."
          : isAnalysis ? "Comparing resume evidence with the role." : isPreparation ? "Preparing resume and role context." : "The selected writer is preparing your requested draft.";
        return (
          <div className="operation-overlay" data-complete={operationComplete || undefined} role="status" aria-live="polite" aria-label={title}>
            <section className="operation-overlay__panel" aria-labelledby="operation-overlay-title">
              <span className="operation-overlay__eyebrow">{isAnalysis ? "SKILLS ANALYSIS" : isPreparation ? "INPUT PREPARATION" : "AI STUDIO"}</span>
              <h2 id="operation-overlay-title">{title}</h2>
              <p className="operation-overlay__outcome">{overlayDetail}</p>
              <ThoughtLine
                working={true}
                completedSteps={completedSteps}
                steps={steps}
                label={transitionLabel}
                doneLabel={operationOutcome || "Ready"}
                glyph="sparkle"
                fontSize={16}
                breathPeriod={1.6}
                breathDepth={0.45}
                settleDuration={350}
                settleBlur={2}
                collapsible={false}
                collapseOnSettle={false}
                showTimer={false}
                settleAfter={0}
                color="var(--theme-ink)"
              />
            </section>
          </div>
        );
      })() : null}
    </>
  );
}
