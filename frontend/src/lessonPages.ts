import type { Block, ChallengeBlock } from "./types";

/**
 * Split a lesson into pages. A page ends after each interactive block
 * (example, visualize, quiz, challenge), so text always introduces what follows.
 */
export function paginate(blocks: Block[]): Block[][] {
  const pages: Block[][] = [];
  let current: Block[] = [];
  for (const block of blocks) {
    current.push(block);
    if (block.type !== "text") {
      pages.push(current);
      current = [];
    }
  }
  if (current.length) pages.push(current);
  return pages;
}

export const hasGoals = (b: Block): b is ChallengeBlock => b.type === "challenge" && (b.goals?.length ?? 0) > 0;
