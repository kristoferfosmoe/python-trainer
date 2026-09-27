// Lesson progress, kept in this browser until accounts exist (milestone 3).

import { useSyncExternalStore } from "react";
import type { Block, Lesson } from "./types";

export interface LessonProgress {
  page: number; // furthest page reached (0-based)
  done: string[]; // ids of finished quizzes and challenges
  finished: boolean; // reached the end of the lesson
}

type Store = Record<string, LessonProgress>;

const KEY = "progress:v1";
const listeners = new Set<() => void>();
let cache: Store | null = null;

function read(): Store {
  if (cache) return cache;
  try {
    cache = JSON.parse(localStorage.getItem(KEY) ?? "{}") as Store;
  } catch {
    cache = {};
  }
  return cache;
}

function write(store: Store) {
  cache = store;
  try {
    localStorage.setItem(KEY, JSON.stringify(store));
  } catch {
    // Private windows can block storage; progress just won't be remembered.
  }
  listeners.forEach((listener) => listener());
}

export function lessonProgress(lessonId: string): LessonProgress {
  return read()[lessonId] ?? { page: 0, done: [], finished: false };
}

export function update(lessonId: string, change: (p: LessonProgress) => LessonProgress) {
  const store = read();
  write({ ...store, [lessonId]: change(lessonProgress(lessonId)) });
}

export function markDone(lessonId: string, blockId: string) {
  update(lessonId, (p) => (p.done.includes(blockId) ? p : { ...p, done: [...p.done, blockId] }));
}

export function reachPage(lessonId: string, page: number) {
  update(lessonId, (p) => (page > p.page ? { ...p, page } : p));
}

export function finishLesson(lessonId: string) {
  update(lessonId, (p) => ({ ...p, finished: true }));
}

/** Quizzes and challenges with goals must be done to complete a lesson. */
export function isRequired(block: Block): boolean {
  return block.type === "quiz" || (block.type === "challenge" && (block.goals?.length ?? 0) > 0);
}

export type LessonStatus = "new" | "started" | "done";

export function lessonStatus(lesson: Lesson, progress = lessonProgress(lesson.id)): LessonStatus {
  const required = lesson.blocks.filter(isRequired);
  if (progress.finished && required.every((b) => progress.done.includes(b.id))) return "done";
  if (progress.page > 0 || progress.done.length > 0) return "started";
  return "new";
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Re-render when progress changes. */
export function useProgress(): Store {
  return useSyncExternalStore(subscribe, read);
}
