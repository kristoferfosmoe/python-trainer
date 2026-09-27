// Looking things up in a trace at a moment in (robot) time.

import type { Pose, Trace, TraceEvent, VarEntry } from "./types";

/** Index of the last item whose time is <= t (or -1). `times` must be sorted. */
export function lastIndexAtOrBefore(times: ArrayLike<number>, t: number): number {
  let lo = 0;
  let hi = times.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (times[mid] <= t) {
      found = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return found;
}

export function frameIndexAt(trace: Trace, t: number): number {
  return Math.max(0, lastIndexAtOrBefore(trace.frames.t, t));
}

/** Robot pose at time t, smoothly between recorded frames. */
export function poseAt(trace: Trace, t: number): Pose {
  const f = trace.frames;
  const i = frameIndexAt(trace, t);
  const j = Math.min(i + 1, f.t.length - 1);
  if (i === j || f.t[j] === f.t[i]) return { x: f.x[i], y: f.y[i], heading: f.heading[i] };
  const k = Math.min(1, Math.max(0, (t - f.t[i]) / (f.t[j] - f.t[i])));
  return {
    x: f.x[i] + (f.x[j] - f.x[i]) * k,
    y: f.y[i] + (f.y[j] - f.y[i]) * k,
    heading: f.heading[i] + (f.heading[j] - f.heading[i]) * k,
  };
}

/** The line of code running at time t. */
export function lineAt(trace: Trace, t: number): number {
  if (t >= trace.end.t && trace.end.line) return trace.end.line;
  return trace.frames.line[frameIndexAt(trace, t)] || 0;
}

export function varsAt(trace: Trace, t: number): VarEntry[] {
  const index = lastIndexAtOrBefore(trace.vars.map((v) => v.t), t);
  return index >= 0 ? trace.vars[index].vars : [];
}

export function countAtOrBefore<T extends { t: number }>(items: T[], t: number): number {
  return lastIndexAtOrBefore(items.map((i) => i.t), t) + 1;
}

export interface HubState {
  light: string;
  display: string;
}

export function hubAt(trace: Trace, t: number): HubState {
  const state: HubState = { light: "off", display: "" };
  for (const event of trace.events) {
    if (event.t > t) break;
    if (event.type === "light") state.light = event.color ?? "off";
    if (event.type === "display") state.display = event.text ?? "";
  }
  return state;
}

export function sensorAt(trace: Trace, key: string, t: number): number | string | undefined {
  const values = trace.sensors[key];
  return values ? values[frameIndexAt(trace, t)] : undefined;
}

/** Events that happen in (from, to]: used to play beeps during playback. */
export function eventsBetween(trace: Trace, from: number, to: number): TraceEvent[] {
  return trace.events.filter((e) => e.t > from && e.t <= to);
}

export function recentCollision(trace: Trace, t: number, windowMs = 400): boolean {
  return trace.events.some((e) => e.type === "collision" && e.t <= t && t - e.t < windowMs);
}

export function formatTime(ms: number): string {
  return `${(ms / 1000).toFixed(1)} s`;
}
