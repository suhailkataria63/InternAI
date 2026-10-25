# InternAI — Work to Codex Handover

**Repository:** `~/Desktop/InternAI`
**Prepared:** 25 October 2026
**Purpose:** Inspection-only handover. This report records the current checkout and the development history visible from the task history and repository. It does not change application behavior.

## Executive summary

InternAI is a Next.js 16.4.3 frontend backed by a FastAPI service. The current source separates resume/job analysis from writing: the analysis endpoint performs deterministic parsing, evidence matching and roadmap preparation; cover letters and application answers are requested from separate, explicit writer endpoints. The UI has a shared navigation shell, a Results screen, a unified AI Studio, direct-writing scenes, a local tracker, light/dark themes and reusable UI components.

The highest-priority follow-up is to reproduce the reported `studioTab` browser error against the current served app and inspect the primary action buttons in the same browser session. In the current checked-out source, `studioTab` is declared, and the Specular Button is not used for those primary actions: they use Spectrum Morph Button. The UI also still contains legacy AI Studio tab/editor JSX below the newer card-based landing screen. These facts make a stale bundle or obsolete duplicated UI a more plausible source of the report than a currently missing state declaration, but this needs browser confirmation.

No live Groq calls were made for this handover. The repository has substantial pre-existing uncommitted work. Do not reset, clean, stage, or overwrite it.

## 1. Current architecture

### Frontend

- **Framework:** Next.js App Router, Next.js **16.4.3**, React 19, TypeScript, Tailwind CSS 4, with application styling primarily in `frontend/app/globals.css`.
- **Application shell:** `frontend/app/layout.tsx` loads the shared theme provider and toast host. `frontend/components/WorkspaceNavigation.tsx` is the shared Home | Analyze | AI Studio | Tracker navigation, with Gooey Nav on wider layouts and a mobile alternative.
- **Main view/state owner:** `frontend/app/page.tsx` is a client-side workflow controller. It uses view state plus URL hashes/history for home, analyze, results, AI Studio writer subflows, draft views and tracker. It also owns input/prepared-context/draft state and request lifecycle coordination.
- **API client:** `frontend/lib/api.ts` wraps backend fetch calls. `NEXT_PUBLIC_API_URL` selects the backend base URL; the code default is `http://127.0.0.1:8000`.
- **Theme:** `frontend/components/theme/ThemeProvider.tsx` stores the user preference in local storage, otherwise follows the operating-system preference. The layout has a pre-hydration theme script to reduce first-paint flash. Semantic Soft Porcelain and Midnight Indigo variables live in the global CSS.
- **Writing:** Cover Letter and Application Answer share a scene-based workflow in `page.tsx`; `frontend/components/WritingEditor.tsx` provides a plain-text editable document, word count and copy/regenerate/navigation actions. Editing and copying are client-side and do not call a writer.
- **Tracker:** `frontend/components/ApplicationTracker.tsx` loads records, updates statuses and deletes records through the tracker API. Current code includes loading/error/empty states and request-staleness protection.
- **Authentication:** Log In and Sign Up remain mock controls that open a Coming Soon dialog. There are no user accounts or auth sessions.

### Backend

- **Framework:** FastAPI, with Pydantic schemas, SQLAlchemy persistence, `httpx` provider calls, PyMuPDF for PDF extraction, and pytest tests. App entry point: `backend/app/main.py`.
- **Resume/JD processing:** PDF upload is handled by `backend/app/services/pdf_service.py`; the configured limits are 5 MB and 12 pages. Resume and JD parsing use the corresponding agents/services and are local transformations; they do not themselves require Groq.
- **Analysis:** `backend/app/services/orchestrator_service.py::run_full_application_analysis` runs resume parsing, JD parsing, EvidenceMatch scoring and rule-based skill-gap/roadmap creation. It preserves response compatibility keys for writing outputs, but does not invoke writer agents in the current path. The API route is in `backend/app/api/orchestrator.py`.
- **EvidenceMatch and roadmap:** Matching and skill-gap logic live under `backend/app/agents/` (including `match_scorer.py` and `skill_gap_agent.py`). The analysis orchestrator uses the deterministic rule-based skill-gap path. Preserve the existing scoring and roadmap behavior unless separately authorized.
- **Writing:** Explicit endpoints are `POST /api/application/write` and `POST /api/cover-letter/generate`. They call only the selected writer. The writer agents first have deterministic fallback behavior, then can use the configured provider, and validate provider output before accepting it. Their public response metadata distinguishes source/fallback status.
- **Grounding:** `backend/app/agents/writer_grounding.py` builds candidate evidence with separated project, listed-skill, education/goal and job-context information. The writer validators and diagnostics check claims while retaining strict rejection of unsupported claims. It is not a guarantee that every unsupported paraphrase is caught.
- **LLM provider:** `backend/app/services/llm_service.py` sends OpenAI-compatible chat completion requests to Groq when configured. The requested model used in prior live evaluation was `openai/gpt-oss-120b`. `backend/.env.example` uses mock defaults; the actual `.env` was not inspected. Never copy or disclose its secrets.
- **Retry caveat:** Current config/example defaults have `GROQ_MAX_RETRIES=1`; provider code can therefore make a second provider attempt for eligible failures. Evaluation mode forces a single attempt, but normal writer usage should not be described as guaranteed exactly one HTTP request unless retries are explicitly configured to zero.
- **Evaluation:** `backend/app/services/evaluation_report.py` supports persistent evaluation events and synthetic-only writing capture under explicit evaluation mode. `GROQ_EVALUATION_REPORT_DIR` can select an alternate report directory. `backend/run_controlled_groq_evaluation.py` is a bounded host-side runner for a single application-answer call (one-request/2,000-token limits), not a general two-writer runner.
- **Persistence:** SQLAlchemy tracker storage defaults to a local SQLite database (`sqlite:///./internai.db`); `DATABASE_URL` may override it. Tracker records include application/resume/JD/match/skill-gap/writing/notes/status fields. No database contents were inspected for this report.

### Frontend/backend request flow

The browser calls FastAPI through `frontend/lib/api.ts`. Analyze calls the analysis orchestrator and then displays Results. Direct writing without prepared context first prepares resume/JD/match context through local analysis APIs, then calls exactly one selected writing endpoint. When valid prepared context from Results exists, the UI reuses it. The frontend uses abort/request identifiers to suppress stale analysis/writer responses when inputs or views change; tracker requests also guard against stale responses.

## 2. Work development history

The history below distinguishes confirmed current source from requested work and milestone results reported in the conversation. File inventory/status is the current checkout, not a reconstruction of every intermediate diff.

| Task | Objective and outcome | Current evidence / limitations |
|---|---|---|
| 1 | Integrate the verified Next.js 16.4.3 security update while preserving R8.2 frontend changes. | Current package files and installed Next package show 16.4.3. The lockfile contains the current UI dependencies; do not replace it wholesale. |
| 2 | Audit Groq grounding and fallback causes. | Investigation task; findings informed later writer validation/grounding work. |
| 3 | Improve validators, evidence relevance, prompts and safe diagnostics. | Current writer agents, grounding module, config and focused tests are present. No claim that every planned fix is perfect. |
| 4 | Controlled live test of three synthetic profiles, up to six requests/12,000 tokens. | Historical request. Do not infer missing per-call token values from this handover. |
| 5 | Add validation diagnostics and persistent synthetic evaluation reporting. | `evaluation_report.py`, diagnostics and tests are present; report files remain local/gitignored. |
| 6 | Wire explicit evaluation mode, durable attempt/result events, budgets and synthetic-only text capture. | Evaluation service and tests are present. Instrumentation does not change ordinary public response contracts. |
| 7 | Two-call synthetic diagnosis. | Historical controlled evaluation. Preserve only values explicitly recorded elsewhere; do not invent usage records. |
| 8 | Precise claim-grounding corrections and regression fixtures. | Grounding/validator tests and code are present. |
| 9 | Controlled re-verification with two calls. | Historical task; no additional conclusions or token figures are asserted here. |
| 10 | Evidence-constrained prompts/ledger and focused mocked tests. | Current grounding module and related tests exist. One writer call per explicit request is the intended app flow; provider retry configuration caveat remains. |
| 11 | Controlled verification, blocked by report storage/network access. | Later tasks added configurable report location and host runner. Do not state that the requested full two-call test completed. |
| 11A–11E | Repair/redirect report storage and resume verification. | Reporter and `GROQ_EVALUATION_REPORT_DIR` exist. The user reported host/sandbox permission/network blockers; preserve saved records. No full Task 11 verification is claimed. |
| 12 | Diagnose provider connectivity without authenticated calls. | Investigation only; actual `.env` secrets are not included in this report. |
| 13 | Prepare a host-side controlled evaluation entry point, not execute it. | Current `backend/run_controlled_groq_evaluation.py` exists with preflight and one-application-answer request/token limits. |
| 14 | Add fact-first anchors and narrowly correct a reproduced false positive. | Current grounding/writer changes and task tests are present. |
| 15 | Reconcile Task 13 evidence/fixture discrepancy and JD field mapping. | User reported: the live and mocked letters had different wording; live writing's unsupported intent to write tests triggered validation. A runner bug used `title`/`company` where evidence expected `role_title`/`company_name`; mapping corrected and covered. User reported 56 focused tests passed, zero Groq calls. |
| 16 | Prepare one-call app-answer verification. | User reported one successful live Groq request using 619 tokens; answer was rejected for unsupported project details. Current runner is configured for one application-answer request, 2,000 tokens, zero retries. |
| 17 | Offline constrained-composition prototype. | Isolated `backend/prototypes/task17_constrained_composition.py` and tests exist; not a production writer replacement. |
| 18 | Improve prototype naturalness with approved composition choices. | Isolated prototype work only; no production writer refactor is evidenced. |
| 19 | Establish redesigned homepage, Analyze and direct-writing workflows. | Current frontend contains Home, Analyze, Results, Studio, Tracker and shared theme/nav elements. |
| 20 | Integration and visual QA of the initial redesign. | Follow-up visual refinements are in current frontend. This report does not claim complete browser QA across all states. |
| 20 refinement | Improve overall contrast/readability, Results/Studio/Tracker and visual consistency. | Current design tokens and screen styling exist. |
| 21 | Add Gooey Nav and light/dark theme. | Current Gooey Nav and theme provider/toggle source are present. |
| 22 | Unify navbar, theme toggle, center writing actions and add generation transitions. | Current shared navigation and Morph Button action paths are present. |
| 23 | Center Analyze action and create reusable writing editor. | Morph Button and `WritingEditor.tsx` exist. Editor is plain text, not TipTap/rich text. |
| 24 | Three-scene writing experience. | Current writing flow has resume/JD, customize and draft scenes; prepared context can skip redundant preparation. Backend does not expose a distinct new prepare endpoint; local parsing/matching APIs are used. |
| 25 | Improve question card, prepared evidence display, Tracker readability and Results actions. | Current source contains the dedicated question card, compact evidence display, theme-aware tracker and aligned Results actions. |
| 26 | On-demand AI Studio and analysis-only orchestration. | Current orchestrator is analysis-only; explicit writer endpoints remain. UI has AI Studio workflow cards and separate writers. ThoughtLine, Stepper, skeletons, toast, Morph Button and card components are present. |
| 26 follow-up | Correct generation/loading presentation based on screenshots. | Current code includes a modal-like request overlay and staged visible status/tick animation bound to request state. Latest typecheck and production build were reported passing in the prior active work. This is not a substitute for full real-browser accessibility/performance QA. |

### Current analysis-only behavior

Current source `run_full_application_analysis` does not call `application_writer_agent` or `cover_letter_agent`; the frontend `handleAnalyze` path calls the orchestrator and displays Results. Opening Results, opening AI Studio, selecting a writer, selecting an example question, changing preferences, editing/copying, or navigating back does not call a writer. Only explicit Generate or Regenerate calls the selected writer endpoint. A focused backend mock test `backend/tests/test_analysis_on_demand.py` verifies the zero-writer-call analysis path.

## 3. Current navigation and user journeys

### Home → Analyze → Results → AI Studio → writer

1. Home action navigates to Analyze.
2. User uploads a PDF or pastes resume text and supplies the job description.
3. Analyze Opportunity calls the analysis-only orchestration path. Parsing, match score, matched/missing skills and rule-based roadmap are produced; no writer endpoint is invoked.
4. Results shows fit/match information and roadmap, with actions to save to Tracker or open a selected AI Studio writer.
5. Choosing a Results action reuses prepared evidence and opens that writer's customize scene; it does not generate content.
6. User configures the exact application question (for answer writer), tone and supported length/preferences, then explicitly selects Generate. Only the selected writer endpoint is invoked.
7. The returned writing appears in the editable document with source/fallback status. Copy/edit/back do not make a writer request; Regenerate explicitly invokes the selected writer again.

### Direct Home/navbar → AI Studio

AI Studio can be opened without an analysis. Selecting a writing card does not call Groq. The user supplies resume and JD, prepares context with the local parsing/matching APIs, then configures the writer and explicitly generates. When valid evidence is already available from Results, the workflow can skip redundant upload/preparation. Changing resume/JD invalidates old prepared context and draft association; changing only question or preferences reuses valid resume/JD preparation.

### Cancellation, stale responses and errors

The main page tracks requests with abort controllers/request IDs. Navigating away or changing inputs aborts/invalidate work where supported; late results are discarded. Writer errors and validator failures are represented with deterministic fallback/source metadata when returned by the backend. The UI should not present a fallback as successful AI output. Verify actual error copy against running backend responses before changing contracts.

### Verified versus intended

- **Source-verified:** Analysis orchestration has no writer calls; explicit writer APIs remain separate; UI calls the selected writer only on Generate/Regenerate; shared nav and state are present.
- **Focused test evidence:** `test_analysis_on_demand.py` passed once in the immediately preceding work (1 test), with mocks confirming no writer/LLM calls.
- **Not fully verified end-to-end:** All four journeys with a running browser + FastAPI, PDF extraction in-browser, tracker CRUD, theme persistence/reload, all mobile breakpoints, screen-reader behavior, reduced-motion/WebGL fallback, and every provider/validator error state. No live Groq was used in recent work.

## 4. Critical current bugs and diagnosis

### Bug A — `ReferenceError: studioTab is not defined` (reported at `frontend/app/page.tsx:1168`)

The current checkout declares `const [studioTab, setStudioTab] = useState<StudioTab>("answer")` around line 236. The old tabbed Studio JSX still references these names in the later legacy section around lines 1151–1208. Thus the reported undefined variable is **not reproducible from current source**; line 1168 in this checkout is within the legacy tab area, but the state exists earlier. The likely causes are an old/stale development or production bundle, source-map mismatch, or a partially hot-reloaded prior component version.

There is a related verified source-level cleanup issue: the old tabbed Studio editor/roadmap tree still renders below the new card-based AI Studio landing section. This creates duplicate/obsolete content and can make the page seem inconsistent. Minimal next steps: restart the current dev server, hard reload, reproduce while recording the console/source map, confirm the served asset matches this checkout, then remove the legacy tab/editor JSX only if it is still rendered and no longer required. Avoid a router rewrite.

### Bug B — primary Analyze/Generate buttons missing or broken after Specular integration

Current primary actions in `frontend/app/page.tsx` use Spectrum `MorphButton`; `React Bits SpecularButton` exists under `frontend/components/react-bits/` but is not imported into the active page. Therefore this checkout does not use Specular for Analyze/Generate and does not reproduce the reported WebGL-related button failure.

The current action is conditional on the Analyze/writing view and is disabled while a request/upload is active or required text is absent. A prior browser accessibility snapshot found the Generate Answer button in the DOM but disabled when inputs were empty. The Morph Button returns a semantic native button, so its click semantics do not depend on the Specular WebGL effect. The action may be below the fold; disabled state, stale bundle, styling/stacking, or an unsubmitted form may explain the screenshots better than a missing component.

Minimal verification: on current source, inspect DOM/accessibility tree and computed visibility/opacity/z-index at desktop/mobile, first with empty inputs and then valid inputs; inspect console and network calls. Confirm each button submits the form and is disabled only for a clear reason. Keep one button system; do not switch to WebGL Specular blindly.

### Other current UX concerns

- Legacy AI Studio tabs/editors are still present after the card-based landing UI, as noted above.
- The writing Stepper is a progress display rather than a required interactive control; its trigger element is non-interactive. This is acceptable if it remains clearly decorative/status-only, but it should not be presented as a keyboard-operable step-navigation control.
- ThoughtLine's stages are app-authored status text, not model reasoning. Keep stages factual and bound to confirmed request state.
- Primary writer generation in ordinary mode may retry once under default config. This can exceed a user's assumption of one provider request on a failed attempt; configure retries to zero when a strict single-attempt guarantee is required.

## 5. UI components and dependency inventory

| Component | Library/source | File path | Implemented? | Current working status / notes |
|---|---|---|---|---|
| Gooey Nav | React Bits source, adapted | `frontend/components/react-bits/GooeyNav.tsx` and CSS | Yes, used by shared nav | Active pill + WebGL/fallback handling are present. Browser fallback and GPU/performance behavior not recently exhaustively tested. |
| Specular Button | React Bits source | `frontend/components/react-bits/SpecularButton.tsx` and CSS | Source exists; not active in primary workflows | Native button remains; decorative WebGL effect can skip on reduced motion/no WebGL. Not the button currently used for primary actions. |
| ThoughtLine | React Bits source, TypeScript adaptation | `frontend/components/react-bits/ThoughtLine.tsx` and CSS | Yes, generation/analysis overlay | Adapted to explicit completed-step status; not private chain-of-thought. Recent transition was UI-verified by source/build, not a complete browser timing audit. |
| Morph Button | Spectrum UI adapted source | `frontend/components/spectrumui/morph-button.tsx` | Yes, Analyze and writer CTAs | Semantic motion button and theme styling; actions may be disabled until inputs are valid. |
| Animated Card | Spectrum UI adapted source | `frontend/components/spectrumui/animated-card.tsx` | Yes, Results/AI Studio actions | Accessible card actions; check exact rendered section for legacy duplicate UI. |
| Status Badge | Spectrum UI adapted source | `frontend/components/spectrumui/status-badge.tsx` | Yes | Used for prepared/source status. |
| Stepper | Control UI adapted source | `frontend/components/control-ui/ui/stepper.tsx` | Yes | Controlled progress indicator; not intended to skip required workflow stages. |
| Skeleton | Control UI adapted source | `frontend/components/control-ui/ui/skeleton.tsx` | Yes | Prepared-context/Tracker loading states. |
| Toast | Control UI adapted source | `frontend/components/control-ui/ui/toast.tsx` | Yes | Shared Toaster mounted once; operation success should only toast after actual success. |
| Theme provider/toggle | InternAI implementation using CSS tokens | `frontend/components/theme/ThemeProvider.tsx`, `ThemeToggle.tsx` | Yes | Persistent preference + OS default; theme reload should be retested in browser. |
| Shared writing editor | InternAI reusable component | `frontend/components/WritingEditor.tsx` | Yes | Plain-text textarea editor with copy, count and actions; no TipTap/rich-text formatting. |
| Application Question Card | InternAI UI using existing controls | `frontend/app/page.tsx`, `frontend/components/ui/radio-group.tsx`, `frontend/app/globals.css` | Yes | Exact question field, example chips, tone/length controls. Chip selection changes local field only. |

### Frontend package inventory

`frontend/package.json` currently contains the following runtime dependency families: `next` (16.4.3), `react`/`react-dom` (19), `@base-ui/react`, Hugeicons packages, Radix radio-group/slot, `class-variance-authority`, `clsx`, `framer-motion`, `lucide-react`, and `tailwind-merge`. Tailwind/PostCSS and TypeScript/type packages are dev dependencies. The repository also contains local copied/adapted UI component source; the named component registries are not all runtime packages.

Potential cleanup: verify actual imports before removing packages. `@base-ui/react` and multiple icon systems may be candidates for usage review, but no removal is recommended without an import audit. Framer Motion is actively used; do not add a second general animation runtime for the existing transitions.

### Backend dependencies

The backend requirements include FastAPI/Uvicorn, Pydantic/settings, python-dotenv, python-multipart, PyMuPDF, SQLAlchemy, httpx and pytest. See `backend/requirements.txt` for the authoritative current list.

## 6. Testing and verification evidence

| Area | Most recent evidence | Status |
|---|---|---|
| Frontend TypeScript | `npm run typecheck` passed after the latest overlay/UI change (prior active work). | Verified then; rerun before shipping. |
| Frontend lint | `npm run lint` is configured as `tsc --noEmit`, not ESLint. It passed in earlier Phase 1 verification; not independently rerun for this report. | Note command semantics. |
| Next production build | `npm run build` passed after the latest UI change, using `next build --webpack`; installed Next is 16.4.3. | Verified then; rerun before shipping. |
| `git diff --check` | Passed in prior UI verification. | Verified then. |
| Backend analysis-only test | `backend/.venv/bin/python -m pytest -q tests/test_analysis_on_demand.py`: 1 passed, mocked no-writer/no-LLM behavior. | Focused test verified. |
| Backend full test suite | Task 15 user-reported 56 focused tests passed; this was a historical result, not a current full-suite run. | Not currently verified. |
| Browser smoke | Prior CUA snapshot showed shared navigation, question card, examples and Generate Answer disabled before required inputs. | Partial only. |
| Browser navigation/workflows | No complete running-browser journey through Analyze → Results → Studio → writer was verified in this handover. | Not fully verified. |
| PDF upload/extraction | Backend implementation inspected; browser upload flow not recently exercised. | Not currently browser-verified. |
| Tracker | Component/API integration inspected; no fresh CRUD run. | Not currently verified. |
| Light/dark mode | Provider/toggle implementation inspected; no fresh reload/OS-preference matrix. | Not currently verified. |
| Mobile/responsive/accessibility | CSS and semantic controls inspected; no fresh full mobile/screen-reader/reduced-motion matrix. | Not fully verified. |
| Live Groq | No calls during current implementation/verification. Task 16 is the user-reported historical one-call/619-token exception. | No new calls. |

Suggested commands (run from the respective directories):

```sh
cd frontend
npm run typecheck
npm run lint
npm run build
```

```sh
cd backend
.venv/bin/python -m pytest -q
```

`npm run lint` currently invokes TypeScript checking; it is not a separate ESLint rule pass. Backend development server command in the README is expected to use Uvicorn, e.g. `.venv/bin/python -m uvicorn app.main:app --reload` from `backend/`.

## 7. Git working tree and environment

**Branch:** `develop/internai-2.0`
**HEAD:** `7f8528c` — `Harden InternAI pipeline and frontend dependencies`
**Upstream shown by status:** `origin/codex/internai-audit-fixes`

The following changes were already present before this handover document was created. This report does not alter them.

**Modified tracked files:**

- `.gitignore`, `README.md`, `backend/.env.example`
- `backend/app/agents/application_writer_agent.py`, `cover_letter_agent.py`, `jd_analyzer.py`, `match_scorer.py`, `resume_analyzer.py`, `skill_gap_agent.py`
- `backend/app/api/orchestrator.py`, `backend/app/config.py`
- `backend/app/schemas/application_writer.py`, `cover_letter.py`, `orchestrator.py`
- `backend/app/services/llm_service.py`, `orchestrator_service.py`, `pdf_service.py`
- `backend/app/utils/__init__.py`, `backend/tests/test_api_contracts.py`
- `frontend/app/globals.css`, `frontend/app/layout.tsx`, `frontend/app/page.tsx`
- `frontend/components/ApplicationTracker.tsx`, `frontend/components/WelcomeIntro.tsx`
- `frontend/lib/api.ts`, `frontend/lib/types.ts`, `frontend/package.json`, `frontend/package-lock.json`

**Untracked files/directories:**

- `backend/app/agents/writer_grounding.py`, `backend/app/services/evaluation_report.py`
- `backend/prototypes/` (including `task17_constrained_composition.py`)
- `backend/run_controlled_groq_evaluation.py`
- Focused backend tests: `test_analysis_on_demand.py`, `test_controlled_groq_runner_task13.py`, `test_evidence_constrained_writing_task10.py`, `test_fact_first_writing_task14.py`, `test_generated_content_quality.py`, `test_groq_evaluation_task06.py`, `test_grounded_writing_task03.py`, `test_grounding_diagnostics_task05.py`, `test_precise_claim_grounding_task08.py`, `test_task17_constrained_composition.py`
- `frontend/AGENTS.md`, `frontend/components.json`
- `frontend/components/CallChip.tsx`, `MockAuthActions.tsx`, `WorkspaceNavigation.tsx`, `WritingEditor.tsx`
- `frontend/components/control-ui/`, `react-bits/`, `spectrumui/`, `theme/`, `ui/`
- `frontend/lib/utils.ts`

**Recent relevant commits (newest first):**

- `7f8528c` Harden InternAI pipeline and frontend dependencies
- `d391833` Improve welcome intro visibility 2
- `7241b29` Improve welcome intro visibility
- `f719f44` Remove accidental zip folder
- `cf38ed0` Upgraded animations.
- `51ee0bb` Fix CORS for Vercel production deployment
- `7821bd8` Fix CORS for deployed frontend
- `186d2ba` Deployment.

**Configuration:** `backend/.env.example` and `frontend/.env.example` are templates. Do not inspect/share `.env` values. `NEXT_PUBLIC_API_URL` selects the frontend API target; backend configuration includes provider/model/retry and database settings. Local evaluation output is gitignored; preserve existing records.

## 8. Prioritized Codex backlog

### P0 — Correct runtime and request behavior

1. **Reproduce the `studioTab` error against the served build.** Restart the current frontend process, hard reload, capture the browser stack/source map, and confirm the loaded JS corresponds to this checkout. Current source declares `studioTab`; do not patch blindly.
2. **Verify primary CTA presence and disabled reasons.** Inspect Analyze, Cover Letter and Answer at valid/invalid input states, desktop/mobile and reduced motion. Confirm DOM semantics, computed visibility, pointer events and real form submission. Current primary control is Morph Button; Specular source is unused.
3. **Keep analysis writer-free.** Retain/extend the mocked orchestrator test to assert both writer agents and LLM service are untouched. Do not call live Groq.
4. **Make retry expectations explicit.** For strict one-provider-attempt behavior, set `GROQ_MAX_RETRIES=0` in the relevant environment and confirm no second call on failure. Avoid changing defaults without confirming product requirements.

### P1 — Remove state/UI ambiguity

1. Remove or consolidate the obsolete legacy AI Studio tabs/editor block below the new card landing section, after browser reproduction confirms it is stale duplicate UI.
2. Verify browser Back/Forward and hash restoration across Home, Analyze, Results, Studio subflows and Tracker; confirm state and prepared evidence stay associated with the right resume/JD/question.
3. Run mocked end-to-end frontend journeys and ensure exactly one selected writer endpoint is called only after explicit Generate/Regenerate.
4. Verify cancellation and stale request protections after navigating away or editing resume/JD.
5. Verify tracker empty/error/loading states do not misrepresent backend failures as no records.

### P2 — Visual/accessibility polish

1. Check Question Card, Prepared Context and request overlay in both themes and at phone widths; retain contrast and keyboard focus.
2. Audit Stepper semantics: either expose it as a clearly noninteractive progress indicator or make it a proper accessible navigation component without allowing required stages to be skipped.
3. Test Gooey Nav fallback with WebGL2 unavailable, reduced motion and touch navigation; ensure it does not render continuously while idle.
4. Review unused package/icon dependencies through source import searches before proposing cleanup.
5. Capture current screenshots for Home, Analyze, Results, Studio customization, generation overlay, draft and Tracker in both themes/mobile.

## 9. Recommended first Codex task

**Reproduce and close the primary-action/runtime regression without touching backend logic:** run the current frontend locally, confirm the served build/version, inspect the exact `studioTab` stack and CTA states, then remove the obsolete tabbed Studio JSX if confirmed redundant. Add a focused regression test for the active AI Studio view and primary Generate visibility/disabled behavior. Keep existing worktree changes intact and do not make live Groq calls.

## 10. Handover cautions

- Treat all modified and untracked files listed above as user work. Inspect diffs before editing and preserve them.
- Do not equate a successful build with browser-level workflow verification.
- Do not infer live evaluation token totals or Task 11 completion where persisted records are unavailable.
- Do not expose `.env`, evaluation fixtures containing real data, SQLite contents, resumes, or generated writing outside explicitly synthetic test data.
- Do not change prompts, validators, matching, scoring, roadmap or API contracts while addressing a frontend rendering issue.
