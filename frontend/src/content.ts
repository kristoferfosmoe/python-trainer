// Lessons and everything needed to run them, from the backend. Challenge
// solutions are only included for coaches, mentors and staff.

import { useSyncExternalStore } from "react";
import { api } from "./api";
import type { Challenge, CourseSummary, Lesson, LessonSummary, RobotSpec, RunRequest, UnitSummary, WorldSpec } from "./types";

// Console-only programs still run in a world; the robot just sits there.
export const DEFAULT_WORLD = "practice-field";

export interface Catalog {
  courses: CourseSummary[];
  playground: Challenge[];
  worlds: Record<string, WorldSpec>;
  robot: RobotSpec;
  solutions_included: boolean;
}

export interface LessonEntry {
  lesson: LessonSummary;
  unit: UnitSummary;
  course: CourseSummary;
  number: number; // 1-based, within its course
}

let catalog: Catalog | null = null;
let entries: LessonEntry[] = [];
const lessonCache = new Map<string, Promise<Lesson>>();
const listeners = new Set<() => void>();

export async function loadCatalog() {
  catalog = await api<Catalog>("/catalog");
  entries = catalog.courses.flatMap((course) =>
    course.units.flatMap((unit) => unit.lessons.map((lesson) => ({ lesson, unit, course, number: 0 }))),
  );
  for (const course of catalog.courses) {
    entries.filter((e) => e.course === course).forEach((e, i) => (e.number = i + 1));
  }
  lessonCache.clear();
  listeners.forEach((listener) => listener());
}

export function getCatalog(): Catalog {
  if (!catalog) throw new Error("The catalog hasn't loaded yet.");
  return catalog;
}

/** Re-render when the catalog reloads (after signing in or out). */
export function useCatalog(): Catalog {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    getCatalog,
  );
}

export const allLessons = () => entries;

export function findLesson(id: string) {
  const index = entries.findIndex((e) => e.lesson.id === id);
  if (index < 0) return null;
  const entry = entries[index];
  const next = entries[index + 1];
  return { ...entry, next: next && next.course === entry.course ? next : null };
}

export function fetchLesson(id: string): Promise<Lesson> {
  let request = lessonCache.get(id);
  if (!request) {
    request = api<Lesson>(`/lessons/${encodeURIComponent(id)}`);
    request.catch(() => lessonCache.delete(id));
    lessonCache.set(id, request);
  }
  return request;
}

export const robot = () => getCatalog().robot;

// --- Running --------------------------------------------------------------------

export function worldFor(challenge: Pick<Challenge, "world">): WorldSpec {
  const id = challenge.world ?? DEFAULT_WORLD;
  const world = getCatalog().worlds[id];
  if (!world) throw new Error(`Unknown world ${id}`);
  return world;
}

export function startFor(challenge: Pick<Challenge, "world" | "start">) {
  const world = worldFor(challenge);
  return {
    x: challenge.start?.x ?? world.start?.x ?? 200,
    y: challenge.start?.y ?? world.start?.y ?? 200,
    heading: challenge.start?.heading ?? world.start?.heading ?? 0,
  };
}

export function runRequest(challenge: Partial<Challenge>, code: string): RunRequest {
  return {
    code,
    world: worldFor(challenge),
    robot: robot(),
    options: {
      time_limit: challenge.time_limit ?? 150,
      realism: challenge.realism ?? "off",
      start: startFor(challenge),
      seed: 1,
      buttons: challenge.buttons,
    },
    goals: challenge.goals,
  };
}
