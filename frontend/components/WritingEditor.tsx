"use client";

import { useEffect, useMemo, useRef } from "react";
import { motion, useReducedMotion } from "framer-motion";

type DraftSource = "ai" | "fallback" | "error" | "rejected" | "unknown";

type WritingEditorProps = {
  title: string;
  value: string;
  onChange: (value: string) => void;
  source: DraftSource;
  sourceDetail?: string;
  placeholder?: string;
  disabled?: boolean;
  onCopy?: () => void;
  copied?: boolean;
  onEditInputs?: () => void;
  onRegenerate?: () => void;
  onBack?: () => void;
  backLabel?: string;
  editInputsLabel?: string;
  isGenerating?: boolean;
  reveal?: boolean;
};

const sourceLabel: Record<DraftSource, string> = {
  ai: "AI-generated draft",
  fallback: "Fallback draft",
  error: "Provider error",
  rejected: "Validation rejected",
  unknown: "Draft source unavailable",
};

export default function WritingEditor({
  title,
  value,
  onChange,
  source,
  sourceDetail,
  placeholder,
  disabled = false,
  onCopy,
  copied = false,
  onEditInputs,
  onRegenerate,
  onBack,
  backLabel = "← Back to customization",
  editInputsLabel = "Edit resume and role",
  isGenerating = false,
  reveal = false,
}: WritingEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const reduceMotion = useReducedMotion();
  const wordCount = useMemo(() => value.trim().split(/\s+/).filter(Boolean).length, [value]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.max(textarea.scrollHeight, 300)}px`;
  }, [value]);

  const content = (
    <>
    <div className="writing-editor-navigation" aria-label="Document navigation">
      {onBack ? <button className="editor-back-action" type="button" onClick={onBack}>{backLabel}</button> : null}
      {onEditInputs ? <button className="editor-edit-inputs-action" type="button" onClick={onEditInputs}>{editInputsLabel}</button> : null}
    </div>
    <article className="writing-editor document-panel" aria-label={`${title} editor`}>
      <header className="writing-editor-header">
        <div>
          <p className={`writing-source writing-source--${source}`} role="status">
            <span aria-hidden="true" />
            {sourceLabel[source]}{sourceDetail ? ` · ${sourceDetail}` : ""}
          </p>
          <h2>{title}</h2>
        </div>
        <span className="writing-word-count" aria-live="polite">{wordCount} {wordCount === 1 ? "word" : "words"}</span>
      </header>

      <div className="writing-editor-toolbar" role="group" aria-label="Document actions">
        {onCopy ? <button className="secondary-btn small" type="button" onClick={onCopy} disabled={!value.trim()}>{copied ? "Copied" : "Copy"}</button> : null}
        {onRegenerate ? <button className="secondary-btn small" type="button" onClick={onRegenerate} disabled={isGenerating}>{isGenerating ? "Generating…" : "Regenerate"}</button> : null}
      </div>

      <label className="sr-only" htmlFor={`writing-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}>Edit {title}</label>
      <textarea
        ref={textareaRef}
        id={`writing-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
        className="writing-editor-content"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder ?? "Your writing will appear here."}
        disabled={disabled}
        spellCheck
      />
      <p className="writing-review-note">Review names, details, and claims before submitting. Your edits stay on this page.</p>
    </article>
    </>
  );

  return reveal ? (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 10, clipPath: "inset(0 0 14% 0 round 18px)" }}
      animate={{ opacity: 1, y: 0, clipPath: "inset(0 0 0% 0 round 18px)" }}
      transition={reduceMotion ? { duration: 0 } : { duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
    >{content}</motion.div>
  ) : content;
}
