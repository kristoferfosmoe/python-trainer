import { describe, expect, it } from "vitest";
import { hubAt, lastIndexAtOrBefore, lineAt, poseAt, varsAt } from "./playback";
import type { Trace } from "./types";

function makeTrace(): Trace {
  return {
    sim_version: "0.1.0",
    frame_ms: 20,
    start: { x: 0, y: 0, heading: 0 },
    frames: { t: [0, 20, 40], x: [0, 10, 20], y: [0, 0, 0], heading: [0, 0, 90], line: [1, 2, 3] },
    sensors: {},
    motors: {},
    steps: [],
    steps_truncated: false,
    vars: [
      { t: 0, vars: [["a", "1", "global"]] },
      { t: 30, vars: [["a", "2", "global"]] },
    ],
    prints: [],
    prints_truncated: false,
    events: [
      { t: 5, type: "light", line: 1, color: "red" },
      { t: 25, type: "display", line: 2, text: "Hi" },
    ],
    end: { reason: "finished", t: 40, line: 3 },
    warnings: [],
    goals: [],
    stats: { lines: 3, sim_ms: 40, wall_ms: 1 },
  };
}

describe("playback", () => {
  it("finds the last index at or before a time", () => {
    expect(lastIndexAtOrBefore([0, 20, 40], -1)).toBe(-1);
    expect(lastIndexAtOrBefore([0, 20, 40], 0)).toBe(0);
    expect(lastIndexAtOrBefore([0, 20, 40], 39)).toBe(1);
    expect(lastIndexAtOrBefore([0, 20, 40], 100)).toBe(2);
  });

  it("interpolates the pose between frames", () => {
    const pose = poseAt(makeTrace(), 30);
    expect(pose.x).toBeCloseTo(15);
    expect(pose.heading).toBeCloseTo(45);
  });

  it("looks up the line, variables and hub state", () => {
    const trace = makeTrace();
    expect(lineAt(trace, 25)).toBe(2);
    expect(varsAt(trace, 29)).toEqual([["a", "1", "global"]]);
    expect(varsAt(trace, 30)).toEqual([["a", "2", "global"]]);
    expect(hubAt(trace, 10)).toEqual({ light: "red", display: "" });
    expect(hubAt(trace, 30)).toEqual({ light: "red", display: "Hi" });
  });
});
