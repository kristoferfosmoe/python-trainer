import { useEffect, useRef, useState } from "react";
import { loadCatalog } from "./content";
import { navigate, useRoute } from "./router";
import { dismissRestored, initSession, signOut, usesTeamPages, useSession, type Me } from "./session";
import { useRunnerStatus } from "./sim/instance";
import { AccountPage, SignInPage, SignUpPage } from "./pages/AuthPages";
import { CourseMap } from "./pages/CourseMap";
import { LessonPage } from "./pages/LessonPage";
import { PlaygroundPage } from "./pages/PlaygroundPage";
import { MemberPage, TeamPage, TeamsPage } from "./pages/TeamPages";
import { ErrorBoundary } from "./components/ErrorBoundary";

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
  const { me, unsaved, signedOut, restored } = useSession();

  const firstRoute = useRef(true);
  useEffect(() => {
    window.scrollTo(0, 0);
    // The "Not you?" note is for the first page; moving on means it's you.
    if (!firstRoute.current) dismissRestored();
    firstRoute.current = false;
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
        {signedOut ? (
          <a className="status status-broken" role="status" href="#/signin" title="Your work is kept until you sign in again.">
            ⚠ Signed out: sign in again to save your work
          </a>
        ) : (
          unsaved && (
            <span className="status status-broken" role="status" title="We'll keep trying to save your work.">
              ⚠ Not saved yet
            </span>
          )
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
        <ErrorBoundary resetKey={JSON.stringify(route)}>
          {me && restored && <NotYou me={me} />}
          {route.page === "map" && <CourseMap />}
          {route.page === "lesson" && <LessonPage lessonId={route.lessonId} pageNumber={route.pageNumber} />}
          {route.page === "playground" && <PlaygroundPage challengeId={route.challengeId} />}
          {route.page === "signin" && <SignInPage />}
          {route.page === "signup" && <SignUpPage />}
          {route.page === "account" && <AccountPage />}
          {route.page === "teams" && <TeamsPage />}
          {route.page === "team" && <TeamPage teamId={route.teamId} />}
          {route.page === "member" && <MemberPage teamId={route.teamId} username={route.username} />}
        </ErrorBoundary>
      </main>
    </div>
  );
}

/** On a shared computer, the last person may still be signed in. */
function NotYou({ me }: { me: Me }) {
  return (
    <div className="feedback welcome-back" role="status">
      <span>
        👋 You're signed in as <span aria-hidden>{me.avatar}</span> <b>{me.display_name}</b>.
      </span>
      <span className="spacer" />
      <button
        className="secondary"
        onClick={async () => {
          await signOut();
          navigate({ page: "signin" });
        }}
      >
        Not you? Switch account
      </button>
      <button className="secondary" onClick={dismissRestored}>That's me</button>
    </div>
  );
}
