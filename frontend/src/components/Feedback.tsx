// Error and warning messages shown under the editor.

import type { KidError } from "../types";

export function withCode(text: string) {
  // Render `code` spans in the kid-friendly messages.
  return text.split(/(`[^`]+`)/g).map((part, i) =>
    part.startsWith("`") && part.endsWith("`") ? <code key={i}>{part.slice(1, -1)}</code> : <span key={i}>{part}</span>,
  );
}

export function ErrorCard({ error }: { error: KidError }) {
  return (
    <div className="feedback error" role="alert">
      <div className="feedback-title">
        🐞 {error.line ? `Problem on line ${error.line}` : "Problem"}
      </div>
      <p className="kid-message">
        {error.kid_message.split("\n").map((line, i) => (
          <span key={i} className="kid-line">{withCode(line)}</span>
        ))}
      </p>
      <details>
        <summary>What Python said</summary>
        <pre className="python-message">{error.python_message}</pre>
      </details>
    </div>
  );
}

export function Warnings({ warnings }: { warnings: { line: number; message: string }[] }) {
  if (warnings.length === 0) return null;
  return (
    <div className="feedback warning">
      {warnings.map((w, i) => (
        <p key={i}>
          <b>Line {w.line}:</b> {withCode(w.message)}
        </p>
      ))}
    </div>
  );
}

export function Notice({ children }: { children: React.ReactNode }) {
  return <div className="feedback notice" role="status">{children}</div>;
}
