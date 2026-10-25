"use client";

import { useRef } from "react";
import { Button as SpectrumButton } from "@/components/ui/button";
import { Button as ControlButton } from "@/components/control-ui/button";

export default function MockAuthActions() {
  const dialogRef = useRef<HTMLDialogElement>(null);

  const showComingSoon = () => dialogRef.current?.showModal();

  return (
    <>
      <div className="mock-auth-actions">
        <ControlButton type="button" variant="quiet" size="sm" className="auth-button auth-button-secondary" onClick={showComingSoon}>
          Log In
        </ControlButton>
        <SpectrumButton type="button" variant="default" size="sm" className="auth-button auth-button-primary" onClick={showComingSoon}>
          Sign Up
        </SpectrumButton>
      </div>

      <dialog ref={dialogRef} className="coming-soon-dialog" aria-labelledby="coming-soon-title">
        <div className="coming-soon-content">
          <span className="coming-soon-mark" aria-hidden="true">IA</span>
          <p className="eyebrow">InternAI accounts</p>
          <h2 id="coming-soon-title">Coming soon.</h2>
          <p>Account access is on the way. You can keep exploring the workspace in the meantime.</p>
          <form method="dialog">
            <button className="coming-soon-close" type="submit" autoFocus>Got it</button>
          </form>
        </div>
      </dialog>
    </>
  );
}
