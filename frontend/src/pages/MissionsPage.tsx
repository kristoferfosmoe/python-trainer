// The Mission Mode ladder: each game's tiers, with a tile per challenge.
// Challenges unlock one after another (see missions.ts unlockedIds).

import { useEffect, useState } from "react";
import { fetchLadder, starText, unlockedIds } from "../missions";
import { href } from "../router";
import { useSession } from "../session";
import type { LadderGame } from "../types";

export function useLadder() {
  const { me } = useSession();
  const [games, setGames] = useState<LadderGame[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    fetchLadder().then(
      (data) => live && setGames(data.games),
      (e: Error) => live && setError(e.message),
    );
    return () => {
      live = false;
    };
  }, [me?.username]);
  return { games, error };
}

export function MissionsPage() {
  const { games, error } = useLadder();
  const { me, missions } = useSession();
  if (error) return <div className="card narrow">{error}</div>;
  if (!games) return <div className="card narrow">Loading missions…</div>;
  if (games.length === 0) return <div className="card narrow">No missions yet.</div>;
  const stars = (id: string) => missions[id]?.stars ?? 0;

  return (
    <div className="course missions">
      {games.map((game) => {
        const open = unlockedIds(game, stars);
        const done = game.challenges.filter((c) => stars(c.id) >= 1).length;
        const earned = game.challenges.reduce((sum, c) => sum + stars(c.id), 0);
        const next = game.challenges.find((c) => open.has(c.id) && stars(c.id) === 0);
        return (
          <div className="course-block" key={game.id}>
            <section className="card hero mission-hero">
              <div>
                <p className="eyebrow">🏆 Mission Mode</p>
                <h1>{game.title}</h1>
                <p>{game.summary}</p>
                <div className="progress-bar" role="progressbar" aria-label={`${game.title} progress`}
                  aria-valuemin={0} aria-valuemax={game.challenges.length} aria-valuenow={done}>
                  <span style={{ width: `${(done / game.challenges.length) * 100}%` }} />
                </div>
                <p className="progress-text">
                  {done} of {game.challenges.length} challenges complete · {earned} of {game.challenges.length * 3} ★
                </p>
                {!me && (
                  <p className="progress-text">👋 As a guest, your stars are only saved on this computer.</p>
                )}
              </div>
              {next && (
                <a className="button primary big" href={href({ page: "mission", challengeId: next.id })}>
                  {done === 0 ? "▶ Start" : "▶ Continue"}: {next.title}
                </a>
              )}
            </section>

            {game.tiers.map((tier) => {
              const ladder = game.challenges.filter((c) => c.tier === tier.id);
              if (ladder.length === 0) return null;
              return (
                <section className="unit" key={tier.id} aria-labelledby={`tier-${game.id}-${tier.id}`}>
                  <h2 id={`tier-${game.id}-${tier.id}`}>
                    <span className="unit-icon" aria-hidden>{tier.icon}</span> Tier {tier.id}: {tier.title}
                  </h2>
                  <p className="unit-summary">{tier.summary}</p>
                  <ol className="lesson-tiles">
                    {ladder.map((challenge) => {
                      const number = game.challenges.indexOf(challenge) + 1;
                      const got = stars(challenge.id);
                      const locked = !open.has(challenge.id);
                      const isNext = next?.id === challenge.id;
                      const body = (
                        <>
                          <span className="tile-num" aria-hidden>{locked ? "🔒" : number}</span>
                          <span className="tile-text">
                            <span className="tile-title">{challenge.title}</span>
                            <span className="tile-summary">{challenge.summary}</span>
                            <span className={`tile-stars ${got ? "" : "none"}`} aria-label={`${got} of 3 stars`}>
                              {starText(got)}
                            </span>
                          </span>
                          {isNext && <span className="tile-badge">Next up</span>}
                        </>
                      );
                      return (
                        <li key={challenge.id}>
                          {locked ? (
                            <div className="lesson-tile locked" aria-disabled="true"
                              title="Finish the challenge before this one to unlock it.">
                              {body}
                              <span className="sr-only">(locked)</span>
                            </div>
                          ) : (
                            <a className={`lesson-tile ${got ? "done" : ""} ${isNext ? "next" : ""}`}
                              href={href({ page: "mission", challengeId: challenge.id })}>
                              {body}
                            </a>
                          )}
                        </li>
                      );
                    })}
                  </ol>
                </section>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
