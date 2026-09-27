// Plays a program one line at a time: the line about to run, how many times
// each line has run, what if/while/for decide, the variables and the output.
// Students watch; they don't build anything here.

import { useEffect, useMemo, useState } from "react";
import { varsAt } from "../playback";
import { stepView } from "../stepping";
import type { Trace } from "../types";
import { CodeView } from "./CodeView";
import { ErrorCard } from "./Feedback";

const SPEEDS = [
  { label: "Slow", ms: 1400 },
  { label: "Normal", ms: 800 },
  { label: "Fast", ms: 350 },
];

interface Props {
  code: string;
  trace: Trace;
  /** Extra buttons at the end of the control row. */
  actions?: React.ReactNode;
}

export function StepVisualizer({ code, trace, actions }: Props) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(SPEEDS[1].ms);
  const last = trace.steps.length; // the "done" step

  useEffect(() => {
    setIndex(0);
    setPlaying(false);
  }, [trace]);

  useEffect(() => {
    if (!playing) return;
    if (index >= last) {
      setPlaying(false);
      return;
    }
    const timer = setTimeout(() => setIndex((i) => Math.min(last, i + 1)), speed);
    return () => clearTimeout(timer);
  }, [playing, index, last, speed]);

  const view = useMemo(() => stepView(trace, index), [trace, index]);
  const vars = varsAt(trace, view.time);
  const prints = trace.prints.slice(0, view.printCount);
  const error = view.done ? trace.end.error : undefined;

  return (
    <div className="stepper">
      <div className="stepper-controls" aria-label="Step controls">
        <button className="icon" onClick={() => { setPlaying(false); setIndex(0); }} title="Back to the start" aria-label="Back to the start">⏮</button>
        <button className="icon" onClick={() => { setPlaying(false); setIndex((i) => Math.max(0, i - 1)); }} disabled={index === 0} title="Step back" aria-label="Step back">◀</button>
        <button className="primary" onClick={() => (index >= last ? (setIndex(0), setPlaying(true)) : setPlaying(!playing))}>
          {playing ? "⏸ Pause" : index >= last ? "↺ Play again" : index === 0 ? "▶ Play" : "▶ Keep going"}
        </button>
        <button className="icon" onClick={() => { setPlaying(false); setIndex((i) => Math.min(last, i + 1)); }} disabled={index >= last} title="Step forward" aria-label="Step forward">▶</button>
        <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="Speed">
          {SPEEDS.map((s) => <option key={s.ms} value={s.ms}>{s.label}</option>)}
        </select>
        <span className="step-count" aria-live="polite">
          {view.done ? (error ? "Stopped by an error" : "✔ Finished") : `Step ${index + 1} of ${last}`}
        </span>
        {actions}
      </div>
      <div className="stepper-body">
        <div className="stepper-code">
          <CodeView code={code} annotations={view.annotations} counts label="Code being stepped through" />
          {!view.done && view.line !== null && <p className="stepper-hint">The highlighted line runs next.</p>}
        </div>
        <div className="stepper-side">
          <div className="side-box">
            <h4>Variables</h4>
            {vars.length === 0 ? (
              <p className="empty">None yet</p>
            ) : (
              <table className="vars compact">
                <tbody>
                  {vars.map(([name, value, scope]) => (
                    <tr key={`${scope}:${name}`}>
                      <td><code>{name}</code></td>
                      <td><code>{value}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="side-box">
            <h4>Output</h4>
            {prints.length === 0 ? (
              <p className="empty">Nothing printed yet</p>
            ) : (
              <pre className="output">{prints.map((p) => p.text).join("\n")}</pre>
            )}
          </div>
        </div>
      </div>
      {error && <ErrorCard error={error} />}
      {trace.steps_truncated && view.done && (
        <p className="empty">This program has too many steps to show them all; only the first 5000 are shown.</p>
      )}
    </div>
  );
}
