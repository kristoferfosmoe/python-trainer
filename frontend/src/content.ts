// Loads lessons, worlds and the robot from the repo's content/ folder.
// Until the backend exists (milestone 3), content is bundled with the app.

import { load } from "js-yaml";
import type { Challenge, RobotSpec, RunRequest, WorldSpec } from "./types";

const raw = (files: Record<string, unknown>) =>
  Object.entries(files)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([, text]) => load(text as string));

const worldList = raw(
  import.meta.glob("../../content/worlds/*.yaml", { query: "?raw", import: "default", eager: true }),
) as WorldSpec[];

const robotList = raw(
  import.meta.glob("../../content/robots/*.yaml", { query: "?raw", import: "default", eager: true }),
) as RobotSpec[];

export const challenges = raw(
  import.meta.glob("../../content/challenges/*.yaml", { query: "?raw", import: "default", eager: true }),
) as Challenge[];

export const worlds: Record<string, WorldSpec> = Object.fromEntries(worldList.map((w) => [w.id, w]));

export const robot: RobotSpec = robotList.find((r) => r.id === "trainer-bot") ?? robotList[0];

export function worldFor(challenge: Challenge): WorldSpec {
  const world = worlds[challenge.world];
  if (!world) throw new Error(`Challenge ${challenge.id} uses unknown world ${challenge.world}`);
  return world;
}

export function startFor(challenge: Challenge) {
  const world = worldFor(challenge);
  return {
    x: challenge.start?.x ?? world.start?.x ?? 200,
    y: challenge.start?.y ?? world.start?.y ?? 200,
    heading: challenge.start?.heading ?? world.start?.heading ?? 0,
  };
}

export function runRequest(challenge: Challenge, code: string): RunRequest {
  return {
    code,
    world: worldFor(challenge),
    robot,
    options: {
      time_limit: challenge.time_limit ?? 150,
      realism: challenge.realism ?? "off",
      start: startFor(challenge),
      seed: 1,
    },
    goals: challenge.goals,
  };
}
