import { useEffect } from "react";
import { allLessons } from "./content";
import { paginate } from "./lessonPages";
import { useRoute } from "./router";
import { useRunnerStatus } from "./sim/instance";
import { CourseMap } from "./pages/CourseMap";
import { LessonPage } from "./pages/LessonPage";
import { PlaygroundPage } from "./pages/PlaygroundPage";

// Test hook: where each lesson's challenge pages are, for browser tests.
if (import.meta.env.DEV) {
  (window as unknown as { __course: object }).__course = allLessons.map(({ lesson }) => ({
    id: lesson.id,
    challengePages: paginate(lesson.blocks)
      .map((page, i) => ({ page: i + 1, block: page.find((b) => b.type === "challenge") }))
      .filter((p) => p.block && "goals" in p.block && p.block.goals?.length)
      .map((p) => p.page),
  }));
}

export default function App() {
  const route = useRoute();
  const status = useRunnerStatus();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [route]);

  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="#/">
          <span aria-hidden>🤖</span> Python Trainer
        </a>
        <nav className="main-nav" aria-label="Main">
          <a href="#/" className={route.page !== "playground" ? "active" : ""} aria-current={route.page !== "playground" ? "page" : undefined}>
            🗺️ Lessons
          </a>
          <a href="#/playground" className={route.page === "playground" ? "active" : ""} aria-current={route.page === "playground" ? "page" : undefined}>
            🎮 Playground
          </a>
        </nav>
        <span className={`status status-${status}`} role="status">
          {status === "loading" && "Starting Python…"}
          {status === "ready" && "Python ready"}
          {status === "running" && "Running…"}
          {status === "broken" && "Python didn't start. Reload the page."}
        </span>
      </header>
      <main>
        {route.page === "map" && <CourseMap />}
        {route.page === "lesson" && <LessonPage lessonId={route.lessonId} pageNumber={route.pageNumber} />}
        {route.page === "playground" && <PlaygroundPage challengeId={route.challengeId} />}
      </main>
    </div>
  );
}
