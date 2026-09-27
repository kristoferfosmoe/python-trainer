// Lesson blocks: text, runnable examples, step-by-step visualizations and quizzes.
// (Challenge blocks use ChallengeWorkspace.)

import { useEffect, useState } from "react";
import { runRequest } from "../content";
import { markdown } from "../markdown";
import { runner, useRunnerStatus } from "../sim/instance";
import * as storage from "../storage";
import type { CodeBlock, KidError, QuizBlock, TextBlock, Trace } from "../types";
import { runFailure } from "./ChallengeWorkspace";
import { CodeEditor } from "./CodeEditor";
import { CodeView } from "./CodeView";
import { ErrorCard, withCode } from "./Feedback";
import { endMessage } from "./Panels";
import { StepVisualizer } from "./StepVisualizer";

export function TextBlockView({ block }: { block: TextBlock }) {
  return <div className="markdown" dangerouslySetInnerHTML={markdown(block.markdown)} />;
}

// --- Examples and visualizations ------------------------------------------------------

interface CodeBlockProps {
  block: CodeBlock;
  lessonId: string;
}

/**
 * Example blocks open in the editor, with Run and Step-through buttons.
 * Visualize blocks open in step mode; students can still switch to editing.
 */
export function CodeBlockView({ block, lessonId }: CodeBlockProps) {
  const codeKey = `lesson/${lessonId}/${block.id}`;
  const status = useRunnerStatus();
  const [code, setCode] = useState(() => storage.savedCode(codeKey) ?? block.code);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [tracedCode, setTracedCode] = useState<string | null>(null);
  const [failure, setFailure] = useState<KidError | null>(null);
  const [mode, setMode] = useState<"edit" | "step">(block.type === "visualize" ? "step" : "edit");
  const [busy, setBusy] = useState(false);

  const changeCode = (next: string) => {
    setCode(next);
    storage.saveCode(codeKey, next);
  };

  const run = async (then: "edit" | "step") => {
    if (busy) return;
    setBusy(true);
    setFailure(null);
    try {
      setTrace(await runner.run(runRequest({}, code)));
      setTracedCode(code);
      setMode(then);
    } catch (error) {
      setTrace(null);
      setFailure(runFailure(error));
      setMode("edit");
    } finally {
      setBusy(false);
    }
  };

  // Visualize blocks prepare their steps as soon as Python is ready.
  useEffect(() => {
    if (block.type === "visualize" && !trace && !busy && (status === "ready" || status === "running")) void run("step");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  const fresh = trace !== null && tracedCode === code;
  const stepping = mode === "step" && fresh && trace !== null;
  const changed = code !== block.code;

  return (
    <div className="card code-block-card">
      {stepping ? (
        <StepVisualizer
          code={tracedCode!}
          trace={trace!}
          actions={<button className="secondary" onClick={() => setMode("edit")}>✏️ Change the code</button>}
        />
      ) : mode === "step" && !failure ? (
        <p className="empty padded">⏳ Getting the steps ready…</p>
      ) : (
        <>
          <div className="toolbar">
            <button className="primary run" onClick={() => run("edit")} disabled={busy || status === "broken"}>
              {status === "loading" ? "⏳ Starting…" : "▶ Run"}
            </button>
            <button className="secondary" onClick={() => run("step")} disabled={busy || status === "broken"}>
              👣 Step through
            </button>
            <span className="spacer" />
            {changed && (
              <button className="secondary" onClick={() => changeCode(block.code)} title="Put the original code back">
                ↺ Reset
              </button>
            )}
          </div>
          <CodeEditor
            value={code}
            onChange={changeCode}
            onRun={() => run("edit")}
            playLine={null}
            errorLine={fresh && trace?.end.error ? trace.end.error.line : null}
            warningLines={[]}
            compact
          />
          {failure && <ErrorCard error={failure} />}
          {fresh && trace && <Output trace={trace} />}
        </>
      )}
    </div>
  );
}

function Output({ trace }: { trace: Trace }) {
  return (
    <div className="example-output">
      <div className="output-label">Output</div>
      {trace.prints.length > 0 ? (
        <pre className="output">{trace.prints.map((p) => p.text).join("\n")}</pre>
      ) : (
        <p className="empty">Nothing was printed.</p>
      )}
      {trace.end.error ? <ErrorCard error={trace.end.error} /> : trace.end.reason !== "finished" && <p className="console-note">{endMessage(trace)}</p>}
    </div>
  );
}

// --- Quizzes -----------------------------------------------------------------------------

interface QuizProps {
  block: QuizBlock;
  done: boolean;
  onCorrect: () => void;
}

export function QuizBlockView({ block, done, onCorrect }: QuizProps) {
  const [solved, setSolved] = useState(done);
  const [wrong, setWrong] = useState<number[]>([]);
  const [last, setLast] = useState<number | null>(null);
  const output = block.check === "output";

  const choose = (index: number) => {
    if (solved) return;
    setLast(index);
    if (index === block.answer) {
      setSolved(true);
      onCorrect();
    } else if (!wrong.includes(index)) {
      setWrong([...wrong, index]);
    }
  };

  const lastChoice = last !== null ? block.choices[last] : null;
  const why = lastChoice && typeof lastChoice === "object" ? lastChoice.why : undefined;

  return (
    <div className="card quiz">
      <div className="quiz-label">❓ Quick check</div>
      <div className="markdown quiz-question" dangerouslySetInnerHTML={markdown(block.question)} />
      {block.code && <CodeView code={block.code} label="Quiz code" />}
      <div className={`choices ${output ? "output-choices" : ""}`} role="group" aria-label="Answers">
        {block.choices.map((choice, index) => {
          const text = typeof choice === "string" ? choice : choice.text;
          const state = solved && index === block.answer ? "right" : wrong.includes(index) ? "wrong" : "";
          return (
            <button
              key={index}
              className={`choice ${state}`}
              onClick={() => choose(index)}
              disabled={solved && index !== block.answer}
              aria-pressed={state === "right"}
            >
              {output ? <pre>{text}</pre> : <span>{withCode(text)}</span>}
            </button>
          );
        })}
      </div>
      {solved ? (
        <div className="quiz-feedback right" role="status">
          <b>✔ Correct!</b>
          {block.explain && <div className="markdown" dangerouslySetInnerHTML={markdown(block.explain)} />}
        </div>
      ) : (
        last !== null && (
          <div className="quiz-feedback wrong" role="status">
            <b>Not quite.</b> {why ? withCode(why) : "Try again!"}
          </div>
        )
      )}
    </div>
  );
}
