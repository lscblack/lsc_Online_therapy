import { useEffect, useId, useRef, type ReactNode } from "react";

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

/** Minimal accessible modal: labelled dialog, focus trapped, Esc closes, focus restored on close. */
export default function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    const first = ref.current?.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus();
    return () => prev?.focus?.();
  }, []);
  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") { e.stopPropagation(); onClose(); return; }
    if (e.key !== "Tab") return;
    const els = Array.from(ref.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    if (els.length === 0) return;
    const a = document.activeElement;
    if (e.shiftKey && a === els[0]) { e.preventDefault(); els[els.length - 1].focus(); }
    else if (!e.shiftKey && a === els[els.length - 1]) { e.preventDefault(); els[0].focus(); }
  }
  return (
    <div className="modal-backdrop" onKeyDown={onKeyDown}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby={titleId} ref={ref}>
        <h3 id={titleId}>{title}</h3>
        {children}
      </div>
    </div>
  );
}
