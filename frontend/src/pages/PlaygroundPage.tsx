import { useCatalog } from "../content";
import { href } from "../router";
import { useSession } from "../session";
import * as storage from "../storage";
import type { Challenge } from "../types";
import { ChallengeWorkspace } from "../components/ChallengeWorkspace";

interface Section {
  name: string;
  challenges: { challenge: Challenge; num: number }[];
}

/** Challenges grouped by their section, in the order the sections first appear. */
function sections(playground: Challenge[]): Section[] {
  const groups: Section[] = [];
  playground.forEach((challenge, i) => {
    const name = challenge.section ?? "More";
    let group = groups.find((g) => g.name === name);
    if (!group) groups.push((group = { name, challenges: [] }));
    group.challenges.push({ challenge, num: i + 1 });
  });
  return groups;
}

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
        {sections(playground).map((section) => {
          const withGoals = section.challenges.filter(({ challenge: c }) => c.goals?.length);
          const done = withGoals.filter(({ challenge: c }) => solved.includes(c.id)).length;
          return (
            <div key={section.name} className="challenge-section" role="group" aria-label={section.name}>
              <span className="challenge-section-name">
                {section.name}
                {withGoals.length > 0 && (
                  <span className="challenge-section-count">
                    {done}/{withGoals.length}
                  </span>
                )}
              </span>
              <div className="challenge-chips">
                {section.challenges.map(({ challenge: c, num }) => (
                  <a
                    key={c.id}
                    className={`chip ${c.id === challenge.id ? "active" : ""}`}
                    href={href({ page: "playground", challengeId: c.id })}
                    aria-current={c.id === challenge.id ? "page" : undefined}
                  >
                    <span className="chip-num">{num}</span> {c.title}
                    {solved.includes(c.id) && <span className="chip-done" aria-label="solved">✔</span>}
                  </a>
                ))}
              </div>
            </div>
          );
        })}
      </nav>
      <ChallengeWorkspace key={challenge.id} challenge={challenge} codeKey={`playground/${challenge.id}`} />
    </>
  );
}
