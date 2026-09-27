import { allLessons, course } from "../content";
import { lessonStatus, useProgress } from "../progress";
import { href } from "../router";

export function CourseMap() {
  const store = useProgress();
  const statuses = new Map(allLessons.map(({ lesson }) => [lesson.id, lessonStatus(lesson, store[lesson.id])]));
  const doneCount = [...statuses.values()].filter((s) => s === "done").length;
  const nextUp = allLessons.find(({ lesson }) => statuses.get(lesson.id) !== "done");

  return (
    <div className="course">
      <section className="card hero">
        <div>
          <h1>{course.title}</h1>
          <p>{course.summary}</p>
          <div className="progress-bar" role="progressbar" aria-valuemin={0} aria-valuemax={allLessons.length} aria-valuenow={doneCount}>
            <span style={{ width: `${(doneCount / allLessons.length) * 100}%` }} />
          </div>
          <p className="progress-text">
            {doneCount} of {allLessons.length} lessons complete
          </p>
        </div>
        {nextUp && (
          <a className="button primary big" href={href({ page: "lesson", lessonId: nextUp.lesson.id })}>
            {doneCount === 0 && statuses.get(nextUp.lesson.id) === "new" ? "▶ Start" : "▶ Continue"}: {nextUp.lesson.title}
          </a>
        )}
      </section>

      {course.units.map((unit, u) => (
        <section className="unit" key={unit.id} aria-labelledby={`unit-${unit.id}`}>
          <h2 id={`unit-${unit.id}`}>
            <span className="unit-icon" aria-hidden>{unit.icon}</span> Unit {u + 1}: {unit.title}
          </h2>
          <p className="unit-summary">{unit.summary}</p>
          <ol className="lesson-tiles">
            {unit.lessons.map((lesson) => {
              const entry = allLessons.find((l) => l.lesson.id === lesson.id)!;
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

      <section className="card promo">
        <div>
          <h2>🎮 Playground</h2>
          <p>Free practice: seven robot challenges, from parking to line following.</p>
        </div>
        <a className="button secondary" href={href({ page: "playground" })}>Open the playground →</a>
      </section>
    </div>
  );
}
