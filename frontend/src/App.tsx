import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { EditorView } from "@codemirror/view";
import { challenges, robot, runRequest, startFor, worldFor } from "./content";
import { eventsBetween, lineAt } from "./playback";
import { RunTimeout, SimRunner, type RunnerStatus } from "./sim/runner";
import { beep } from "./sound";
import * as storage from "./storage";
import type { Challenge, KidError, Trace } from "./types";
import { ChallengeCard } from "./components/ChallengeCard";
import { CodeEditor } from "./components/CodeEditor";
import { ErrorCard, Notice, Warnings } from "./components/Feedback";
import { MatView } from "./components/MatView";
import { ConsolePanel, RobotPanel, VariablesPanel } from "./components/Panels";
import { PlaybackBar } from "./components/PlaybackBar";

type Tab = "console" | "variables" | "robot";

const runner = new SimRunner();

function initialChallenge(): Challenge {
  const id = storage.lastChallenge();
  return challenges.find((c) => c.id === id) ?? challenges[0];
}

export default function App() {
  const [challenge, setChallenge] = useState<Challenge>(initialChallenge);
  const [code, setCode] = useState(() => storage.savedCode(challenge.id) ?? challenge.starter);
  const [status, setStatus] = useState<RunnerStatus>(runner.status);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [tracedCode, setTracedCode] = useState("");
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [sound, setSound] = useState(storage.soundOn);
  const [tab, setTab] = useState<Tab>("console");
  const [runError, setRunError] = useState<KidError | null>(null);
  const [solved, setSolved] = useState(storage.solvedChallenges);
  const [copied, setCopied] = useState(false);
  const [runCount, setRunCount] = useState(0);
  const editorRef = useRef<EditorView | null>(null);

  const world = worldFor(challenge);
  const start = useMemo(() => startFor(challenge), [challenge]);
  const end = trace?.end.t ?? 0;
  const finished = trace !== null && time >= end;

  useEffect(() => {
    const unsubscribe = runner.onStatus(setStatus);
    return () => {
      unsubscribe();
    };
  }, []);

  // --- Playback clock --------------------------------------------------------------
  const clock = useRef({ time: 0, speed: 1, sound: true });
  clock.current.speed = speed;
  clock.current.sound = sound;

  useEffect(() => {
    if (!playing || !trace) return;
    let frame = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const before = clock.current.time;
      const after = Math.min(trace.end.t, before + (now - last) * clock.current.speed);
      last = now;
      if (clock.current.sound) {
        for (const event of eventsBetween(trace, before, after)) {
          if (event.type === "beep") beep(event.frequency ?? 500, (event.duration ?? 100) / clock.current.speed);
        }
      }
      clock.current.time = after;
      setTime(after);
      if (after >= trace.end.t) {
        setPlaying(false);
        return;
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, trace]);

  const seek = (t: number) => {
    clock.current.time = t;
    setTime(t);
  };

  // When a run finishes playing, remember solved challenges.
  useEffect(() => {
    if (finished && trace && trace.goals.length > 0 && trace.goals.every((g) => g.passed)) {
      storage.markSolved(challenge.id);
      setSolved(storage.solvedChallenges());
    }
  }, [finished, trace, challenge.id]);

  // --- Actions -----------------------------------------------------------------------
  const run = useCallback(async () => {
    if (status === "running") return;
    setRunError(null);
    setPlaying(false);
    storage.saveCode(challenge.id, code);
    try {
      const result = await runner.run(runRequest(challenge, code));
      setTrace(result);
      setTracedCode(code);
      setRunCount((n) => n + 1);
      seek(0);
      setPlaying(true);
      if (result.end.reason === "error" && result.end.t < 50) setTab("console");
    } catch (error) {
      setTrace(null);
      setRunCount((n) => n + 1);
      setRunError({
        type: "Timeout",
        line: null,
        python_message: String(error),
        kid_message:
          error instanceof RunTimeout
            ? "Your program took too long for the simulator to finish. Is there a loop that never ends and never waits? Try adding `wait(10)` inside it."
            : "The simulator had a problem running this program. Try again, or reload the page.",
      });
    }
  }, [status, challenge, code]);

  const pickChallenge = (next: Challenge) => {
    storage.saveCode(challenge.id, code);
    storage.saveLastChallenge(next.id);
    setChallenge(next);
    setCode(storage.savedCode(next.id) ?? next.starter);
    setTrace(null);
    setRunError(null);
    setPlaying(false);
    seek(0);
  };

  const resetCode = () => {
    if (code !== challenge.starter && !window.confirm("Start over with the starter code? Your changes will be lost.")) return;
    setCode(challenge.starter);
    storage.saveCode(challenge.id, challenge.starter);
  };

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("Copy your code:", code);
    }
  };

  // Test hook: lets browser tests type into the editor quickly.
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    (window as unknown as { __trainer: object }).__trainer = {
      setCode: (text: string) => setCode(text),
      solution: () => challenge.solution ?? "",
      skipToEnd: () => {
        setPlaying(false);
        seek(trace?.end.t ?? 0);
      },
    };
  }, [challenge, trace]);

  // --- What to show --------------------------------------------------------------------
  const codeMatchesTrace = trace !== null && tracedCode === code;
  const error = runError ?? (trace && trace.end.error && time >= trace.end.t ? trace.end.error : null);
  const playLine = codeMatchesTrace && trace && !finished ? lineAt(trace, time) : null;
  const errorLine = codeMatchesTrace && error ? error.line : null;
  const warningLines = useMemo(
    () => (codeMatchesTrace && trace ? trace.warnings.map((w) => w.line) : []),
    [codeMatchesTrace, trace],
  );
  const goals = finished && trace && trace.goals.length > 0 ? trace.goals : null;
  const allPassed = goals !== null && goals.every((g) => g.passed);

  return (
    <div className="app" data-runs={runCount}>
      <header className="topbar">
        <h1>
          <span aria-hidden>🤖</span> Python Trainer
        </h1>
        <span className={`status status-${status}`} role="status">
          {status === "loading" && "Starting Python…"}
          {status === "ready" && "Python ready"}
          {status === "running" && "Running…"}
          {status === "broken" && "Python didn't start. Reload the page."}
        </span>
      </header>

      <nav className="challenges" aria-label="Challenges">
        {challenges.map((c, i) => (
          <button
            key={c.id}
            className={`chip ${c.id === challenge.id ? "active" : ""}`}
            onClick={() => pickChallenge(c)}
            aria-current={c.id === challenge.id ? "page" : undefined}
          >
            <span className="chip-num">{i + 1}</span> {c.title}
            {solved.has(c.id) && <span className="chip-done" aria-label="solved">✔</span>}
          </button>
        ))}
      </nav>

      <main className="workspace">
        <div className="left">
          <ChallengeCard key={challenge.id} challenge={challenge} world={world} goals={goals} />
          {allPassed && <Notice>🎉 <b>Challenge complete!</b> Nice work. Try the next one, or make your code even better.</Notice>}
          <section className="card code-card" aria-label="Your code">
            <div className="toolbar">
              <button className="primary run" onClick={run} disabled={status === "running" || status === "broken"}>
                {status === "loading" ? "⏳ Starting…" : status === "running" ? "⏳ Running…" : "▶ Run"}
              </button>
              <span className="shortcut">Ctrl + Enter</span>
              <span className="spacer" />
              <button className="secondary" onClick={copyCode} title="Copy your code to paste into Pybricks for your real robot">
                {copied ? "Copied!" : "📋 Copy for Pybricks"}
              </button>
              <button className="secondary" onClick={resetCode}>↺ Start over</button>
            </div>
            {error && <ErrorCard error={error} />}
            {codeMatchesTrace && trace && <Warnings warnings={trace.warnings} />}
            <CodeEditor
              value={code}
              onChange={setCode}
              onRun={run}
              playLine={playLine}
              errorLine={errorLine}
              warningLines={warningLines}
              editorRef={editorRef}
            />
          </section>
        </div>

        <div className="right">
          <section className="card mat-card" aria-label="Robot mat">
            <MatView world={world} robot={robot} start={start} trace={trace} time={time} />
            {trace && (
              <PlaybackBar
                time={time}
                end={end}
                playing={playing}
                speed={speed}
                sound={sound}
                onPlayPause={() => {
                  if (finished) seek(0);
                  setPlaying(!playing || finished);
                }}
                onSeek={(t) => {
                  setPlaying(false);
                  seek(t);
                }}
                onSpeed={setSpeed}
                onSound={(on) => {
                  setSound(on);
                  storage.saveSoundOn(on);
                }}
              />
            )}
          </section>
          <section className="card panels">
            <div className="tabs" role="tablist">
              {(["console", "variables", "robot"] as Tab[]).map((name) => (
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
      </main>
    </div>
  );
}
