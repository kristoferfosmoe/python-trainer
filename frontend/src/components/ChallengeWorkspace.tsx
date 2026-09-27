// Editor + mat + console for one challenge. Used by the playground and by
// challenge pages in lessons.

import { useCallback, useEffect, useMemo, useState } from "react";
import { robot as currentRobot, runRequest, startFor, worldFor } from "../content";
import { lineAt } from "../playback";
import { runner, useRunnerStatus } from "../sim/instance";
import { RunTimeout } from "../sim/runner";
import * as session from "../session";
import type { Challenge, KidError, Trace } from "../types";
import { usePlayback } from "../usePlayback";
import { ChallengeCard } from "./ChallengeCard";
import { CodeEditor } from "./CodeEditor";
import { ErrorCard, Notice, Warnings } from "./Feedback";
import { MatView } from "./MatView";
import { ConsolePanel, RobotPanel, VariablesPanel } from "./Panels";
import { PlaybackBar } from "./PlaybackBar";
import { RunOnRobot } from "./RunOnRobot";

type Tab = "console" | "variables" | "robot";

export const TIMEOUT_ERROR: KidError = {
  type: "Timeout",
  line: null,
  python_message: "The program took too long to simulate.",
  kid_message:
    "Your program took too long for the simulator to finish. Is there a loop that never ends and never waits? Try adding `wait(10)` inside it.",
};

export function runFailure(error: unknown): KidError {
  if (error instanceof RunTimeout) return TIMEOUT_ERROR;
  return {
    type: "SimulatorError",
    line: null,
    python_message: String(error),
    kid_message: "The simulator had a problem running this program. Try again, or reload the page.",
  };
}

interface Props {
  challenge: Challenge;
  /** Where the student's code is saved: lesson/<lesson>/<block> or playground/<id>. */
  codeKey: string;
  /** For challenges inside lessons, recorded with each attempt. */
  lessonId?: string;
  /** Lesson text shown above the challenge's own instructions. */
  intro?: string;
  onSolved?: () => void;
  /** Shown in the "Challenge complete!" banner, e.g. a Continue button. */
  solvedAction?: React.ReactNode;
}

export function ChallengeWorkspace({ challenge, codeKey, lessonId, intro, onSolved, solvedAction }: Props) {
  const status = useRunnerStatus();
  const robot = currentRobot();
  const [code, setCode] = useState(() => session.draft(codeKey) ?? challenge.starter);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [tracedCode, setTracedCode] = useState("");
  const [runError, setRunError] = useState<KidError | null>(null);
  const [tab, setTab] = useState<Tab>("console");
  const [onRobot, setOnRobot] = useState(false);
  const [runCount, setRunCount] = useState(0);
  const playback = usePlayback(trace);

  const hasWorld = Boolean(challenge.world);
  const world = worldFor(challenge);
  const start = useMemo(() => startFor(challenge), [challenge]);
  const { time, finished } = playback;

  const changeCode = (next: string) => {
    setCode(next);
    session.saveDraft(codeKey, next);
  };

  const run = useCallback(async () => {
    if (status === "running") return;
    setRunError(null);
    playback.pause();
    try {
      const result = await runner.run(runRequest(challenge, code));
      setTrace(result);
      setTracedCode(code);
      if (result.goals.length > 0) {
        session.recordAttempt({
          key: codeKey,
          code,
          passed: result.goals.every((g) => g.passed),
          goals: result.goals.map((g) => ({ id: g.id, passed: g.passed })),
          sim_version: result.sim_version,
          lesson_id: lessonId,
          block_id: lessonId ? challenge.id : undefined,
        });
      }
      if (hasWorld) playback.restart();
      else playback.seek(result.end.t);
    } catch (error) {
      setTrace(null);
      setRunError(runFailure(error));
    }
    setRunCount((n) => n + 1);
  }, [status, challenge, code, codeKey, lessonId, hasWorld, playback]);

  const goals = finished && trace && trace.goals.length > 0 ? trace.goals : null;
  const allPassed = goals !== null && goals.every((g) => g.passed);

  useEffect(() => {
    if (allPassed) onSolved?.();
    // Only when a run's result is revealed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allPassed, trace]);

  const resetCode = () => {
    if (code !== challenge.starter && !window.confirm("Start over with the starter code? Your changes will be lost.")) return;
    changeCode(challenge.starter);
  };

  // Test hook: lets browser tests type into the editor quickly.
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    // The hooks come from the latest render, so tests can wait for code() and
    // runs() to catch up before pressing Run or skipping to the end.
    const hooks = {
      setCode: changeCode,
      key: () => codeKey,
      code: () => code,
      runs: () => runCount,
      solution: () => challenge.solution ?? "",
      skipToEnd: playback.skipToEnd,
    };
    (window as unknown as { __trainer: object }).__trainer = hooks;
    return () => {
      const w = window as unknown as { __trainer?: object };
      if (w.__trainer === hooks) delete w.__trainer;
    };
  });

  const codeMatchesTrace = trace !== null && tracedCode === code;
  const error = runError ?? (trace && trace.end.error && time >= trace.end.t ? trace.end.error : null);
  const playLine = codeMatchesTrace && trace && !finished ? lineAt(trace, time) : null;
  const errorLine = codeMatchesTrace && error ? error.line : null;
  const warningLines = useMemo(
    () => (codeMatchesTrace && trace ? trace.warnings.map((w) => w.line) : []),
    [codeMatchesTrace, trace],
  );

  return (
    <div className="workspace" data-runs={runCount}>
      {onRobot && <RunOnRobot code={code} onClose={() => setOnRobot(false)} />}
      <div className="left">
        <ChallengeCard challenge={challenge} world={world} goals={goals} intro={intro} />
        {allPassed && (
          <Notice>
            <span>🎉 <b>Challenge complete!</b> Nice work.</span>
            {solvedAction}
          </Notice>
        )}
        <section className="card code-card" aria-label="Your code">
          <div className="toolbar">
            <button className="primary run" onClick={run} disabled={status === "running" || status === "broken"}>
              {status === "loading" ? "⏳ Starting…" : status === "running" ? "⏳ Running…" : "▶ Run"}
            </button>
            <span className="shortcut">Ctrl + Enter</span>
            <span className="spacer" />
            {hasWorld && (
              <button className="secondary" onClick={() => setOnRobot(true)} title="Copy your code into Pybricks and run it on a real robot">
                🤖 Run on your robot
              </button>
            )}
            <button className="secondary" onClick={resetCode}>↺ Start over</button>
          </div>
          {error && <ErrorCard error={error} />}
          {codeMatchesTrace && trace && <Warnings warnings={trace.warnings} />}
          <CodeEditor
            value={code}
            onChange={changeCode}
            onRun={run}
            playLine={playLine}
            errorLine={errorLine}
            warningLines={warningLines}
          />
        </section>
      </div>

      <div className="right">
        {hasWorld && (
          <section className="card mat-card" aria-label="Robot mat">
            <MatView world={world} robot={robot} start={start} trace={trace} time={time} />
            {trace && (
              <PlaybackBar
                time={time}
                end={playback.end}
                playing={playback.playing}
                speed={playback.speed}
                sound={playback.sound}
                onPlayPause={playback.playing ? playback.pause : playback.play}
                onSeek={(t) => {
                  playback.pause();
                  playback.seek(t);
                }}
                onSpeed={playback.setSpeed}
                onSound={playback.setSound}
              />
            )}
          </section>
        )}
        <section className={`card panels ${hasWorld ? "" : "tall"}`}>
          <div className="tabs" role="tablist">
            {(["console", "variables", ...(hasWorld ? ["robot"] : [])] as Tab[]).map((name) => (
              <button key={name} role="tab" aria-selected={tab === name} className={tab === name ? "active" : ""} onClick={() => setTab(name)}>
                {name === "console" ? "Console" : name === "variables" ? "Variables" : "Robot & ports"}
              </button>
            ))}
          </div>
          <div className="tab-body" role="tabpanel">
            {tab === "console" && <ConsolePanel trace={trace} time={time} />}
            {tab === "variables" && <VariablesPanel trace={trace} time={time} />}
            {tab === "robot" && <RobotPanel robot={robot} trace={trace} time={time} />}
          </div>
        </section>
      </div>
    </div>
  );
}
