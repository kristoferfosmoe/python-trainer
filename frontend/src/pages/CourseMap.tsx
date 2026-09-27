import { allLessons, useCatalog } from "../content";
import { lessonStatus, useProgress } from "../progress";
import { href } from "../router";
import { useSession } from "../session";

export function CourseMap() {
  const catalog = useCatalog();
  const store = useProgress();
  const { me } = useSession();
  const entries = allLessons();
  const statuses = new Map(entries.map(({ lesson }) => [lesson.id, lessonStatus(lesson, store[lesson.id])]));

  return (
    <div className="course">
      {!me && (
        <section className="card guest-banner">
          <span>
            👋 You're a guest, so your progress is only saved on this computer. <b>Sign up</b> to keep it safe
            and join your team.
          </span>
          <span className="banner-actions">
            <a className="button primary" href={href({ page: "signup" })}>Sign up</a>
            <a className="button secondary" href={href({ page: "signin" })}>Sign in</a>
          </span>
        </section>
      )}

      {catalog.courses.map((course) => {
        const lessons = entries.filter((e) => e.course.id === course.id);
        const doneCount = lessons.filter(({ lesson }) => statuses.get(lesson.id) === "done").length;
        const nextUp = lessons.find(({ lesson }) => statuses.get(lesson.id) !== "done");
        return (
          <div className="course-block" key={course.id}>
            <section className="card hero">
              <div>
                <h1>{course.title}</h1>
                <p>{course.summary}</p>
                <div className="progress-bar" role="progressbar" aria-label={`${course.title} progress`}
                  aria-valuemin={0} aria-valuemax={lessons.length} aria-valuenow={doneCount}>
                  <span style={{ width: `${lessons.length ? (doneCount / lessons.length) * 100 : 0}%` }} />
                </div>
                <p className="progress-text">
                  {doneCount} of {lessons.length} lessons complete
                </p>
              </div>
              {nextUp && (
                <a className="button primary big" href={href({ page: "lesson", lessonId: nextUp.lesson.id })}>
                  {doneCount === 0 && statuses.get(nextUp.lesson.id) === "new" ? "▶ Start" : "▶ Continue"}: {nextUp.lesson.title}
                </a>
              )}
            </section>

            {course.units.map((unit, u) => (
              <section className="unit" key={unit.id} aria-labelledby={`unit-${course.id}-${unit.id}`}>
                <h2 id={`unit-${course.id}-${unit.id}`}>
                  <span className="unit-icon" aria-hidden>{unit.icon}</span> Unit {u + 1}: {unit.title}
                </h2>
                <p className="unit-summary">{unit.summary}</p>
                <ol className="lesson-tiles">
                  {unit.lessons.map((lesson) => {
                    const entry = lessons.find((l) => l.lesson.id === lesson.id)!;
                    const status = statuses.get(lesson.id);
                    const isNext = nextUp?.lesson.id === lesson.id;
                    return (
                      <li key={lesson.id}>
                        <a className={`lesson-tile ${status} ${isNext ? "next" : ""}`} href={href({ page: "lesson", lessonId: lesson.id })}>
                          <span className="tile-num" aria-hidden>{status === "done" ? "✔" : entry.number}</span>
                          <span className="tile-text">
                            <span className="tile-title">{lesson.title}</span>
                            <span className="tile-summary">{lesson.summary}</span>
                          </span>
                          {isNext && <span className="tile-badge">Next up</span>}
                          {status === "started" && !isNext && <span className="tile-badge muted">In progress</span>}
                          <span className="sr-only">{status === "done" ? "(complete)" : status === "started" ? "(in progress)" : ""}</span>
                        </a>
                      </li>
                    );
                  })}
                </ol>
              </section>
            ))}
          </div>
        );
      })}

      <section className="card promo">
        <div>
          <h2>🎮 Playground</h2>
          <p>Free practice: robot challenges, from parking to line following.</p>
        </div>
        <a className="button secondary" href={href({ page: "playground" })}>Open the playground →</a>
      </section>
    </div>
  );
}
