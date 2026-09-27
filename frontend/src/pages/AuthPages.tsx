// Sign up (username + PIN), sign in, and the account page.

import { useState } from "react";
import { navigate } from "../router";
import * as session from "../session";

const AVATARS = ["🤖", "🦊", "🐼", "🐙", "🦄", "🐢", "🦖", "🐝", "🦉", "🐬", "🚀", "⚡"];

function pinProblem(pin: string): string | null {
  if (!/^\d{6}$/.test(pin)) return "Your PIN must be exactly 6 numbers.";
  if (new Set(pin).size === 1) return "That PIN is too easy to guess. Try mixing it up.";
  if ("0123456789012".includes(pin) || "9876543210987".includes(pin)) return "That PIN is too easy to guess (counting). Try mixing it up.";
  if (pin.slice(0, 3) === pin.slice(3) || pin.slice(0, 2).repeat(3) === pin) return "That PIN is too easy to guess (it repeats). Try mixing it up.";
  return null;
}

function useSubmit(action: () => Promise<void>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
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
  return { busy, error, setError, submit };
}

export function SignUpPage() {
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [avatar, setAvatar] = useState(AVATARS[0]);
  const [pin, setPin] = useState("");
  const [pin2, setPin2] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [showPin, setShowPin] = useState(false);
  const form = useSubmit(async () => {
    const problem = pinProblem(pin) ?? (pin !== pin2 ? "The two PINs don't match." : null);
    if (problem) throw new Error(problem);
    await session.signUp({ username: username.trim(), pin, display_name: displayName.trim(), avatar, join_code: joinCode.trim() });
    navigate({ page: "map" });
  });

  return (
    <form className="card auth" onSubmit={form.submit}>
      <h1>Sign up</h1>
      <p className="muted">Your progress will be saved, so you can pick up on any computer.</p>

      <label htmlFor="username">Username</label>
      <div className="row">
        <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username"
          required minLength={3} maxLength={20} pattern="[A-Za-z][A-Za-z0-9_]{2,19}" />
        <button type="button" className="secondary" onClick={async () => setUsername(await session.suggestUsername())}
          title="Make up a username">🎲 Make one up</button>
      </div>
      <p className="field-hint">⚠️ Don't use your real name. Pick a made-up name, like BraveOtter42.</p>

      <label htmlFor="display">Nickname (optional)</label>
      <input id="display" value={displayName} onChange={(e) => setDisplayName(e.target.value)} maxLength={40}
        placeholder="What should we call you?" />

      <fieldset className="avatars">
        <legend>Pick an avatar</legend>
        {AVATARS.map((a) => (
          <button key={a} type="button" className={`avatar-choice ${a === avatar ? "chosen" : ""}`}
            onClick={() => setAvatar(a)} aria-pressed={a === avatar} aria-label={`Avatar ${a}`}>{a}</button>
        ))}
      </fieldset>

      <label htmlFor="pin">Make a 6-number PIN</label>
      <input id="pin" className="pin" value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
        type={showPin ? "text" : "password"} inputMode="numeric" maxLength={6} autoComplete="new-password" required />
      <label htmlFor="pin2">Type your PIN again</label>
      <input id="pin2" className="pin" value={pin2} onChange={(e) => setPin2(e.target.value.replace(/\D/g, ""))}
        type={showPin ? "text" : "password"} inputMode="numeric" maxLength={6} autoComplete="new-password" required />
      <label className="check">
        <input type="checkbox" checked={showPin} onChange={(e) => setShowPin(e.target.checked)} /> Show PIN
      </label>
      <p className="field-hint">Keep your PIN secret. Your coach can give you a new one if you forget it.</p>

      <label htmlFor="team">Team code (optional)</label>
      <input id="team" value={joinCode} onChange={(e) => setJoinCode(e.target.value.toUpperCase())} maxLength={6}
        placeholder="From your coach, like K7Q2MX" />

      {form.error && <p className="form-error" role="alert">{form.error}</p>}
      <button className="primary big" disabled={form.busy}>{form.busy ? "Signing up…" : "Sign up"}</button>
      <p className="muted">Already have an account? <a href="#/signin">Sign in</a></p>
    </form>
  );
}

export function SignInPage() {
  const [username, setUsername] = useState("");
  const [secret, setSecret] = useState("");
  const form = useSubmit(async () => {
    await session.signIn(username.trim(), secret);
    navigate({ page: "map" });
  });
  return (
    <form className="card auth" onSubmit={form.submit}>
      <h1>Sign in</h1>
      <label htmlFor="username">Username</label>
      <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
      <label htmlFor="secret">PIN <span className="muted">(coaches: your password)</span></label>
      <input id="secret" value={secret} onChange={(e) => setSecret(e.target.value)} type="password" autoComplete="current-password" required />
      {form.error && <p className="form-error" role="alert">{form.error}</p>}
      <button className="primary big" disabled={form.busy}>{form.busy ? "Signing in…" : "Sign in"}</button>
      <p className="muted">New here? <a href="#/signup">Sign up</a></p>
    </form>
  );
}

export function AccountPage() {
  const { me } = session.useSession();
  const [code, setCode] = useState("");
  const join = useSubmit(async () => {
    await session.joinTeam(code.trim());
    setCode("");
  });
  if (!me) {
    return (
      <div className="card auth">
        <h1>You're not signed in</h1>
        <p><a href="#/signin">Sign in</a> or <a href="#/signup">sign up</a>.</p>
      </div>
    );
  }
  return (
    <div className="card auth">
      <h1><span aria-hidden>{me.avatar}</span> {me.display_name}</h1>
      <p className="muted">Username: <b>{me.username}</b></p>
      <h2>Teams</h2>
      {me.teams.length === 0 ? (
        <p className="muted">You're not on a team yet.</p>
      ) : (
        <ul className="team-list">
          {me.teams.map((t) => (
            <li key={t.id}>{t.name} <span className="badge">{t.role}</span></li>
          ))}
        </ul>
      )}
      <form onSubmit={join.submit} className="row">
        <input aria-label="Team code" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())}
          maxLength={6} placeholder="Team code" required />
        <button className="secondary" disabled={join.busy}>Join a team</button>
      </form>
      {join.error && <p className="form-error" role="alert">{join.error}</p>}
      {me.is_staff && (
        <p><a className="button secondary" href="/admin/">🛠 Open the admin (lessons, teams, students)</a></p>
      )}
      <button
        className="secondary"
        onClick={async () => {
          await session.signOut();
          navigate({ page: "map" });
        }}
      >
        Sign out
      </button>
    </div>
  );
}
