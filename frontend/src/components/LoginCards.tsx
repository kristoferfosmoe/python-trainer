// Sign-in cards for new accounts and new PINs, to print and hand out.
// PINs are only shown once, so the coach is told to print or copy them now.

import type { LoginCard } from "../coach";

export function LoginCards({ cards, teamName }: { cards: LoginCard[]; teamName: string }) {
  const site = window.location.origin;
  return (
    <div className="login-cards-wrap">
      <div className="feedback warning login-cards-note">
        <span>
          ⚠️ <b>Print these now or write them down.</b> PINs are only shown once. You can always make a new PIN later.
        </span>
        <button type="button" className="secondary" onClick={() => window.print()}>🖨 Print cards</button>
      </div>
      <div className="login-cards print-area" aria-label="Sign-in cards">
        {cards.map((card) => (
          <div className="login-card" key={card.username}>
            <div className="login-card-title">🤖 Python Trainer</div>
            <div className="login-card-name">{card.display_name}</div>
            <dl>
              <dt>Website</dt>
              <dd>{site}</dd>
              <dt>Username</dt>
              <dd className="mono" data-testid="card-username">{card.username}</dd>
              <dt>PIN</dt>
              <dd className="mono" data-testid="card-pin">{card.pin}</dd>
            </dl>
            <div className="login-card-team">Team: {teamName}</div>
            <p className="login-card-note">Keep your PIN secret. If you forget it, your coach can make a new one.</p>
          </div>
        ))}
      </div>
    </div>
  );
}
