import { useEffect, useState } from "react";
import { loadCatalog } from "./content";
import { useRoute } from "./router";
import { initSession, usesTeamPages, useSession } from "./session";
import { useRunnerStatus } from "./sim/instance";
import { AccountPage, SignInPage, SignUpPage } from "./pages/AuthPages";
import { CourseMap } from "./pages/CourseMap";
import { LessonPage } from "./pages/LessonPage";
import { PlaygroundPage } from "./pages/PlaygroundPage";
import { MemberPage, TeamPage, TeamsPage } from "./pages/TeamPages";

export default function App() {
  const [loaded, setLoaded] = useState<"loading" | "ready" | { error: string }>("loading");

  useEffect(() => {
    Promise.all([loadCatalog(), initSession()]).then(
      () => setLoaded("ready"),
      (error: Error) => setLoaded({ error: error.message }),
    );
  }, []);

  if (loaded === "loading") {
    return <div className="splash">🤖 Loading Python Trainer…</div>;
  }
  if (loaded !== "ready") {
    return (
      <div className="card narrow">
        <h1>Python Trainer can't start</h1>
        <p>{loaded.error}</p>
        <button className="primary" onClick={() => window.location.reload()}>Try again</button>
      </div>
    );
  }
  return <Shell />;
}

function Shell() {
  const route = useRoute();
  const status = useRunnerStatus();
  const { me, unsaved } = useSession();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [route]);

  const inPlayground = route.page === "playground";
  const inTeams = route.page === "teams" || route.page === "team" || route.page === "member";
  const inLessons = !inPlayground && !inTeams;
  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="#/">
          <span aria-hidden>🤖</span> Python Trainer
        </a>
        <nav className="main-nav" aria-label="Main">
          <a href="#/" className={inLessons ? "active" : ""} aria-current={inLessons ? "page" : undefined}>
            🗺️ Lessons
          </a>
          <a href="#/playground" className={inPlayground ? "active" : ""} aria-current={inPlayground ? "page" : undefined}>
            🎮 Playground
          </a>
          {(usesTeamPages(me) || inTeams) && (
            <a href="#/teams" className={inTeams ? "active" : ""} aria-current={inTeams ? "page" : undefined}>
              👥 Teams
            </a>
          )}
        </nav>
        {unsaved && (
          <span className="status status-broken" role="status" title="We'll keep trying to save your work.">
            ⚠ Not saved yet
          </span>
        )}
        <span className={`status status-${status}`} role="status">
          {status === "loading" && "Starting Python…"}
          {status === "ready" && "Python ready"}
          {status === "running" && "Running…"}
          {status === "broken" && "Python didn't start. Reload the page."}
        </span>
        {me ? (
          <a className="account-chip" href="#/account" title="Your account">
            <span aria-hidden>{me.avatar}</span> {me.display_name}
          </a>
        ) : (
          <a className="button secondary" href="#/signin">Sign in</a>
        )}
      </header>
      <main>
        {route.page === "map" && <CourseMap />}
        {route.page === "lesson" && <LessonPage lessonId={route.lessonId} pageNumber={route.pageNumber} />}
        {route.page === "playground" && <PlaygroundPage challengeId={route.challengeId} />}
        {route.page === "signin" && <SignInPage />}
        {route.page === "signup" && <SignUpPage />}
        {route.page === "account" && <AccountPage />}
        {route.page === "teams" && <TeamsPage />}
        {route.page === "team" && <TeamPage teamId={route.teamId} />}
        {route.page === "member" && <MemberPage teamId={route.teamId} username={route.username} />}
      </main>
    </div>
  );
}
