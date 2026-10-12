import { Fragment, type ReactNode } from "react";

/** Minimal, XSS-safe markdown renderer for chat answers: **bold**, bullet lists (* / - / •) and
 *  paragraphs. Inline [S1]/[S2] citation markers are stripped (sources show as chips below).
 *  Unformatted text is emitted as plain strings (no wrapper spans) to keep the DOM clean. */

function inline(text: string): ReactNode[] {
  const cleaned = text.replace(/\s*\[S\d+\]/g, "").replace(/ {2,}/g, " ").trim();
  return cleaned.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, i) => {
    const b = /^\*\*([^*]+)\*\*$/.exec(part);
    return b ? <strong key={i}>{b[1]}</strong> : <Fragment key={i}>{part}</Fragment>;
  });
}

const BULLET = /^(\*|-|•)\s+/;

export default function Markdown({ text }: { text: string }) {
  const blocks = text.replace(/\r\n/g, "\n").split(/\n{2,}/);
  return (
    <>
      {blocks.map((block, bi) => {
        const lines = block.split("\n").map((l) => l.trim()).filter(Boolean);
        if (lines.length === 0) return null;
        if (lines.every((l) => BULLET.test(l))) {
          return (
            <ul key={bi} className="md-list">
              {lines.map((l, li) => <li key={li}>{inline(l.replace(BULLET, ""))}</li>)}
            </ul>
          );
        }
        return (
          <p key={bi} className="bubble-text">
            {lines.map((l, li) => (
              <Fragment key={li}>{li > 0 && <br />}{inline(l.replace(BULLET, "• "))}</Fragment>
            ))}
          </p>
        );
      })}
    </>
  );
}
