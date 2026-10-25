"use client";

import { useEffect, useState } from "react";

type ToastKind = "success" | "error" | "info";
type ToastItem = { id: number; kind: ToastKind; title: string; description?: string };
type ToastOptions = { description?: string; duration?: number };
let nextId = 1;
const EVENT_NAME = "internai:toast";

function publish(kind: ToastKind, title: string, options: ToastOptions = {}) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: { id: nextId++, kind, title, ...options } }));
}

export const toast = {
  success: (title: string, options?: ToastOptions) => publish("success", title, options),
  error: (title: string, options?: ToastOptions) => publish("error", title, options),
  info: (title: string, options?: ToastOptions) => publish("info", title, options),
};

export function Toaster() {
  const [items, setItems] = useState<ToastItem[]>([]);
  useEffect(() => {
    const onToast = (event: Event) => {
      const item = (event as CustomEvent<ToastItem & ToastOptions>).detail;
      setItems((current) => [...current, item]);
      window.setTimeout(() => setItems((current) => current.filter((toastItem) => toastItem.id !== item.id)), item.duration ?? 4200);
    };
    window.addEventListener(EVENT_NAME, onToast);
    return () => window.removeEventListener(EVENT_NAME, onToast);
  }, []);

  return (
    <div className="app-toaster" role="region" aria-label="Notifications" aria-live="polite">
      {items.map((item) => <div key={item.id} className={`app-toast app-toast--${item.kind}`} role={item.kind === "error" ? "alert" : "status"}>
        <strong>{item.title}</strong>{item.description ? <span>{item.description}</span> : null}
        <button type="button" aria-label={`Dismiss ${item.title}`} onClick={() => setItems((current) => current.filter((candidate) => candidate.id !== item.id))}>×</button>
      </div>)}
    </div>
  );
}
