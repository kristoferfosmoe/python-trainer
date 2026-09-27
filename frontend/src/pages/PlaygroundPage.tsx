import { useState } from "react";
import { challenges } from "../content";
import { href } from "../router";
import * as storage from "../storage";
import { ChallengeWorkspace } from "../components/ChallengeWorkspace";

export function PlaygroundPage({ challengeId }: { challengeId?: string }) {
  const [solved, setSolved] = useState(storage.solvedChallenges);
  const challenge =
    challenges.find((c) => c.id === challengeId) ??
    challenges.find((c) => c.id === storage.lastChallenge()) ??
    challenges[0];
  if (challengeId && challenge.id === challengeId) storage.saveLastChallenge(challenge.id);

  return (
    <>
      <nav className="challenges" aria-label="Challenges">
        {challenges.map((c, i) => (
          <a
            key={c.id}
            className={`chip ${c.id === challenge.id ? "active" : ""}`}
            href={href({ page: "playground", challengeId: c.id })}
            aria-current={c.id === challenge.id ? "page" : undefined}
          >
            <span className="chip-num">{i + 1}</span> {c.title}
            {solved.has(c.id) && <span className="chip-done" aria-label="solved">✔</span>}
          </a>
        ))}
      </nav>
      <ChallengeWorkspace
        key={challenge.id}
        challenge={challenge}
        codeKey={challenge.id}
        onSolved={() => {
          storage.markSolved(challenge.id);
          setSolved(storage.solvedChallenges());
        }}
      />
    </>
  );
}
