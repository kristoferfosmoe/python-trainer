// Lesson progress helpers on top of the session store.

import type { Block, LessonSummary } from "./types";
import { lessonProgress, useSession, type LessonProgress } from "./session";

export { finishLesson, lessonProgress, markDone, reachPage, type LessonProgress } from "./session";

/** Quizzes and challenges with goals must be done to complete a lesson. */
export function isRequired(block: Block): boolean {
  return block.type === "quiz" || (block.type === "challenge" && (block.goals?.length ?? 0) > 0);
}

export type LessonStatus = "new" | "started" | "done";

/**
 * A lesson is done when the student reached its end with every quiz and goal
 * challenge finished. The map only has lesson summaries, so it trusts
 * `finished` plus the absence of skipped challenges recorded at the end.
 */
export function lessonStatus(lesson: LessonSummary, progress: LessonProgress = lessonProgress(lesson.id)): LessonStatus {
  if (progress.finished) return "done";
  if (progress.page > 0 || progress.done.length > 0) return "started";
  return "new";
}

export function useProgress(): Record<string, LessonProgress> {
  return useSession().lessons;
}
