// The team's real robot: which port each part uses and the wheel sizes.
// Students' code is changed to match it when they copy it to Pybricks.

import { useState } from "react";
import { PARTS, PORTS, type Direction, type PartKey, type TeamRobot } from "../pybricks";

interface Props {
  robot: TeamRobot | null;
  trainer: TeamRobot;
  editable: boolean;
  onSave: (robot: TeamRobot | null) => Promise<void>;
}

function duplicatePort(robot: TeamRobot): string | null {
  const seen = new Map<string, string>();
  for (const part of PARTS) {
    const port = robot[part.key];
    if (!port) continue;
    if (seen.has(port)) return `The ${part.label.toLowerCase()} and the ${seen.get(port)!.toLowerCase()} can't both use port ${port}.`;
    seen.set(port, part.label);
  }
  return null;
}

export function RobotForm({ robot, trainer, editable, onSave }: Props) {
  const [draft, setDraft] = useState<TeamRobot>(robot ?? trainer);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const change = (update: Partial<TeamRobot>) => {
    setDraft({ ...draft, ...update });
    setMessage(null);
  };

  const save = async (next: TeamRobot | null) => {
    const problem = next && duplicatePort(next);
    if (problem) {
      setMessage({ ok: false, text: problem });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      await onSave(next);
      if (!next) setDraft(trainer);
      setMessage({ ok: true, text: next ? "Saved. Students' code will now fit this robot." : "Back to the Trainer Bot's setup." });
    } catch (error) {
      setMessage({ ok: false, text: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const setPort = (key: PartKey, port: string | null) => {
    setDraft({ ...draft, [key]: port } as TeamRobot);
    setMessage(null);
  };

  const direction = (side: "left" | "right") => (
    <select
      aria-label={`${side === "left" ? "Left" : "Right"} wheel direction`}
      value={draft[`${side}_direction`]}
      disabled={!editable}
      onChange={(e) => change({ [`${side}_direction`]: e.target.value as Direction })}
    >
      <option value="clockwise">Direction.CLOCKWISE</option>
      <option value="counterclockwise">Direction.COUNTERCLOCKWISE</option>
    </select>
  );

  return (
    <form
      className="robot-form"
      onSubmit={(e) => {
        e.preventDefault();
        void save(draft);
      }}
    >
      <table>
        <thead>
          <tr>
            <th>Part</th>
            <th>Port on your robot</th>
            <th>On the Trainer Bot</th>
          </tr>
        </thead>
        <tbody>
          {PARTS.map((part) => (
            <tr key={part.key}>
              <td>
                <label htmlFor={`port-${part.key}`}>{part.label}</label>
              </td>
              <td>
                <select
                  id={`port-${part.key}`}
                  value={draft[part.key] ?? ""}
                  disabled={!editable}
                  onChange={(e) => setPort(part.key, e.target.value || null)}
                >
                  {!part.required && <option value="">Not on our robot</option>}
                  {PORTS.map((port) => (
                    <option key={port} value={port}>Port.{port}</option>
                  ))}
                </select>
                {part.key === "left_wheel" && direction("left")}
                {part.key === "right_wheel" && direction("right")}
              </td>
              <td className="muted">
                {trainer[part.key] ? `Port.${trainer[part.key]}` : "—"}
                {part.key === "left_wheel" && `, ${trainer.left_direction}`}
                {part.key === "right_wheel" && `, ${trainer.right_direction}`}
              </td>
            </tr>
          ))}
          <tr>
            <td><label htmlFor="wheel-diameter">Wheel diameter (mm)</label></td>
            <td>
              <input id="wheel-diameter" type="number" min={20} max={200} step="any" required value={draft.wheel_diameter}
                disabled={!editable} onChange={(e) => change({ wheel_diameter: Number(e.target.value) })} />
            </td>
            <td className="muted">{trainer.wheel_diameter}</td>
          </tr>
          <tr>
            <td><label htmlFor="axle-track">Axle track (mm)</label></td>
            <td>
              <input id="axle-track" type="number" min={40} max={400} step="any" required value={draft.axle_track}
                disabled={!editable} onChange={(e) => change({ axle_track: Number(e.target.value) })} />
            </td>
            <td className="muted">{trainer.axle_track}</td>
          </tr>
        </tbody>
      </table>
      <p className="field-hint">
        Wheel diameter: measure across the tire (standard SPIKE Prime wheels are 56 mm). Axle track: measure from the
        middle of one wheel to the middle of the other. A wheel motor that drives backwards needs the other direction.
      </p>
      {message && <p className={message.ok ? "form-ok" : "form-error"} role={message.ok ? "status" : "alert"}>{message.text}</p>}
      {editable && (
        <div className="row">
          <button className="primary" disabled={busy}>{busy ? "Saving…" : "Save robot"}</button>
          {robot && (
            <button type="button" className="secondary" disabled={busy} onClick={() => void save(null)}>
              Use the Trainer Bot's setup
            </button>
          )}
        </div>
      )}
    </form>
  );
}
