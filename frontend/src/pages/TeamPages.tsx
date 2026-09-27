// The coach tools: your teams, a team's progress and accounts, and one
// student's work. Mentors see the same pages without the buttons that change things.

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api";
import * as coach from "../coach";
import type { ChallengeWork, Dashboard, LoginCard, MemberDetail, StudentRow, TeamListing } from "../coach";
import { CodeView } from "../components/CodeView";
import { LoginCards } from "../components/LoginCards";
import { RobotForm } from "../components/RobotForm";
import { allLessons, robot, type LessonEntry } from "../content";
import { trainerRobot } from "../pybricks";
import { href, navigate } from "../router";
import { refreshMe, useSession, type LessonProgress } from "../session";

// --- Small helpers -------------------------------------------------------------------------

/** Load something from the server, with a way to load it again. */
function useLoad<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => {
    load().then(
      (result) => {
        setData(result);
        setError(null);
      },
      (e: Error) => setError(e.message),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(reload, [reload]);
  return { data, error, reload };
}

/** Run a button's action, showing "busy" and any error. */
function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, run };
}

export function timeAgo(iso: string | null, now = Date.now()): string {
  if (!iso) return "never";
  const minutes = Math.round((now - new Date(iso).getTime()) / 60000);
  if (minutes < 2) return "just now";
  if (minutes < 60) return `${minutes} minutes ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days < 14) return days === 1 ? "yesterday" : `${days} days ago`;
  return new Date(iso).toLocaleDateString();
}

/** Coaches know students by their nicknames. */
const byName = <T extends { display_name: string }>(people: T[]) =>
  [...people].sort((a, b) => a.display_name.localeCompare(b.display_name, undefined, { sensitivity: "base" }));

type Status = "new" | "started" | "done";

function statusOf(progress: LessonProgress | undefined): Status {
  if (!progress) return "new";
  if (progress.finished) return "done";
  return progress.page > 0 || progress.done.length > 0 ? "started" : "new";
}

/** Lessons grouped by unit, in course order. */
interface UnitGroup {
  key: string;
  title: string;
  icon: string;
  number: number;
  lessons: LessonEntry[];
}

function unitsOfLessons(): UnitGroup[] {
  const units = new Map<string, UnitGroup>();
  for (const entry of allLessons()) {
    const key = `${entry.course.id}/${entry.unit.id}`;
    const unit = units.get(key) ?? {
      key,
      title: entry.unit.title,
      icon: entry.unit.icon ?? "",
      number: entry.course.units.findIndex((u) => u.id === entry.unit.id) + 1,
      lessons: [],
    };
    unit.lessons.push(entry);
    units.set(key, unit);
  }
  return [...units.values()];
}

function NotAllowed({ error }: { error: string }) {
  return (
    <div className="card auth">
      <h1>Can't show this page</h1>
      <p>{error}</p>
      <p><a href={href({ page: "teams" })}>← Your teams</a></p>
    </div>
  );
}

const Loading = () => <p className="splash">Loading…</p>;

// --- Your teams ---------------------------------------------------------------------------------

export function TeamsPage() {
  const { me } = useSession();
  const { data, error, reload } = useLoad<TeamListing>(() => coach.listTeams(), [me?.username]);
  const [name, setName] = useState("");
  const [season, setSeason] = useState("");
  const make = useAction();

  if (!me) {
    return (
      <div className="card auth">
        <h1>Teams</h1>
        <p>Coaches: <a href={href({ page: "signin" })}>sign in</a> with your coach account to see your teams.</p>
      </div>
    );
  }
  if (error) return <NotAllowed error={error} />;
  if (!data) return <Loading />;

  return (
    <div className="coach">
      <section className="card">
        <h1>👥 Your teams</h1>
        {data.teams.length === 0 ? (
          <p className="muted">You don't lead a team yet.{data.can_create ? " Make one below." : " Ask your coach to make you a mentor."}</p>
        ) : (
          <ul className="team-cards">
            {data.teams.map((team) => (
              <li key={team.id}>
                <a className="team-card" href={href({ page: "team", teamId: team.id })}>
                  <span className="team-card-name">{team.name}</span>
                  <span className="muted">
                    {team.season && `${team.season} · `}
                    {team.students} student{team.students === 1 ? "" : "s"}
                  </span>
                  <span className="badge">{team.role}</span>
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>

      {data.can_create && (
        <form
          className="card stack"
          onSubmit={(e) => {
            e.preventDefault();
            void make.run(async () => {
              const team = await coach.createTeam(name.trim(), season.trim());
              await refreshMe();
              setName("");
              setSeason("");
              reload();
              navigate({ page: "team", teamId: team.id });
            });
          }}
        >
          <h2>Make a team</h2>
          <div className="row wrap">
            <label>
              Team name
              <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} placeholder="Brick Builders" />
            </label>
            <label>
              Season (optional)
              <input value={season} onChange={(e) => setSeason(e.target.value)} maxLength={40} placeholder="2026-27" />
            </label>
          </div>
          {make.error && <p className="form-error" role="alert">{make.error}</p>}
          <div><button className="primary" disabled={make.busy}>{make.busy ? "Making…" : "Make team"}</button></div>
        </form>
      )}
    </div>
  );
}

// --- One team ------------------------------------------------------------------------------------

export function TeamPage({ teamId }: { teamId: number }) {
  const { data, error, reload } = useLoad<Dashboard>(() => coach.loadDashboard(teamId), [teamId]);
  if (error) return <NotAllowed error={error} />;
  if (!data) return <Loading />;
  const manage = data.can_manage;

  return (
    <div className="coach">
      <p className="back-link"><a href={href({ page: "teams" })}>← Your teams</a></p>
      <TeamHeader data={data} onChange={reload} />
      <ProgressTable data={data} />
      {manage && <AddStudents data={data} onAdded={reload} />}
      <Leaders data={data} />
      <section className="card">
        <h2>🤖 Our robot</h2>
        <p className="muted">
          Lessons use the Trainer Bot. When your students press <b>Run on your robot</b>, their code is changed to
          match the robot you describe here: its ports and its wheel sizes.
        </p>
        <RobotForm
          robot={data.team.robot}
          trainer={trainerRobot(robot())}
          editable={manage}
          onSave={async (next) => {
            await coach.changeTeam(teamId, { robot: next ?? {} });
            await refreshMe();
            reload();
          }}
        />
      </section>
      {manage && <TeamSettings data={data} onChange={reload} />}
    </div>
  );
}

function TeamHeader({ data, onChange }: { data: Dashboard; onChange: () => void }) {
  const code = useAction();
  return (
    <section className="card team-head">
      <div>
        <h1>{data.team.name}</h1>
        <p className="muted">
          {data.team.season && `${data.team.season} · `}You're {data.role === "staff" ? "a site admin" : `a ${data.role}`}
          {!data.can_manage && " (you can look, but only coaches change things)"}
        </p>
      </div>
      <div className="join-code">
        <span className="muted">Join code</span>
        <span className="join-code-value" data-testid="join-code">{data.team.join_code}</span>
        <span className="field-hint">Students type it when they sign up.</span>
        {data.can_manage && (
          <button
            className="link"
            disabled={code.busy}
            onClick={() => {
              if (!window.confirm("Make a new join code? The old one will stop working. Students already on the team stay.")) return;
              void code.run(async () => {
                await coach.newJoinCode(data.team.id);
                onChange();
              });
            }}
          >
            Make a new code
          </button>
        )}
        {code.error && <p className="form-error" role="alert">{code.error}</p>}
      </div>
    </section>
  );
}

function ProgressTable({ data }: { data: Dashboard }) {
  const units = unitsOfLessons();
  const total = units.reduce((n, u) => n + u.lessons.length, 0);
  const finished = (student: StudentRow, lessons: LessonEntry[]) =>
    lessons.filter((e) => statusOf(student.lessons[e.lesson.id]) === "done").length;
  const started = (student: StudentRow, lessons: LessonEntry[]) =>
    lessons.some((e) => statusOf(student.lessons[e.lesson.id]) !== "new");

  return (
    <section className="card">
      <h2>📈 Progress</h2>
      {data.students.length === 0 ? (
        <p className="muted">
          No students yet. Share the join code{data.can_manage ? ", or add students below" : ""}.
        </p>
      ) : (
        <div className="table-scroll">
          <table className="progress-table">
            <thead>
              <tr>
                <th>Student</th>
                <th>Last active</th>
                <th>Lessons</th>
                {units.map((unit) => (
                  <th key={unit.key} className="unit-col" title={`Unit ${unit.number}: ${unit.title}`}>
                    <span aria-hidden>{unit.icon}</span>
                    <span className="unit-col-num">{unit.number}</span>
                  </th>
                ))}
                <th title="Playground challenges solved">🎮</th>
              </tr>
            </thead>
            <tbody>
              {byName(data.students).map((student) => (
                <tr key={student.username}>
                  <td>
                    <a href={href({ page: "member", teamId: data.team.id, username: student.username })} className="person">
                      <span aria-hidden>{student.avatar}</span> {student.display_name}
                      {student.display_name !== student.username && <span className="muted"> ({student.username})</span>}
                    </a>
                    {student.locked && <span className="badge danger" title="Too many wrong PINs">🔒 locked</span>}
                  </td>
                  <td className="muted nowrap">{timeAgo(student.last_active)}</td>
                  <td className="nowrap">{finished(student, units.flatMap((u) => u.lessons))} / {total}</td>
                  {units.map((unit) => {
                    const done = finished(student, unit.lessons);
                    const state = done === unit.lessons.length ? "done" : started(student, unit.lessons) ? "started" : "new";
                    return (
                      <td key={unit.key} className={`unit-cell ${state}`}
                        title={`Unit ${unit.number}: ${done} of ${unit.lessons.length} lessons finished`}>
                        {state === "new" ? "" : state === "done" ? "✔" : `${done}/${unit.lessons.length}`}
                      </td>
                    );
                  })}
                  <td className="nowrap">{student.solved}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function AddStudents({ data, onAdded }: { data: Dashboard; onAdded: () => void }) {
  const [text, setText] = useState("");
  const [cards, setCards] = useState<LoginCard[]>([]);
  const [made, setMade] = useState<{ done: number; of: number } | null>(null);
  const add = useAction();
  const list = coach.parseStudentList(text);
  const room = Math.max(0, data.max_members - data.members);

  if (room === 0 && cards.length === 0) {
    return (
      <section className="card stack">
        <h2>➕ Add students</h2>
        <p className="feedback warning" role="status">
          Your team has {data.max_members} members, the most a team can have. Remove a member before adding another:
          open their page from the list above and press <b>Remove from team</b>.
        </p>
      </section>
    );
  }
  const tooMany = list.length > room;

  return (
    <section className="card stack">
      <h2>➕ Add students</h2>
      <p className="muted">
        Type one student per line: a nickname, like a first name or initials (no last names). Each student gets a
        made-up username and a PIN. To pick a username yourself, add it after a comma: <code>Sam, RoboSam</code>.
      </p>
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          void add.run(async () => {
            setCards([]);
            setMade({ done: 0, of: list.length });
            try {
              await coach.createStudents(data.team.id, list, (sofar) => {
                setCards(sofar);
                setMade({ done: sofar.length, of: list.length });
              });
              setText("");
            } finally {
              setMade(null);
              onAdded();
            }
          });
        }}
      >
        <label htmlFor="new-students" className="sr-only">Students to add</label>
        <textarea id="new-students" rows={5} value={text} onChange={(e) => setText(e.target.value)}
          placeholder={"Sam\nPriya\nJ.T."} />
        {tooMany && (
          <p className="feedback warning" role="status">
            Your team has room for {room} more member{room === 1 ? "" : "s"} (a team can have {data.max_members}).
            Remove members before adding more, or add fewer.
          </p>
        )}
        <div className="row">
          <button className="primary" disabled={add.busy || list.length === 0 || tooMany}>
            {made ? `Making accounts… ${made.done} of ${made.of}` : `Make ${list.length || ""} account${list.length === 1 ? "" : "s"}`}
          </button>
          <span className="muted">{data.members} of {data.max_members} places on the team are used.</span>
        </div>
      </form>
      {add.error && <p className="form-error" role="alert">{add.error}</p>}
      {cards.length > 0 && <LoginCards cards={cards} teamName={data.team.name} />}
    </section>
  );
}

function Leaders({ data }: { data: Dashboard }) {
  return (
    <section className="card">
      <h2>🧑‍🏫 Coaches and mentors</h2>
      <p className="muted">Mentors are older students who help. They can see everyone's work and the answers, but can't change accounts.</p>
      <ul className="people">
        {byName(data.leaders).map((person) => (
          <li key={person.username}>
            <span aria-hidden>{person.avatar}</span>{" "}
            {data.can_manage && person.role === "mentor" ? (
              <a href={href({ page: "member", teamId: data.team.id, username: person.username })}>{person.display_name}</a>
            ) : (
              person.display_name
            )}
            <span className="badge">{person.role}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function TeamSettings({ data, onChange }: { data: Dashboard; onChange: () => void }) {
  const [name, setName] = useState(data.team.name);
  const [season, setSeason] = useState(data.team.season);
  const save = useAction();
  const [saved, setSaved] = useState(false);
  return (
    <form
      className="card stack"
      onSubmit={(e) => {
        e.preventDefault();
        setSaved(false);
        void save.run(async () => {
          await coach.changeTeam(data.team.id, { name, season });
          await refreshMe();
          onChange();
          setSaved(true);
        });
      }}
    >
      <h2>⚙️ Team details</h2>
      <div className="row wrap">
        <label>
          Team name
          <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} />
        </label>
        <label>
          Season
          <input value={season} onChange={(e) => setSeason(e.target.value)} maxLength={40} placeholder="2026-27" />
        </label>
      </div>
      {save.error && <p className="form-error" role="alert">{save.error}</p>}
      {saved && <p className="form-ok" role="status">Saved.</p>}
      <div><button className="secondary" disabled={save.busy}>Save</button></div>
    </form>
  );
}

// --- One student ------------------------------------------------------------------------------------

export function MemberPage({ teamId, username }: { teamId: number; username: string }) {
  const { data, error, reload } = useLoad<MemberDetail>(() => coach.loadMember(teamId, username), [teamId, username]);
  if (error) return <NotAllowed error={error} />;
  if (!data) return <Loading />;
  const { student } = data;

  return (
    <div className="coach">
      <p className="back-link"><a href={href({ page: "team", teamId })}>← {data.team.name}</a></p>
      <section className="card team-head">
        <div>
          <h1><span aria-hidden>{student.avatar}</span> {student.display_name}</h1>
          <p className="muted">
            Username <b>{student.username}</b> · {student.role} · last active {timeAgo(student.last_active)}
            {student.locked && <span className="badge danger">🔒 locked after too many wrong PINs</span>}
          </p>
        </div>
      </section>
      {data.can_manage && <AccountActions data={data} onChange={reload} />}
      <LessonList data={data} />
      <section className="card">
        <h2>🧩 Challenges</h2>
        {data.challenges.length === 0 ? (
          <p className="muted">No challenges tried yet.</p>
        ) : (
          <ul className="work-list">
            {data.challenges.map((work) => <ChallengeItem key={work.key} work={work} />)}
          </ul>
        )}
      </section>
    </div>
  );
}

function AccountActions({ data, onChange }: { data: MemberDetail; onChange: () => void }) {
  const { student, team } = data;
  const [card, setCard] = useState<LoginCard | null>(null);
  const [askPassword, setAskPassword] = useState(false);
  const [password, setPassword] = useState("");
  const action = useAction();
  const mentor = student.role === "mentor";

  // Whoever has a new PIN can sign in as the student, so the server may ask
  // the coach to type their password again first.
  const makePin = async () => {
    try {
      setCard(await coach.newPin(team.id, student.username));
    } catch (e) {
      if (e instanceof ApiError && e.code === "password_needed") {
        setAskPassword(true);
        return;
      }
      throw e;
    }
    onChange();
  };
  const closePasswordCheck = () => {
    setAskPassword(false);
    setPassword("");
  };

  return (
    <section className="card stack">
      <h2>🔑 Account</h2>
      <div className="row wrap">
        <button
          className="secondary"
          disabled={action.busy}
          onClick={() => {
            if (!window.confirm(`Make a new PIN for ${student.display_name}? Their old PIN will stop working.`)) return;
            void action.run(makePin);
          }}
        >
          🔑 Make a new PIN
        </button>
        {student.locked && (
          <button className="secondary" disabled={action.busy}
            onClick={() => void action.run(async () => {
              await coach.unlock(team.id, student.username);
              onChange();
            })}>
            🔓 Unlock
          </button>
        )}
        <button className="secondary" disabled={action.busy}
          onClick={() => void action.run(async () => {
            await coach.setRole(team.id, student.username, mentor ? "student" : "mentor");
            onChange();
          })}>
          {mentor ? "Make a student again" : "🎓 Make a mentor"}
        </button>
        <button
          className="secondary danger"
          disabled={action.busy}
          onClick={() => {
            if (!window.confirm(`Take ${student.display_name} off ${team.name}? Their account and work are kept.`)) return;
            void action.run(async () => {
              await coach.removeMember(team.id, student.username);
              navigate({ page: "team", teamId: team.id });
            });
          }}
        >
          Remove from team
        </button>
      </div>
      {askPassword && (
        <form
          className="password-check"
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(async () => {
              await coach.confirmPassword(password);
              closePasswordCheck();
              await makePin();
            });
          }}
        >
          <p>🔒 For safety, type your password to make {student.display_name} a new PIN.</p>
          <div className="row wrap">
            <input type="password" aria-label="Your password" placeholder="Your password" autoComplete="current-password"
              value={password} onChange={(e) => setPassword(e.target.value)} required autoFocus />
            <button className="primary" disabled={action.busy}>Make the new PIN</button>
            <button type="button" className="secondary" onClick={closePasswordCheck}>Cancel</button>
          </div>
        </form>
      )}
      {action.error && <p className="form-error" role="alert">{action.error}</p>}
      {card && <LoginCards cards={[card]} teamName={team.name} />}
    </section>
  );
}

function LessonList({ data }: { data: MemberDetail }) {
  const units = unitsOfLessons();
  const label = (progress: MemberDetail["lessons"][string] | undefined) => {
    const status = statusOf(progress);
    if (status === "done") return "✔ Finished";
    if (status === "started") return `In progress (page ${progress!.page + 1})`;
    return "Not started";
  };
  return (
    <section className="card">
      <h2>📚 Lessons</h2>
      <div className="table-scroll">
        <table className="lesson-table">
          <tbody>
            {units.map((unit) => (
              unit.lessons.map((entry, i) => {
                const progress = data.lessons[entry.lesson.id];
                const status = statusOf(progress);
                return (
                  <tr key={entry.lesson.id} className={status}>
                    {i === 0 && (
                      <th rowSpan={unit.lessons.length} className="unit-name">
                        {unit.icon} Unit {unit.number}: {unit.title}
                      </th>
                    )}
                    <td><a href={href({ page: "lesson", lessonId: entry.lesson.id })}>{entry.lesson.title}</a></td>
                    <td className={`lesson-status ${status}`}>{label(progress)}</td>
                    <td className="muted nowrap">{progress ? timeAgo(progress.updated_at) : ""}</td>
                  </tr>
                );
              })
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ChallengeItem({ work }: { work: ChallengeWork }) {
  const [open, setOpen] = useState(false);
  const icon = work.passed ? "✔" : work.attempts > 0 ? "✗" : "✎";
  const status = work.passed ? "Solved" : work.attempts > 0 ? "Not solved yet" : "Started, never run";
  const lastGoals = work.last_goals.length
    ? `${work.last_goals.filter((g) => g.passed).length} of ${work.last_goals.length} goals passed on the last run`
    : null;
  const codes: { title: string; code: string }[] = [];
  if (work.last_code !== null) codes.push({ title: `Last run${work.last_passed ? " (passed)" : ""}`, code: work.last_code });
  if (work.passed_code !== null && work.passed_code !== work.last_code) codes.push({ title: "The code that passed", code: work.passed_code });
  if (work.draft !== null && work.draft !== work.last_code) codes.push({ title: "In the editor now", code: work.draft });

  return (
    <li>
      <details onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
        <summary className="work-summary">
          <span className={`work-icon ${work.passed ? "pass" : work.attempts > 0 ? "fail" : ""}`} aria-label={status}>{icon}</span>
          <span className="work-title">{work.title}</span>
          <span className="muted">{work.where}</span>
          <span className="spacer" />
          <span className="muted nowrap">
            {work.attempts} run{work.attempts === 1 ? "" : "s"} · {timeAgo(work.last_at)}
          </span>
        </summary>
        {open && (
          <div className="work-body">
            <p className="muted">
              {status}.{lastGoals && ` ${lastGoals}.`}
              {work.lesson && <> <a href={href({ page: "lesson", lessonId: work.lesson })}>Open the lesson →</a></>}
            </p>
            {codes.map(({ title, code }) => (
              <div key={title} className="work-code">
                <h4>{title}</h4>
                {code ? <CodeView code={code} label={`${work.title}: ${title}`} /> : <p className="muted">(No code saved: solved as a guest.)</p>}
              </div>
            ))}
          </div>
        )}
      </details>
    </li>
  );
}
