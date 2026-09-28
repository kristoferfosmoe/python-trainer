// One Mission Mode challenge: instructions, the attachment plan, the editor,
// the mat with the mission models, and the score. Built from the same pieces
// as the playground's ChallengeWorkspace.

import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError } from "../api";
import { describe } from "../components/ChallengeCard";
import { runFailure } from "../components/ChallengeWorkspace";
import { CodeEditor } from "../components/CodeEditor";
import { ErrorCard, Notice, Warnings, withCode } from "../components/Feedback";
import { MatView } from "../components/MatView";
import { ConsolePanel, RobotPanel, VariablesPanel } from "../components/Panels";
import { PlaybackBar } from "../components/PlaybackBar";
import { RunOnRobot } from "../components/RunOnRobot";
import { markdown } from "../markdown";
import {
  armsAt, fetchMissionChallenge, fieldModels, initialState, missionRequest, modelStatesAt, nextChallengeId,
  runAt, runPlans, scoreAt, starText, tokensAt, unlockedIds,
} from "../missions";
import { formatTime, lineAt } from "../playback";
import { href } from "../router";
import * as session from "../session";
import { useRunnerStatus } from "../sim/instance";
import { runner } from "../sim/instance";
import * as storage from "../storage";
import type { GameSpec, GoalResult, KidError, LadderGame, MissionChallenge, Trace } from "../types";
import { usePlayback } from "../usePlayback";
import { useLadder } from "./MissionsPage";

type Tab = "console" | "variables" | "robot";

export function MissionPage({ challengeId }: { challengeId: string }) {
  const { me, missions } = session.useSession();
  const { games } = useLadder();
  const [data, setData] = useState<{ game: GameSpec; challenge: MissionChallenge } | null>(null);
  const [error, setError] = useState<{ locked: boolean; message: string } | null>(null);

  useEffect(() => {
    let live = true;
    setData(null);
    setError(null);
    fetchMissionChallenge(challengeId, me?.username ?? "guest").then(
      (found) => live && setData(found),
      (e: Error) => live && setError({ locked: e instanceof ApiError && e.status === 403, message: e.message }),
    );
    return () => {
      live = false;
    };
  }, [challengeId, me?.username]);

  const ladder = games?.find((g) => g.challenges.some((c) => c.id === challengeId)) ?? null;
  const stars = (id: string) => missions[id]?.stars ?? 0;
  const locked = error?.locked || (ladder !== null && !unlockedIds(ladder, stars).has(challengeId));

  if (locked) {
    return (
      <div className="card narrow locked-card">
        <h1>🔒 Not unlocked yet</h1>
        <p>Challenges unlock one at a time. Earn at least one ★ on the challenge before this one first.</p>
        <a className="button primary" href={href({ page: "missions" })}>Back to the missions</a>
      </div>
    );
  }
  if (error) return <div className="card narrow">{error.message}</div>;
  if (!data || !games) return <div className="card narrow">Loading the mission…</div>;
  return <MissionWorkspace key={challengeId} game={data.game} challenge={data.challenge} ladder={ladder} />;
}

interface Props {
  game: GameSpec;
  challenge: MissionChallenge;
  ladder: LadderGame | null;
}

function MissionWorkspace({ game, challenge, ladder }: Props) {
  const status = useRunnerStatus();
  const codeKey = `mission/${challenge.id}`;
  const [code, setCode] = useState(() => session.draft(codeKey) ?? challenge.starter);
  const [picks, setPicks] = useState(() => storage.missionPicks(challenge.id));
  const [trace, setTrace] = useState<Trace | null>(null);
  const [tracedCode, setTracedCode] = useState("");
  const [runError, setRunError] = useState<KidError | null>(null);
  const [tab, setTab] = useState<Tab>("console");
  const [onRobot, setOnRobot] = useState(false);
  const [runCount, setRunCount] = useState(0);
  const playback = usePlayback(trace);
  const { time, finished } = playback;

  const plans = useMemo(() => runPlans(game, challenge, picks), [game, challenge, picks]);
  const models = useMemo(() => fieldModels(game, challenge), [game, challenge]);
  const start = plans[0].start;
  const attachmentsById = useMemo(() => new Map(game.attachments.map((a) => [a.id, a])), [game]);

  const changeCode = (next: string) => {
    setCode(next);
    session.saveDraft(codeKey, next);
  };

  const choose = (run: number, port: string, id: string) => {
    const next = plans.map((plan, i) =>
      Object.fromEntries(Object.keys(plan.choose).map((p) => [p, i === run && p === port ? id : plan.attachments[p]])),
    );
    setPicks(next);
    storage.saveMissionPicks(challenge.id, next);
  };

  const run = useCallback(async () => {
    if (status === "running") return;
    setRunError(null);
    playback.pause();
    try {
      const result = await runner.runMission(missionRequest(game, challenge, code, picks));
      setTrace(result);
      setTracedCode(code);
      const stars = result.mission?.stars ?? 0;
      session.recordAttempt({
        key: codeKey,
        code,
        passed: stars >= 1,
        goals: result.goals.map((g) => ({ id: g.id, passed: g.passed })),
        sim_version: result.sim_version,
      });
      session.recordMissionResult(challenge.id, stars, result.mission?.score.total ?? 0);
      playback.restart();
    } catch (error) {
      setTrace(null);
      setRunError(runFailure(error));
    }
    setRunCount((n) => n + 1);
  }, [status, game, challenge, code, codeKey, picks, playback]);

  const resetCode = () => {
    if (code !== challenge.starter && !window.confirm("Start over with the starter code? Your changes will be lost.")) return;
    changeCode(challenge.starter);
  };

  // Test hook: lets browser tests type into the editor and pick attachments quickly.
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    const hooks = {
      setCode: changeCode,
      key: () => codeKey,
      code: () => code,
      runs: () => runCount,
      solution: () => challenge.solution ?? "",
      skipToEnd: playback.skipToEnd,
      choose: (next: Record<string, string>[]) => setPicks(next),
      picks: () => picks,
    };
    (window as unknown as { __trainer: object }).__trainer = hooks;
    return () => {
      const w = window as unknown as { __trainer?: object };
      if (w.__trainer === hooks) delete w.__trainer;
    };
  });

  const mission = trace?.mission;
  const mat = useMemo(() => {
    if (trace && mission) {
      const states = modelStatesAt(trace, time);
      return { models: models.map((spec) => ({ spec, state: states[spec.id] ?? initialState(spec) })), arms: armsAt(trace, time) };
    }
    const arms = Object.values(plans[0].attachments).flatMap((id) => {
      const spec = attachmentsById.get(id);
      return spec ? [{ spec, angle: challenge.runs?.[0]?.rest?.[spec.port] ?? spec.rest_angle ?? 0 }] : [];
    });
    return { models: models.map((spec) => ({ spec, state: initialState(spec) })), arms };
  }, [trace, mission, time, models, plans, attachmentsById, challenge]);

  const goals = finished && trace ? trace.goals : null;
  const stars = finished && mission ? mission.stars : null;
  const best = session.missionResult(challenge.id);
  const next = ladder ? nextChallengeId(ladder, challenge.id) : null;

  const codeMatchesTrace = trace !== null && tracedCode === code;
  const error = runError ?? (trace && trace.end.error && time >= trace.end.t ? trace.end.error : null);
  const playLine = codeMatchesTrace && trace && !finished ? lineAt(trace, time) : null;
  const errorLine = codeMatchesTrace && error ? error.line : null;
  const warningLines = useMemo(
    () => (codeMatchesTrace && trace ? trace.warnings.map((w) => w.line) : []),
    [codeMatchesTrace, trace],
  );
  const tier = game.tiers.find((t) => t.id === challenge.tier);

  return (
    <>
      <nav className="mission-crumbs" aria-label="Breadcrumbs">
        <a href={href({ page: "missions" })}>🏆 {game.title}</a>
        <span aria-hidden>›</span>
        <span>{tier ? `${tier.icon} Tier ${tier.id}: ${tier.title}` : `Tier ${challenge.tier}`}</span>
        {best.stars > 0 && <span className="crumb-stars" aria-label={`Your best: ${best.stars} stars`}>{starText(best.stars)}</span>}
      </nav>
      <div className="workspace mission-workspace" data-runs={runCount}>
        {onRobot && <RunOnRobot code={code} onClose={() => setOnRobot(false)} />}
        <div className="left">
          <MissionCard game={game} challenge={challenge} goals={goals} stars={stars} />
          {stars !== null && stars > 0 && (
            <Notice>
              <span>🎉 <b>{starText(stars)}</b> {stars === 3 ? "Perfect!" : "Challenge complete!"}</span>
              {next && (
                <a className="button primary" href={href({ page: "mission", challengeId: next })}>Next challenge →</a>
              )}
            </Notice>
          )}
          <section className="card attachment-plan" aria-label="Attachments">
            <h3>🔧 Attachments</h3>
            <ol className="plan-runs">
              {plans.map((plan, i) => (
                <li key={i} className="plan-run">
                  <span className="plan-run-name">{plans.length > 1 ? `Run ${i + 1}` : "The robot"}</span>
                  {Object.keys(plan.attachments).length === 0 && <span className="plan-none">no attachments</span>}
                  {Object.entries(plan.attachments).map(([port, id]) => {
                    const spec = attachmentsById.get(id);
                    const options = plan.choose[port];
                    return (
                      <span key={port} className="plan-attachment" title={spec?.summary}>
                        <code>Port.{port}</code>{" "}
                        {options ? (
                          <select aria-label={`Run ${i + 1}, port ${port}`} value={id}
                            onChange={(e) => choose(i, port, e.target.value)}>
                            {options.map((o) => <option key={o} value={o}>{attachmentsById.get(o)?.name ?? o}</option>)}
                          </select>
                        ) : (
                          <b>{spec?.name ?? id}</b>
                        )}
                      </span>
                    );
                  })}
                </li>
              ))}
            </ol>
            {Object.values(plans[0].attachments).length > 0 && (
              <ul className="plan-notes">
                {[...new Set(plans.flatMap((p) => Object.values(p.attachments)))].map((id) => {
                  const spec = attachmentsById.get(id);
                  return spec?.summary ? <li key={id}><b>{spec.name}:</b> {withCode(spec.summary)}</li> : null;
                })}
              </ul>
            )}
          </section>
          <section className="card code-card" aria-label="Your code">
            <div className="toolbar">
              <button className="primary run" onClick={run} disabled={status === "running" || status === "broken"}>
                {status === "loading" ? "⏳ Starting…" : status === "running" ? "⏳ Running…" : "▶ Run"}
              </button>
              <span className="shortcut">Ctrl + Enter</span>
              <span className="spacer" />
              <button className="secondary" onClick={() => setOnRobot(true)} title="Copy your code into Pybricks and run it on a real robot">
                🤖 Run on your robot
              </button>
              <button className="secondary" onClick={resetCode}>↺ Start over</button>
            </div>
            {error && <ErrorCard error={error} />}
            {codeMatchesTrace && trace && <Warnings warnings={trace.warnings} />}
            <CodeEditor value={code} onChange={changeCode} onRun={run} playLine={playLine} errorLine={errorLine}
              warningLines={warningLines} />
          </section>
        </div>

        <div className="right">
          <section className="card mat-card" aria-label="Robot mat">
            <MatView world={game.field} robot={game.robot} start={start} trace={trace} time={time} mission={mat} />
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
          <ScorePanel game={game} challenge={challenge} trace={trace} time={time} finished={finished} runs={plans.length} />
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
              {tab === "robot" && <RobotPanel robot={game.robot} trace={trace} time={time} />}
            </div>
          </section>
        </div>
      </div>
    </>
  );
}

const MISSION_GOAL_TEXT: Record<string, (goal: Record<string, unknown>, game: GameSpec) => string> = {
  mission_done: (goal, game) => {
    const mission = game.missions.find((m) => m.id === goal.mission);
    const title = `${goal.mission}: ${mission?.title ?? ""}`;
    return goal.points ? `Score ${goal.points} points for ${title}` : `Score ${title}`;
  },
  min_score: (goal) => `Score at least ${goal.points} points`,
  model_state: (goal, game) => {
    const model = game.models.find((m) => m.id === goal.model);
    return `${model?.label ?? goal.model}: ${String(goal.state).replace(/_/g, " ")}`;
  },
  model_in_zone: (goal, game) => {
    const model = game.models.find((m) => m.id === goal.model);
    const zone = game.field.zones?.find((z) => z.id === goal.zone);
    return `Get the ${model?.label ?? goal.model} into ${zone?.label ?? goal.zone}`;
  },
};

function previewGoals(game: GameSpec, challenge: MissionChallenge): GoalResult[] {
  const zoneName = (id: unknown) => game.field.zones?.find((z) => z.id === id)?.label ?? String(id);
  const rows = (challenge.goals ?? []).map((goal, i) => ({
    id: `goal-${i}`,
    type: goal.type,
    label: (goal.label as string) ?? (MISSION_GOAL_TEXT[goal.type]?.(goal, game) ?? describe(goal, zoneName)),
    passed: false,
    detail: "",
  }));
  if (challenge.stars) {
    rows.push({ id: "first-star", type: "min_score", label: `Score at least ${challenge.stars[0]} points`, passed: false, detail: "" });
  }
  if ((challenge.seeds?.length ?? 1) > 1) {
    rows.push({ id: "every-time", type: "every_time", label: `Works every time: all ${challenge.seeds!.length} tries`, passed: false, detail: "" });
  }
  return rows;
}

function MissionCard({ game, challenge, goals, stars }: {
  game: GameSpec; challenge: MissionChallenge; goals: GoalResult[] | null; stars: number | null;
}) {
  const [open, setOpen] = useState(true);
  const [hintsShown, setHintsShown] = useState(0);
  const instructions = useMemo(() => markdown(challenge.instructions ?? ""), [challenge.instructions]);
  const rows = goals ?? previewGoals(game, challenge);
  const hints = challenge.hints ?? [];
  const realism = challenge.realism !== undefined && challenge.realism !== false && challenge.realism !== "off";
  const tries = challenge.seeds?.length ?? 1;
  return (
    <section className="card challenge" aria-labelledby="challenge-title">
      <div className="challenge-head">
        <div>
          <h2 id="challenge-title">{challenge.title}</h2>
          {challenge.summary && <p className="summary">{challenge.summary}</p>}
        </div>
        <button className="link" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? "Hide" : "Show"} instructions
        </button>
      </div>
      {realism && (
        <p className="realism" title="Wheels slip, one wheel may be slightly smaller, and sensors are a bit noisy, like a real robot.">
          🌪️ Real-world wobble is <b>on</b>{tries > 1 ? <>, and your program runs <b>{tries} times</b></> : null}.
        </p>
      )}
      {open && <div className="instructions markdown" dangerouslySetInnerHTML={instructions} />}
      <div className="star-targets" aria-label="Stars">
        {challenge.stars ? (
          challenge.stars.map((points, i) => (
            <span key={i} className={stars !== null && stars > i ? "got" : ""}>{starText(i + 1).replace(/☆/g, "")} {points} pts</span>
          ))
        ) : (
          <span className={stars === 3 ? "got" : ""}>★★★ for reaching every goal</span>
        )}
      </div>
      {rows.length > 0 && (
        <ul className="goals" aria-label="Goals">
          {rows.map((goal) => (
            <li key={goal.id} className={goals ? (goal.passed ? "pass" : "fail") : "todo"}>
              <span className="goal-icon" aria-hidden>{goals ? (goal.passed ? "✔" : "✖") : "○"}</span>
              <span>
                {withCode(goal.label)}
                {goals && !goal.passed && goal.detail && <span className="goal-detail"> {goal.detail}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
      {hints.length > 0 && (
        <div className="hints">
          {hints.slice(0, hintsShown).map((hint, i) => (
            <p key={i} className="hint" dangerouslySetInnerHTML={markdown(`💡 ${hint}`)} />
          ))}
          {hintsShown < hints.length && (
            <button className="secondary small" onClick={() => setHintsShown(hintsShown + 1)}>
              {hintsShown === 0 ? "Show a hint" : "Another hint"} ({hints.length - hintsShown} left)
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function ScorePanel({ game, challenge, trace, time, finished, runs }: {
  game: GameSpec; challenge: MissionChallenge; trace: Trace | null; time: number; finished: boolean; runs: number;
}) {
  const mission = trace?.mission;
  const limit = (challenge.time_limit ?? 150) * 1000;
  const tokenStart = mission?.score.token_start ?? game.precision_tokens?.start ?? 6;
  const tokens = trace && mission ? tokensAt(trace, time) : tokenStart;
  const current = trace && mission ? runAt(trace, time) : null;
  const clock = Math.min(time, limit);
  return (
    <section className="card score-panel" aria-label="Score">
      <div className="score-row">
        <div>
          <div className="reading-label">Score</div>
          <div className="score-total">{trace && mission ? scoreAt(trace, time) : 0}</div>
        </div>
        <div>
          <div className="reading-label">Match clock</div>
          <div className="reading">{formatTime(clock)} / {formatTime(limit)}</div>
        </div>
        {runs > 1 && (
          <div>
            <div className="reading-label">Run</div>
            <div className="reading">{current ? `${current} of ${runs}` : trace ? "in Home" : `1 of ${runs}`}</div>
          </div>
        )}
        <div>
          <div className="reading-label">Precision tokens</div>
          <div className="tokens" aria-label={`${tokens} of ${tokenStart} precision tokens`}>
            {Array.from({ length: tokenStart }, (_, i) => (
              <span key={i} className={i < tokens ? "token" : "token lost"} />
            ))}
          </div>
        </div>
      </div>
      {finished && mission && (
        <>
          <table className="score-sheet">
            <tbody>
              {mission.score.missions.map((row) => (
                <tr key={row.id} className={row.points > 0 ? "scored" : ""}>
                  <td>{row.points > 0 ? "✔" : "·"}</td>
                  <td><b>{row.id}</b> {row.title}</td>
                  <td className="points">{row.points}</td>
                </tr>
              ))}
              <tr>
                <td>●</td>
                <td>Precision tokens ({mission.score.tokens} left)</td>
                <td className="points">{mission.score.token_points}</td>
              </tr>
              <tr className="total">
                <td />
                <td>Total</td>
                <td className="points">{mission.score.total}</td>
              </tr>
            </tbody>
          </table>
          {mission.seeds.length > 1 && (
            <p className="seed-results">
              {mission.seeds.map((s, i) => (
                <span key={s.seed} className={s.passed ? "pass" : "fail"}>
                  Try {i + 1}: {s.score} {s.passed ? "✔" : "✖"}
                </span>
              ))}
            </p>
          )}
        </>
      )}
    </section>
  );
}
