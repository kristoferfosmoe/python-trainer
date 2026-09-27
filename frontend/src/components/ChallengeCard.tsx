import { useMemo, useState } from "react";
import { markdown } from "../markdown";
import type { Challenge, GoalResult, WorldSpec } from "../types";
import { withCode } from "./Feedback";

interface Props {
  challenge: Challenge;
  world: WorldSpec;
  goals: GoalResult[] | null; // null until a run has finished playing
  intro?: string; // lesson text shown before the challenge's instructions
}

export function ChallengeCard({ challenge, world, goals, intro }: Props) {
  const [open, setOpen] = useState(true);
  const [hintsShown, setHintsShown] = useState(0);
  const text = [intro, challenge.instructions].filter(Boolean).join("\n\n");
  const instructions = useMemo(() => markdown(text), [text]);
  const realism = challenge.realism !== undefined && challenge.realism !== false && challenge.realism !== "off";
  const goalRows = goals ?? previewGoals(challenge, world);
  const hints = challenge.hints ?? [];

  return (
    <section className="card challenge" aria-labelledby="challenge-title">
      <div className="challenge-head">
        <div>
          <h2 id="challenge-title">{challenge.title}</h2>
          {challenge.summary && <p className="summary">{challenge.summary}</p>}
        </div>
        {text && (
          <button className="link" onClick={() => setOpen(!open)} aria-expanded={open}>
            {open ? "Hide" : "Show"} instructions
          </button>
        )}
      </div>
      {realism && (
        <p className="realism" title="Wheels slip, one wheel may be slightly smaller, and sensors are a bit noisy, like a real robot.">
          🌪️ Real-world wobble is <b>on</b> for this challenge.
        </p>
      )}
      {challenge.buttons && challenge.buttons.length > 0 && (
        <p className="realism" title="Scripted button presses, like a teammate at the table.">
          🔘 A teammate presses {challenge.buttons.map((b) => `${b.button.toLowerCase()} at ${(b.at / 1000).toFixed(1)} s`).join(", ")}.
        </p>
      )}
      {open && text && <div className="instructions markdown" dangerouslySetInnerHTML={instructions} />}
      {goalRows.length > 0 && (
        <ul className="goals" aria-label="Goals">
          {goalRows.map((goal) => (
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

// Before the first run, show goal labels without results. Labels come from the
// simulator after a run; this preview mirrors the simple cases.
function previewGoals(challenge: Challenge, world: WorldSpec): GoalResult[] {
  const zoneName = (id: unknown) => world.zones?.find((z) => z.id === id)?.label ?? String(id);
  return (challenge.goals ?? []).map((goal, i) => ({
    id: `goal-${i}`,
    type: goal.type,
    label: (goal.label as string) ?? describe(goal, zoneName),
    passed: false,
    detail: "",
  }));
}

function describe(goal: Record<string, unknown>, zoneName: (id: unknown) => string): string {
  switch (goal.type) {
    case "end_in_zone":
      return `Finish in ${zoneName(goal.zone)}`;
    case "visit_zones":
      return `Visit ${(goal.zones as string[]).map(zoneName).join(", ")}${goal.in_order ? " in order" : ""}`;
    case "avoid_zones":
      return `Stay out of ${(goal.zones as string[]).map(zoneName).join(", ")}`;
    case "no_collisions":
      return "Don't bump into anything";
    case "max_time":
      return `Finish within ${goal.seconds} seconds`;
    case "must_use":
      return `Use ${MUST_USE[goal.construct as string] ?? goal.construct}`;
    case "max_calls":
      return goal.value === 0
        ? `Don't use \`${goal.name}()\``
        : `Use \`${goal.name}()\` at most ${goal.value} time${goal.value === 1 ? "" : "s"} in your code`;
    case "min_calls":
      return `Use \`${goal.name}()\` in your code`;
    case "uses_variable_in":
      return `Give \`${goal.name}()\` a variable instead of a plain number`;
    case "printed":
      return `Print "${goal.text}"`;
    default:
      return String(goal.type);
  }
}

const MUST_USE: Record<string, string> = {
  for: "a `for` loop",
  while: "a `while` loop",
  if: "an `if` statement",
  def: "a function (`def`)",
  list: "a list",
  variable: "a variable",
  fstring: "an f-string",
  floor_divide: "whole-number division `//`",
  modulo: "the remainder operator `%`",
};
