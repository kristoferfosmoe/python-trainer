import { describe, expect, it } from "vitest";
import { paginate } from "./lessonPages";
import { stepView } from "./stepping";
import type { Block, Trace } from "./types";

// for side in range(2):
//     print(side)
// print("done")
function loopTrace(): Trace {
  return {
    sim_version: "0.1.0",
    frame_ms: 20,
    start: { x: 0, y: 0, heading: 0 },
    frames: { t: [0], x: [0], y: [0], heading: [0], line: [0] },
    sensors: {},
    motors: {},
    steps: [[0, 1], [0.25, 2], [0.5, 1], [0.75, 2], [1, 1], [1.25, 3]],
    steps_truncated: false,
    vars: [
      { t: 0.25, vars: [["side", "0", "global"]] },
      { t: 0.75, vars: [["side", "1", "global"]] },
    ],
    prints: [
      { t: 0.5, line: 2, text: "0" },
      { t: 1, line: 2, text: "1" },
      { t: 1.5, line: 3, text: "done" },
    ],
    prints_truncated: false,
    events: [],
    end: { reason: "finished", t: 1.5, line: 3 },
    warnings: [],
    structure: [{ line: 1, body: [2, 2], kind: "for", target: "side" }],
    goals: [],
    stats: { lines: 6, sim_ms: 1.5, wall_ms: 1 },
  };
}

describe("stepView", () => {
  it("announces the loop round and the loop variable", () => {
    const view = stepView(loopTrace(), 0);
    expect(view.line).toBe(1);
    expect(view.annotations.notes.get(1)?.text).toBe("🔁 round 1: side = 0");
    expect(view.printCount).toBe(0);
  });

  it("counts how many times each line has run", () => {
    const view = stepView(loopTrace(), 3);
    expect(view.line).toBe(2);
    expect(view.annotations.counts.get(1)).toBe(2);
    expect(view.annotations.counts.get(2)).toBe(1);
    expect(view.annotations.notes.get(1)?.text).toBe("🔁 round 2");
    expect(view.printCount).toBe(1);
  });

  it("says when the loop is done", () => {
    const view = stepView(loopTrace(), 4);
    expect(view.annotations.notes.get(1)?.text).toBe("✅ loop done after 2 rounds");
  });

  it("has a final 'done' step with all the output", () => {
    const view = stepView(loopTrace(), 6);
    expect(view.done).toBe(true);
    expect(view.line).toBeNull();
    expect(view.printCount).toBe(3);
  });

  it("shows whether an if is True or False", () => {
    const trace = loopTrace();
    trace.structure = [{ line: 1, body: [2, 2], kind: "if" }];
    trace.steps = [[0, 1], [0.25, 3]];
    expect(stepView(trace, 0).annotations.notes.get(1)?.text).toBe("✖ False: skips them");
    trace.steps = [[0, 1], [0.25, 2]];
    expect(stepView(trace, 0).annotations.notes.get(1)?.text).toBe("✔ True: runs the indented lines");
  });
});

describe("paginate", () => {
  it("ends a page after each interactive block", () => {
    const t = (id: string): Block => ({ type: "text", id, markdown: id });
    const q = (id: string): Block => ({ type: "quiz", id, question: "?", choices: ["a", "b"], answer: 0 });
    const pages = paginate([t("a"), q("b"), t("c"), t("d"), q("e"), t("f")]);
    expect(pages.map((p) => p.map((b) => b.id))).toEqual([["a", "b"], ["c", "d", "e"], ["f"]]);
  });
});
