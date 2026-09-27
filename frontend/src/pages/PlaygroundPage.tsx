import { useCatalog } from "../content";
import { href } from "../router";
import { useSession } from "../session";
import * as storage from "../storage";
import { ChallengeWorkspace } from "../components/ChallengeWorkspace";

export function PlaygroundPage({ challengeId }: { challengeId?: string }) {
  const { playground } = useCatalog();
  const { solved } = useSession();
  const challenge =
    playground.find((c) => c.id === challengeId) ??
    playground.find((c) => c.id === storage.lastChallenge()) ??
    playground[0];
  if (!challenge) return <div className="card narrow">No playground challenges yet.</div>;
  if (challengeId && challenge.id === challengeId) storage.saveLastChallenge(challenge.id);

  return (
    <>
      <nav className="challenges" aria-label="Challenges">
        {playground.map((c, i) => (
          <a
            key={c.id}
            className={`chip ${c.id === challenge.id ? "active" : ""}`}
            href={href({ page: "playground", challengeId: c.id })}
            aria-current={c.id === challenge.id ? "page" : undefined}
          >
            <span className="chip-num">{i + 1}</span> {c.title}
            {solved.includes(c.id) && <span className="chip-done" aria-label="solved">✔</span>}
          </a>
        ))}
      </nav>
      <ChallengeWorkspace key={challenge.id} challenge={challenge} codeKey={`playground/${challenge.id}`} />
    </>
  );
}
