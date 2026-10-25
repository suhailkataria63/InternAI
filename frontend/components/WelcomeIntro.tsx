"use client";

import type { NavigationKey } from "@/components/WorkspaceNavigation";

type WelcomeIntroProps = {
  onNavigate: (view: NavigationKey) => void;
};

export default function WelcomeIntro({ onNavigate }: WelcomeIntroProps) {
  return (
    <main className="landing-page">
      <section className="landing-hero" id="top">
        <div className="landing-hero-copy">
          <span className="landing-eyebrow"><span className="eyebrow-dot" /> YOUR NEXT ROLE, WITH CLARITY</span>
          <h1>Make your next<br /><em>application</em> count.</h1>
          <p>Understand your fit, find the skills to build, and write with confidence. Start with the tool you need today.</p>
          <div className="landing-hero-actions">
            <button className="button-primary" type="button" onClick={() => onNavigate("analyze")}>Analyze my resume <span aria-hidden="true">↗</span></button>
            <a className="hero-text-link" href="#workflows">Explore the tools <span aria-hidden="true">↓</span></a>
          </div>
          <div className="landing-trust"><span className="trust-check">✓</span> Your resume stays yours. Review every result before you use it.</div>
        </div>
        <aside className="preview-card" aria-label="Illustrative resume match preview">
          <div className="preview-card-top"><div><span className="preview-overline">ILLUSTRATIVE PREVIEW</span><h2>Frontend Intern</h2><p>Northstar Studio · Remote</p></div><span className="preview-spark" aria-hidden="true">✳</span></div>
          <div className="preview-match-row"><div className="preview-ring"><strong>82</strong><span>match</span></div><div><strong>Strong alignment</strong><p>Based on the example profile and role</p></div></div>
          <div className="preview-divider" />
          <div className="preview-skills-head"><strong>Skills in this example</strong><span>Illustrative data</span></div>
          <div className="preview-skill-list"><span>React</span><span>TypeScript</span><span>REST APIs</span><span className="preview-missing">Testing basics</span></div>
          <div className="preview-roadmap"><span className="roadmap-icon">↗</span><span><strong>A focused next step</strong><small>Build confidence in the skills you want to grow.</small></span><span className="roadmap-arrow">→</span></div>
          <div className="preview-orbit orbit-one" /><div className="preview-orbit orbit-two" />
        </aside>
      </section>

      <section className="landing-workflows" id="workflows">
        <div className="section-heading"><span className="landing-eyebrow">A CLEARER WAY FORWARD</span><h2>Start where you are.</h2><p>Three focused tools. Pick the one that gets you closer to your next opportunity.</p></div>
        <div className="workflow-card-grid">
          <article className="landing-workflow-card">
            <span className="workflow-icon icon-violet" aria-hidden="true">◉</span><span className="workflow-number">01 / ANALYZE</span>
            <h3>Know your fit.</h3><p>Compare your experience with the role, see your strengths, and get a practical learning roadmap.</p>
            <button type="button" className="workflow-card-link" onClick={() => onNavigate("analyze")}>Analyze resume <span aria-hidden="true">↗</span></button>
          </article>
          <article className="landing-workflow-card">
            <span className="workflow-icon icon-peach" aria-hidden="true">✳</span><span className="workflow-number">02 / WRITE</span>
            <h3>Tell your story.</h3><p>Create a tailored cover letter from your resume and the opportunity you care about.</p>
            <button type="button" className="workflow-card-link" onClick={() => onNavigate("studio")}>Explore AI Studio <span aria-hidden="true">↗</span></button>
          </article>
          <article className="landing-workflow-card">
            <span className="workflow-icon icon-mint" aria-hidden="true">↗</span><span className="workflow-number">03 / ANSWER</span>
            <h3>Answer with intent.</h3><p>Turn a specific application question into a focused answer grounded in your experience.</p>
            <button type="button" className="workflow-card-link" onClick={() => onNavigate("studio")}>Explore AI Studio <span aria-hidden="true">↗</span></button>
          </article>
        </div>
      </section>

      <section className="landing-how" id="how-it-works"><div><span className="landing-eyebrow">SIMPLE BY DESIGN</span><h2>From experience<br />to next step.</h2></div><div className="how-steps"><div><b>01</b><span><strong>Bring your context</strong><small>Upload a PDF or paste your resume, then add the role.</small></span></div><div><b>02</b><span><strong>Get a grounded view</strong><small>See relevant skills and evidence, or create the writing you need.</small></span></div><div><b>03</b><span><strong>Make it yours</strong><small>Edit, copy, and review every result before submitting.</small></span></div></div></section>
      <footer className="landing-footer"><a className="landing-brand" href="#top"><span className="landing-mark" aria-hidden="true">i</span><span>InternAI</span></a><span>Thoughtful tools for your next opportunity.</span><a href="#top">Back to top ↑</a></footer>
    </main>
  );
}
