// Loads courses, playground challenges, worlds and the robot from the repo's
// content/ folder. Until the backend exists (milestone 3), content is bundled
// with the app. The same rules are implemented in sim/src/trainer_content.

import { load } from "js-yaml";
import type { Block, Challenge, Course, Lesson, RobotSpec, RunRequest, Unit, WorldSpec } from "./types";

// Console-only programs still run in a world; the robot just sits there.
export const DEFAULT_WORLD = "practice-field";

type Files = Record<string, unknown>;

const parsed = (files: Files) =>
  Object.entries(files)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([path, text]) => [path, load(text as string)] as const);

const worldList = parsed(
  import.meta.glob("../../content/worlds/*.yaml", { query: "?raw", import: "default", eager: true }),
).map(([, data]) => data as WorldSpec);

const robotList = parsed(
  import.meta.glob("../../content/robots/*.yaml", { query: "?raw", import: "default", eager: true }),
).map(([, data]) => data as RobotSpec);

export const challenges = parsed(
  import.meta.glob("../../content/challenges/*.yaml", { query: "?raw", import: "default", eager: true }),
).map(([, data]) => data as Challenge);

export const worlds: Record<string, WorldSpec> = Object.fromEntries(worldList.map((w) => [w.id, w]));

export const robot: RobotSpec = robotList.find((r) => r.id === "trainer-bot") ?? robotList[0];

// --- Courses --------------------------------------------------------------------
// content/courses/<course>/course.yaml
// content/courses/<course>/<unit>/unit.yaml
// content/courses/<course>/<unit>/<lesson>.yaml   (ordered by file name)

const courseFiles = parsed(
  import.meta.glob("../../content/courses/**/*.yaml", { query: "?raw", import: "default", eager: true }),
);

function resolveBlocks(lesson: Lesson): Lesson {
  const byId = new Map(challenges.map((c) => [c.id, c]));
  const blocks = (lesson.blocks ?? []).map((raw, index) => {
    let block = { ...raw } as Block & { ref?: string };
    if (block.type === "challenge" && block.ref) {
      const base = byId.get(block.ref);
      if (!base) throw new Error(`Lesson ${lesson.id}: unknown challenge ref ${block.ref}`);
      block = { ...base, ...block, id: block.id ?? block.ref, type: "challenge" };
    }
    return { ...block, id: block.id ?? `block-${index + 1}` } as Block;
  });
  return { ...lesson, blocks };
}

function buildCourses(): Course[] {
  const courses = new Map<string, Course>();
  const units = new Map<string, Unit>();
  for (const [path, data] of courseFiles) {
    const parts = path.split("/content/courses/")[1].split("/");
    if (parts.length === 2 && parts[1] === "course.yaml") {
      courses.set(parts[0], { ...(data as Course), units: [] });
    } else if (parts.length === 3 && parts[2] === "unit.yaml") {
      units.set(`${parts[0]}/${parts[1]}`, { ...(data as Unit), lessons: [] });
    }
  }
  for (const [path, data] of courseFiles) {
    const parts = path.split("/content/courses/")[1].split("/");
    if (parts.length === 3 && parts[2] !== "unit.yaml") {
      units.get(`${parts[0]}/${parts[1]}`)?.lessons.push(resolveBlocks(data as Lesson));
    }
  }
  for (const [key, unit] of [...units.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    courses.get(key.split("/")[0])?.units.push(unit);
  }
  return [...courses.values()];
}

export const courses = buildCourses();
export const course = courses[0];

export const allLessons: { lesson: Lesson; unit: Unit; number: number }[] = course.units.flatMap((unit) =>
  unit.lessons.map((lesson) => ({ lesson, unit, number: 0 })),
).map((entry, index) => ({ ...entry, number: index + 1 }));

export function findLesson(id: string) {
  const index = allLessons.findIndex((l) => l.lesson.id === id);
  if (index < 0) return null;
  return { ...allLessons[index], next: allLessons[index + 1] ?? null };
}

// --- Running --------------------------------------------------------------------

export function worldFor(challenge: Pick<Challenge, "world">): WorldSpec {
  const id = challenge.world ?? DEFAULT_WORLD;
  const world = worlds[id];
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
