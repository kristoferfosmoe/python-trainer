// "Run it on your robot": the student's code, fitted to their team's robot,
// ready to paste into Pybricks (code.pybricks.com), with the steps to run it.

import { useEffect, useMemo, useRef, useState } from "react";
import { robot } from "../content";
import { inlineMarkdown } from "../markdown";
import { forRobot, PARTS, PYBRICKS_URL, trainerRobot } from "../pybricks";
import { teamWithRobot, useSession } from "../session";
import { CodeView } from "./CodeView";

export function RunOnRobot({ code, onClose }: { code: string; onClose: () => void }) {
  const { me } = useSession();
  const team = teamWithRobot(me);
  const trainer = useMemo(() => trainerRobot(robot()), []);
  const result = useMemo(() => forRobot(code, trainer, team?.robot ?? null), [code, trainer, team]);
  const dialog = useRef<HTMLDialogElement>(null);
  const [copied, setCopied] = useState<"yes" | "failed" | null>(null);

  useEffect(() => {
    dialog.current?.showModal();
  }, []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(result.code);
      setCopied("yes");
    } catch {
      setCopied("failed");
    }
  };

  const trainerParts = PARTS.filter((p) => trainer[p.key])
    .map((p) => `${p.label.toLowerCase()} on \`Port.${trainer[p.key]}\``)
    .join(", ");

  return (
    <dialog ref={dialog} className="robot-dialog" aria-labelledby="robot-dialog-title" onClose={onClose}>
      <header className="robot-dialog-head">
        <h2 id="robot-dialog-title">🤖 Run it on your robot</h2>
        <button className="icon" onClick={() => dialog.current?.close()} aria-label="Close">✕</button>
      </header>

      <section aria-label="Your robot" className="robot-dialog-section">
        {team ? (
          result.changes.length > 0 ? (
            <>
              <p>Changed to fit <b>{team.name}</b>'s robot:</p>
              <ul className="change-list">
                {result.changes.map((change) => <li key={change} dangerouslySetInnerHTML={inlineMarkdown(change)} />)}
              </ul>
            </>
          ) : (
            <p>This code already fits <b>{team.name}</b>'s robot.</p>
          )
        ) : (
          <p className="muted">
            This code is for a robot built like the <b>Trainer Bot</b>:{" "}
            <span dangerouslySetInnerHTML={inlineMarkdown(trainerParts)} />; wheels {trainer.wheel_diameter} mm across
            and {trainer.axle_track} mm apart. If your robot is different, change the port letters and the numbers in{" "}
            <code>DriveBase()</code>, or ask your coach to set up your team's robot.
          </p>
        )}
        {result.problems.length > 0 && (
          <div className="feedback error" role="alert">
            <div className="feedback-title">Fix this first</div>
            <ul>{result.problems.map((p) => <li key={p} dangerouslySetInnerHTML={inlineMarkdown(p)} />)}</ul>
          </div>
        )}
      </section>

      <section aria-label="Code for your robot" className="robot-dialog-section">
        <div className="toolbar">
          <h3>Your code</h3>
          <span className="spacer" />
          <button className="primary" onClick={copy}>{copied === "yes" ? "✔ Copied!" : "📋 Copy code"}</button>
        </div>
        {copied === "failed" && (
          <p className="form-error" role="alert">Your browser didn't let us copy. Click in the code, press Ctrl+A, then Ctrl+C.</p>
        )}
        <div className="robot-code">
          <CodeView code={result.code} label="Code for your robot" />
        </div>
      </section>

      <section aria-label="Steps" className="robot-dialog-section">
        <h3>Run it</h3>
        <ol className="robot-steps">
          <li>
            <a className="button secondary" href={PYBRICKS_URL} target="_blank" rel="noopener noreferrer">Open Pybricks ↗</a>{" "}
            in Chrome or Edge.
          </li>
          <li>Turn on the hub, then click the <b>Bluetooth</b> button in Pybricks and pick your hub. (The first time, the hub needs the Pybricks firmware. Ask your coach.)</li>
          <li>Make a new file and paste your code into it (<kbd>Ctrl</kbd> + <kbd>V</kbd>).</li>
          <li>Clear the table, put the robot in home base, and press <b>▶ Run</b>. To stop, press the hub's stop button.</li>
        </ol>
        <ul className="robot-tips">
          {result.tips.map((tip) => <li key={tip} dangerouslySetInnerHTML={inlineMarkdown(tip)} />)}
        </ul>
      </section>
    </dialog>
  );
}
