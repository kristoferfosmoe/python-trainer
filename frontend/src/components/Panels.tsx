// The panels under the mat: console, variables and the robot's hub/sensors.

import { countAtOrBefore, formatTime, frameIndexAt, hubAt, lastIndexAtOrBefore, sensorAt } from "../playback";
import { MAT_COLORS } from "../render/drawMat";
import type { ColorName, RobotSpec, Trace, VarEntry } from "../types";

export function ConsolePanel({ trace, time }: { trace: Trace | null; time: number }) {
  if (!trace) return <p className="empty">Press <b>Run</b> and anything you <code>print()</code> shows up here.</p>;
  const shown = trace.prints.slice(0, countAtOrBefore(trace.prints, time));
  const finished = time >= trace.end.t;
  return (
    <div className="console" role="log" aria-live="polite">
      {shown.length === 0 && !finished && <p className="empty">Nothing printed yet…</p>}
      {shown.map((p, i) => (
        <div className="console-line" key={i}>
          <span className="console-time">{formatTime(p.t)}</span>
          <span className="console-text">{p.text}</span>
        </div>
      ))}
      {finished && trace.prints_truncated && <div className="console-note">(Too much printing! Only the first 1000 lines are shown.)</div>}
      {finished && <div className="console-note">{endMessage(trace)}</div>}
    </div>
  );
}

export function endMessage(trace: Trace): string {
  const seconds = (trace.end.t / 1000).toFixed(1);
  switch (trace.end.reason) {
    case "finished":
      return `✔ Program finished after ${seconds} seconds.`;
    case "time_limit":
      return `⏱ Time's up! The program was still running after ${seconds} seconds.`;
    case "step_limit":
      return "⏱ The program ran over a million lines without stopping. Is there a loop that never ends?";
    case "error":
      return `✖ The program stopped because of an error on line ${trace.end.error?.line ?? "?"}.`;
  }
}

export function VariablesPanel({ trace, time }: { trace: Trace | null; time: number }) {
  if (!trace) return <p className="empty">Your variables and their values show up here while the robot runs.</p>;
  const index = lastIndexAtOrBefore(trace.vars.map((v) => v.t), time);
  const vars: VarEntry[] = index >= 0 ? trace.vars[index].vars : [];
  if (vars.length === 0) return <p className="empty">No variables yet.</p>;
  // Flash values that just changed.
  const before = new Map((index > 0 ? trace.vars[index - 1].vars : []).map(([n, v]) => [n, v]));
  const fresh = index >= 0 && time - trace.vars[index].t < 400;
  return (
    <table className="vars">
      <thead>
        <tr><th>Name</th><th>Value</th></tr>
      </thead>
      <tbody>
        {vars.map(([name, value, scope]) => (
          <tr key={`${scope}:${name}`} className={fresh && before.get(name) !== value ? "changed" : undefined}>
            <td>
              <code>{name}</code>
              {scope === "local" && <span className="badge" title="Only exists inside the function">inside function</span>}
            </td>
            <td><code>{value}</code></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Swatch({ color }: { color: string }) {
  return <span className="swatch" style={{ background: MAT_COLORS[color as ColorName] ?? "transparent" }} />;
}

export function RobotPanel({ robot, trace, time }: { robot: RobotSpec; trace: Trace | null; time: number }) {
  const hub = trace ? hubAt(trace, time) : { light: "off", display: "" };
  const reading = (key: string) => (trace ? sensorAt(trace, key, time) : undefined);
  const gyro = reading("gyro");
  return (
    <div className="robot-panel">
      <div className="hub-row">
        <div className="hub-face" title="The hub's light and display">
          <span className="hub-light" style={{ background: hub.light === "off" ? undefined : MAT_COLORS[hub.light as ColorName] }} />
          <span className="hub-display">{hub.display || " "}</span>
        </div>
        <div>
          <div className="reading-label">Gyro heading</div>
          <div className="reading">{gyro === undefined ? "—" : `${gyro}°`}</div>
        </div>
      </div>
      <table className="ports">
        <thead>
          <tr><th>Port</th><th>What's plugged in</th><th>Reading</th></tr>
        </thead>
        <tbody>
          {Object.entries(robot.ports).map(([port, spec]) => {
            let value: React.ReactNode = "—";
            if (spec.device === "color_sensor") {
              const color = reading(`${port}.color`);
              const reflection = reading(`${port}.reflection`);
              if (color !== undefined) value = <><Swatch color={String(color)} /> {String(color)}, reflection {reflection}</>;
            } else if (spec.device === "ultrasonic_sensor") {
              const d = reading(`${port}.distance`);
              if (d !== undefined) value = `${d} mm`;
            } else if (spec.role === "arm" && trace?.motors[port]) {
              value = `${Math.round(trace.motors[port][frameIndexAt(trace, time)])}°`;
            } else if (spec.role) {
              value = spec.role === "left_wheel" ? "drive (left)" : "drive (right)";
            }
            return (
              <tr key={port}>
                <td><code>Port.{port}</code></td>
                <td>{spec.label}</td>
                <td>{value}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
