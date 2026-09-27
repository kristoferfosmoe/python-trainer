import { expect, type Page } from "@playwright/test";

declare global {
  interface Window {
    __trainer: { setCode: (code: string) => void; solution: () => string; skipToEnd: () => void };
    __course: { id: string; challengePages: number[] }[];
  }
}

export async function open(page: Page, hash = "#/") {
  await page.goto(`/${hash}`);
  await expect(page.getByText("Python ready")).toBeVisible({ timeout: 60_000 });
}

/** Run the code in the challenge workspace and skip to the end of the playback. */
export async function runCode(page: Page, code?: string) {
  if (code !== undefined) await page.evaluate((c) => window.__trainer.setCode(c), code);
  const workspace = page.locator(".workspace");
  const runs = Number(await workspace.getAttribute("data-runs"));
  await workspace.getByRole("button", { name: "▶ Run" }).click();
  await expect(workspace).toHaveAttribute("data-runs", String(runs + 1), { timeout: 30_000 });
  await page.evaluate(() => window.__trainer.skipToEnd());
}

export async function runSolution(page: Page) {
  await runCode(page, await page.evaluate(() => window.__trainer.solution()));
}
