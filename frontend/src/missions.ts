// Mission Mode: the ladder, challenges, locks, and reading a match's trace
// at a moment in time (models, attachments, score). See docs/MISSION_MODE.md.

import { api } from "./api";
import { frameIndexAt, lastIndexAtOrBefore } from "./playback";
import type {
  AttachmentSpec, GameSpec, LadderGame, MissionChallenge, MissionRunRequest, ModelSpec, ModelState, Pose, Trace,
} from "./types";

// --- Fetching ----------------------------------------------------------------------------

export const fetchLadder = () => api<{ games: LadderGame[]; signed_in: boolean }>("/missions");

const challengeCache = new Map<string, Promise<{ game: GameSpec; challenge: MissionChallenge }>>();

/** One challenge and its game. Cached per person, since solutions depend on who's asking. */
export function fetchMissionChallenge(id: string, who: string) {
  const key = `${who}:${id}`;
  let request = challengeCache.get(key);
  if (!request) {
    request = api<{ game: GameSpec; challenge: MissionChallenge }>(`/missions/challenges/${encodeURIComponent(id)}`);
    request.catch(() => challengeCache.delete(key));
    challengeCache.set(key, request);
  }
  return request;
}

// --- Locks -----------------------------------------------------------------------------------

/** Challenges you can open: each unlocks when the one before it has a star. The server's
 * answer (for signed-in students and staff) counts too, so staff can open everything. */
export function unlockedIds(game: LadderGame, stars: (id: string) => number): Set<string> {
  const open = new Set<string>();
  game.challenges.forEach((challenge, i) => {
    const previous = game.challenges[i - 1];
    if (challenge.unlocked === true || i === 0 || (previous && stars(previous.id) >= 1 && open.has(previous.id))) {
      open.add(challenge.id);
    }
  });
  return open;
}

export function nextChallengeId(game: LadderGame, id: string): string | null {
  const index = game.challenges.findIndex((c) => c.id === id);
  return index >= 0 && index + 1 < game.challenges.length ? game.challenges[index + 1].id : null;
}

// --- Runs and attachments --------------------------------------------------------------------

export interface RunPlan {
  start: Pose;
  /** Port → attachment id, with the student's picks applied. */
  attachments: Record<string, string>;
  /** Port → the attachments to choose from (only ports with a choice). */
  choose: Record<string, string[]>;
}

export function runPlans(game: GameSpec, challenge: MissionChallenge, picks: Record<string, string>[] = []): RunPlan[] {
  const fallback = game.field.start ?? {};
  const runs = challenge.runs?.length ? challenge.runs : [{}];
  return runs.map((run, i) => {
    const attachments: Record<string, string> = { ...(run.attachments ?? {}) };
    const choose: Record<string, string[]> = {};
    for (const [port, options] of Object.entries(run.choose ?? {})) {
      choose[port] = options;
      const pick = picks[i]?.[port];
      attachments[port] = pick && options.includes(pick) ? pick : options[0];
    }
    return {
      start: {
        x: run.start?.x ?? fallback.x ?? 200,
        y: run.start?.y ?? fallback.y ?? 200,
        heading: run.start?.heading ?? fallback.heading ?? 0,
      },
      attachments,
      choose,
    };
  });
}

export function missionRequest(
  game: GameSpec, challenge: MissionChallenge, code: string, picks: Record<string, string>[],
): MissionRunRequest {
  const plans = runPlans(game, challenge, picks);
  const choices = plans.map((plan) =>
    Object.fromEntries(Object.keys(plan.choose).map((port) => [port, plan.attachments[port]])),
  );
  return { code, game, challenge, choices };
}

export function fieldModels(game: GameSpec, challenge: MissionChallenge): ModelSpec[] {
  return challenge.models ? game.models.filter((m) => challenge.models!.includes(m.id)) : game.models;
}

// --- Models before a run ------------------------------------------------------------------------

/** A model as it starts (the same as the simulator's Model.snapshot at the start). */
export function initialState(spec: ModelSpec): ModelState {
  const at = spec.at ?? spec.hinge ?? [0, 0];
  const firstState: Record<ModelSpec["type"], string> = {
    block: "on_field", lever: spec.states?.[0] ?? "start", button: "not_pressed", loop: "on_post", flag: "down", gate: "closed",
  };
  return {
    state: firstState[spec.type],
    hidden: Boolean(spec.hidden),
    x: at[0],
    y: at[1],
    angle: spec.type === "lever" ? Number(spec.angle ?? 0) : undefined,
    presses: 0,
    down: false,
  };
}

// --- Reading a trace at time t -----------------------------------------------------------------

const history = new WeakMap<Trace, Map<string, { frames: number[]; states: ModelState[] }>>();

function modelHistory(trace: Trace) {
  let found = history.get(trace);
  if (!found) {
    found = new Map();
    for (const [frame, id, state] of trace.mission?.changes ?? []) {
      let entry = found.get(id);
      if (!entry) found.set(id, (entry = { frames: [], states: [] }));
      entry.frames.push(frame);
      entry.states.push(state);
    }
    history.set(trace, found);
  }
  return found;
}

/** Every model's state at time t. */
export function modelStatesAt(trace: Trace, t: number): Record<string, ModelState> {
  const mission = trace.mission;
  if (!mission) return {};
  const frame = frameIndexAt(trace, t);
  const states: Record<string, ModelState> = { ...mission.initial };
  for (const [id, entry] of modelHistory(trace)) {
    const i = lastIndexAtOrBefore(entry.frames, frame);
    if (i >= 0) states[id] = entry.states[i];
  }
  return states;
}

export interface ArmState {
  spec: AttachmentSpec;
  angle: number;
}

/** The attachments on the robot at time t, and their angles. */
export function armsAt(trace: Trace, t: number): ArmState[] {
  const mission = trace.mission;
  if (!mission) return [];
  const frame = frameIndexAt(trace, t);
  const mounted: Record<string, string | null> = {};
  for (const [f, port, id] of mission.mounts) if (f <= frame) mounted[port] = id;
  const arms: ArmState[] = [];
  for (const [port, id] of Object.entries(mounted)) {
    const angle = mission.arms[port]?.[frame];
    const spec = id ? mission.attachments[id] : undefined;
    if (spec && angle !== null && angle !== undefined) arms.push({ spec, angle });
  }
  return arms;
}

export function scoreAt(trace: Trace, t: number): number {
  const timeline = trace.mission?.score.timeline ?? [];
  const i = lastIndexAtOrBefore(timeline.map(([time]) => time), t);
  return i >= 0 ? timeline[i][1] : 0;
}

export function tokensAt(trace: Trace, t: number): number {
  const mission = trace.mission;
  if (!mission) return 0;
  const lost = trace.events.filter((e) => e.type === "interruption" && e.t <= t).length;
  return Math.max(0, mission.score.token_start - lost);
}

/** The run going on at time t (1-based), or null between runs. */
export function runAt(trace: Trace, t: number): number | null {
  const run = trace.mission?.runs.find((r) => r.start <= t && (r.end === null || t <= r.end));
  return run ? run.run : null;
}

export function starText(stars: number): string {
  return "★".repeat(stars) + "☆".repeat(Math.max(0, 3 - stars));
}
