// Plays a lesson one page at a time (see paginate for how pages are split).

import { useEffect, useMemo, useState } from "react";
import { fetchLesson, findLesson, useCatalog } from "../content";
import { hasGoals, paginate } from "../lessonPages";
import { href, navigate } from "../router";
import * as progress from "../progress";
import type { Block, ChallengeBlock, Lesson, LessonSummary } from "../types";
import { CodeBlockView, QuizBlockView, TextBlockView } from "../components/Blocks";
import { ChallengeWorkspace } from "../components/ChallengeWorkspace";

export function LessonPage({ lessonId, pageNumber }: { lessonId: string; pageNumber?: number }) {
  useCatalog(); // re-render if the catalog reloads
  const found = findLesson(lessonId);
  const store = progress.useProgress();
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    setLesson(null);
    setFailed(null);
    fetchLesson(lessonId).then(
      (loaded) => current && setLesson(loaded),
      (error: Error) => current && setFailed(error.message),
    );
    return () => {
      current = false;
    };
  }, [lessonId, found?.course.id]);

  if (!found) {
    return (
      <div className="card narrow">
        <h2>Lesson not found</h2>
        <p><a href="#/">Back to the lessons</a></p>
      </div>
    );
  }
  if (failed) {
    return (
      <div className="card narrow">
        <h2>This lesson didn't load</h2>
        <p>{failed}</p>
        <p><a href="#/">Back to the lessons</a></p>
      </div>
    );
  }
  if (!lesson) return <p className="empty padded">⏳ Loading the lesson…</p>;
  const { unit, number, next } = found;
  const state = store[lesson.id] ?? progress.lessonProgress(lesson.id);
  return <LessonPlayer key={lesson.id} lesson={lesson} unitTitle={`${unit.icon ?? ""} ${unit.title}`} number={number} next={next?.lesson ?? null} state={state} pageNumber={pageNumber} />;
}

interface PlayerProps {
  lesson: Lesson;
  unitTitle: string;
  number: number;
  next: LessonSummary | null;
  state: progress.LessonProgress;
  pageNumber?: number;
}

function LessonPlayer({ lesson, unitTitle, number, next, state, pageNumber }: PlayerProps) {
  const pages = useMemo(() => paginate(lesson.blocks), [lesson]);
  const finishedPage = pages.length; // one past the last page: the "lesson complete" screen
  const index = Math.min(finishedPage, Math.max(0, (pageNumber ?? state.page + 1) - 1));
  const go = (page: number) => navigate({ page: "lesson", lessonId: lesson.id, pageNumber: page + 1 });

  useEffect(() => {
    if (index < finishedPage) progress.reachPage(lesson.id, index);
  }, [lesson.id, index, finishedPage]);

  const done = (id: string) => state.done.includes(id);
  const page = pages[index] ?? [];
  const quizzesDone = page.filter((b) => b.type === "quiz").every((b) => done(b.id));
  const challengesDone = page.filter(hasGoals).every((b) => done(b.id));
  const challenge = page.find((b): b is ChallengeBlock => b.type === "challenge");
  const isLast = index === pages.length - 1;

  const onContinue = () => go(index + 1);

  return (
    <div className={`lesson ${challenge ? "lesson-wide" : ""}`}>
      <header className="lesson-head">
        <a className="back" href="#/">← All lessons</a>
        <div className="lesson-title">
          <span className="lesson-unit">{unitTitle}</span>
          <h1>
            Lesson {number}: {lesson.title}
          </h1>
        </div>
        <ol className="page-dots" aria-label="Pages">
          {pages.map((_, i) => {
            const reached = i <= state.page || state.finished;
            return (
              <li key={i}>
                <button
                  className={`dot ${i === index ? "current" : reached ? "reached" : ""}`}
                  onClick={() => go(i)}
                  disabled={!reached}
                  aria-label={`Page ${i + 1}`}
                  aria-current={i === index ? "step" : undefined}
                />
              </li>
            );
          })}
        </ol>
      </header>

      {index >= finishedPage ? (
        <Finished lesson={lesson} next={next} state={state} pages={pages} onGo={go} />
      ) : (
        <>
          {challenge ? (
            <ChallengeWorkspace
              key={challenge.id}
              challenge={challenge}
              codeKey={`lesson/${lesson.id}/${challenge.id}`}
              lessonId={lesson.id}
              intro={page.filter((b) => b.type === "text").map((b) => (b.type === "text" ? b.markdown : "")).join("\n\n")}
              onSolved={() => progress.markDone(lesson.id, challenge.id)}
              solvedAction={
                <button className="primary" onClick={onContinue}>
                  {isLast ? "Finish lesson 🎉" : "Continue →"}
                </button>
              }
            />
          ) : (
            <div className="lesson-page">
              {page.map((block) => (
                <BlockView key={block.id} block={block} lessonId={lesson.id} done={done(block.id)} />
              ))}
            </div>
          )}
          <nav className="lesson-nav" aria-label="Lesson navigation">
            <button className="secondary" onClick={() => (index === 0 ? navigate({ page: "map" }) : go(index - 1))}>
              ← Back
            </button>
            <span className="nav-hint">
              {!quizzesDone ? "Answer the question to keep going." : !challengesDone ? "Solve the challenge, or skip it for now." : ""}
            </span>
            <button
              className={challengesDone ? "primary" : "secondary"}
              onClick={onContinue}
              disabled={!quizzesDone}
            >
              {!challengesDone ? "Skip for now →" : isLast ? "Finish lesson 🎉" : "Continue →"}
            </button>
          </nav>
        </>
      )}
    </div>
  );
}

function BlockView({ block, lessonId, done }: { block: Block; lessonId: string; done: boolean }) {
  switch (block.type) {
    case "text":
      return <TextBlockView block={block} />;
    case "example":
    case "visualize":
      return <CodeBlockView block={block} lessonId={lessonId} />;
    case "quiz":
      return <QuizBlockView block={block} done={done} onCorrect={() => progress.markDone(lessonId, block.id)} />;
    case "challenge":
      return null; // rendered as a full workspace
  }
}

interface FinishedProps {
  lesson: Lesson;
  next: LessonSummary | null;
  state: progress.LessonProgress;
  pages: Block[][];
  onGo: (page: number) => void;
}

function Finished({ lesson, next, state, pages, onGo }: FinishedProps) {
  const skipped = pages
    .map((page, i) => ({ i, block: page.find(hasGoals) }))
    .filter((p): p is { i: number; block: ChallengeBlock } => p.block !== undefined && !state.done.includes(p.block.id));
  const unansweredQuiz = lesson.blocks.some((b) => b.type === "quiz" && !state.done.includes(b.id));
  const complete = skipped.length === 0 && !unansweredQuiz;

  // The lesson counts as complete once the student reaches the end with
  // every quiz answered and every challenge solved.
  useEffect(() => {
    if (complete) progress.finishLesson(lesson.id);
  }, [complete, lesson.id]);
  return (
    <div className="card finished">
      {complete ? (
        <>
          <div className="big-emoji" aria-hidden>🎉</div>
          <h2>Lesson complete!</h2>
          <p>You finished <b>{lesson.title}</b>.</p>
        </>
      ) : (
        <>
          <div className="big-emoji" aria-hidden>🏁</div>
          <h2>You reached the end!</h2>
          <p>To complete the lesson, come back and solve:</p>
          <ul>
            {skipped.map(({ i, block }) => (
              <li key={block.id}>
                <button className="link" onClick={() => onGo(i)}>{block.title}</button>
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="finished-actions">
        <a className="button secondary" href="#/">🗺️ All lessons</a>
        {next && (
          <a className="button primary" href={href({ page: "lesson", lessonId: next.id })}>
            Next: {next.title} →
          </a>
        )}
      </div>
    </div>
  );
}
