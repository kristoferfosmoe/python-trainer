import { describe, expect, it } from "vitest";
import {
  armsAt, initialState, missionRequest, modelStatesAt, runAt, runPlans, scoreAt, starText, tokensAt, unlockedIds,
} from "./missions";
import type { GameSpec, LadderGame, MissionChallenge, Trace } from "./types";

const ladder = (unlocked: (boolean | null)[]): LadderGame => ({
  id: "harbor",
  title: "Harbor",
  tiers: [],
  challenges: unlocked.map((u, i) => ({
    id: `c${i + 1}`, title: `C${i + 1}`, tier: 1, summary: "", unlocked: u, stars: 0, best_score: 0,
  })),
});

describe("unlockedIds", () => {
  it("unlocks one challenge after another", () => {
    const game = ladder([null, null, null, null]);
    expect([...unlockedIds(game, () => 0)]).toEqual(["c1"]);
    const stars: Record<string, number> = { c1: 1, c2: 0 };
    expect([...unlockedIds(game, (id) => stars[id] ?? 0)]).toEqual(["c1", "c2"]);
    // Stars on a later challenge don't skip a locked one.
    const skipped: Record<string, number> = { c3: 3 };
    expect([...unlockedIds(game, (id) => skipped[id] ?? 0)]).toEqual(["c1"]);
  });

  it("trusts the server's unlocked flags (staff can open everything)", () => {
    expect(unlockedIds(ladder([true, true, true]), () => 0).size).toBe(3);
    expect([...unlockedIds(ladder([true, false, false]), (id) => (id === "c1" ? 2 : 0))]).toEqual(["c1", "c2"]);
  });
});

const game = {
  field: { id: "f", name: "F", size: [2362, 1143], start: { x: 200, y: 330, heading: 0 } },
  attachments: [], models: [], missions: [], tiers: [],
} as unknown as GameSpec;

const challenge: MissionChallenge = {
  id: "pick", title: "Pick", tier: 6, starter: "",
  runs: [
    { start: { x: 200, y: 330 }, choose: { E: ["forklift", "pusher"] } },
    { start: { x: 200, y: 700, heading: -90 }, attachments: { F: "sweeper" }, choose: { E: ["forklift", "pusher"] } },
  ],
};

describe("runPlans", () => {
  it("applies the student's picks, falling back to the first choice", () => {
    const plans = runPlans(game, challenge, [{ E: "pusher" }, { E: "catapult" }]);
    expect(plans[0]).toEqual({ start: { x: 200, y: 330, heading: 0 }, attachments: { E: "pusher" }, choose: { E: ["forklift", "pusher"] } });
    expect(plans[1].attachments).toEqual({ F: "sweeper", E: "forklift" });
    expect(plans[1].start.heading).toBe(-90);
  });

  it("sends only the ports with a choice", () => {
    expect(missionRequest(game, challenge, "pass", [{ E: "pusher" }]).choices).toEqual([{ E: "pusher" }, { E: "forklift" }]);
  });

  it("gives a challenge without runs one run from the field's start", () => {
    expect(runPlans(game, { ...challenge, runs: undefined })).toEqual([
      { start: { x: 200, y: 330, heading: 0 }, attachments: {}, choose: {} },
    ]);
  });
});

function trace(): Trace {
  return {
    frames: { t: [0, 20, 40, 60], x: [0, 0, 0, 0], y: [0, 0, 0, 0], heading: [0, 0, 0, 0], line: [0, 0, 0, 0] },
    events: [{ t: 45, type: "interruption", line: 3 }],
    mission: {
      initial: { crate: { state: "on_field", hidden: false, x: 700, y: 330 } },
      changes: [[1, "crate", { state: "on_field", hidden: false, x: 710, y: 330 }], [3, "crate", { state: "on_field", hidden: false, x: 720, y: 330 }]],
      arms: { E: [0, 10, 20, null], F: [null, null, null, null] },
      mounts: [[0, "E", "forklift"], [3, "E", null]],
      attachments: { forklift: { id: "forklift", name: "Forklift", kind: "lift", port: "E", length: 130 } },
      runs: [{ run: 1, start: 0, end: 30, ended: "home", attachments: {} }, { run: 2, start: 50, end: null, ended: null, attachments: {} }],
      home: "home",
      score: { total: 40, missions: [], tokens: 5, token_start: 6, token_points: 35, timeline: [[0, 50], [25, 70], [45, 55]] },
      stars: 1, thresholds: null, seeds: [],
    },
  } as unknown as Trace;
}

describe("reading a match at a moment", () => {
  it("finds each model's state", () => {
    const t = trace();
    expect(modelStatesAt(t, 0).crate.x).toBe(700);
    expect(modelStatesAt(t, 25).crate.x).toBe(710);
    expect(modelStatesAt(t, 60).crate.x).toBe(720);
  });

  it("finds the attachments and their angles", () => {
    const t = trace();
    expect(armsAt(t, 20).map((a) => [a.spec.id, a.angle])).toEqual([["forklift", 10]]);
    expect(armsAt(t, 60)).toEqual([]); // taken off
  });

  it("follows the score, the tokens and the runs", () => {
    const t = trace();
    expect([scoreAt(t, 0), scoreAt(t, 30), scoreAt(t, 60)]).toEqual([50, 70, 55]);
    expect([tokensAt(t, 40), tokensAt(t, 50)]).toEqual([6, 5]);
    expect([runAt(t, 10), runAt(t, 40), runAt(t, 55)]).toEqual([1, null, 2]);
  });
});

describe("initialState and stars", () => {
  it("starts models like the simulator does", () => {
    expect(initialState({ id: "l", type: "lever", hinge: [5, 6], angle: 90, states: ["dark", "lit"] })).toMatchObject({
      state: "dark", x: 5, y: 6, angle: 90, hidden: false,
    });
    expect(initialState({ id: "p", type: "block", at: [1, 2], hidden: true }).hidden).toBe(true);
  });

  it("writes stars", () => {
    expect([starText(0), starText(2), starText(3)]).toEqual(["☆☆☆", "★★☆", "★★★"]);
  });
});
