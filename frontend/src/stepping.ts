// What the step-by-step visualizer shows at each step of a trace.
// A "step" is one line about to run. Step N (one past the last) means "done".

import { varsAt } from "./playback";
import type { Annotations, NoteTone } from "./components/CodeView";
import type { Trace } from "./types";

export interface StepView {
  line: number | null; // line about to run
  time: number; // robot time at this step
  annotations: Annotations;
  printCount: number; // how many prints have happened so far
  done: boolean;
}

function note(text: string, tone: NoteTone) {
  return { text, tone };
}

export function stepView(trace: Trace, index: number): StepView {
  const steps = trace.steps;
  const done = index >= steps.length;
  const line = done ? null : steps[index][1];
  const time = done ? trace.end.t : steps[index][0];

  // How many times each line has run so far (before this step).
  const counts = new Map<number, number>();
  for (let i = 0; i < Math.min(index, steps.length); i++) {
    counts.set(steps[i][1], (counts.get(steps[i][1]) ?? 0) + 1);
  }
  const ran = (n: number) => counts.get(n) ?? 0;

  const notes = new Map<number, { text: string; tone: NoteTone }>();

  // Loops we're inside of show which round they're on.
  if (line !== null) {
    for (const s of trace.structure) {
      if ((s.kind === "for" || s.kind === "while") && line >= s.body[0] && line <= s.body[1]) {
        const round = ran(s.body[0]) + (line === s.body[0] ? 1 : 0);
        notes.set(s.line, note(`🔁 round ${round}`, "loop"));
      }
    }
  }

  // The line about to run: say what it will decide.
  const here = trace.structure.find((s) => s.line === line);
  if (here && line !== null) {
    const next = index + 1 < steps.length ? steps[index + 1][1] : null;
    const entersBody = next !== null && next >= here.body[0] && next <= here.body[1];
    if (here.kind === "if" || here.kind === "elif") {
      notes.set(line, entersBody ? note("✔ True: runs the indented lines", "yes") : note("✖ False: skips them", "no"));
    } else {
      const rounds = ran(here.body[0]);
      if (entersBody) {
        let text = `🔁 round ${rounds + 1}`;
        if (here.kind === "for" && here.target && next !== null) {
          const value = varsAt(trace, steps[index + 1][0]).find(([name]) => name === here.target)?.[1];
          if (value !== undefined) text += `: ${here.target} = ${value}`;
        } else if (here.kind === "while") {
          text += ": condition is True";
        }
        notes.set(line, note(text, "loop"));
      } else {
        notes.set(line, note(`✅ loop done after ${rounds} round${rounds === 1 ? "" : "s"}`, "yes"));
      }
    }
  }

  const printCount = trace.prints.filter((p) => p.t <= time).length;
  const errorLine = done && trace.end.error ? trace.end.error.line : null;
  return { line, time, done, printCount, annotations: { activeLine: line, errorLine, counts, notes } };
}
