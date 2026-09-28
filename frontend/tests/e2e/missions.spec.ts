import { expect, test } from "@playwright/test";
import { MISSIONS, open, runCode, runSolution, signUp } from "./helpers";

test("the Missions tab shows the ladder, with everything after the first challenge locked", async ({ page }) => {
  await open(page, "#/missions");
  await expect(page.getByRole("link", { name: "🏆 Missions" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { name: "Harbor Rescue" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Tier 1: First Missions/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Tier 7: Tournament/ })).toBeVisible();
  await expect(page.getByRole("link", { name: "▶ Start: Crate to the Dock" })).toBeVisible();
  await expect(page.locator("a.lesson-tile", { hasText: "Crate to the Dock" })).toBeVisible();
  // Locked challenges aren't links.
  await expect(page.getByRole("link", { name: /Ring the Bell/ })).toHaveCount(0);
  await expect(page.locator(".lesson-tile.locked")).toHaveCount(MISSIONS.length - 1);
  await expect(page.getByText(`0 of ${MISSIONS.length} challenges complete`)).toBeVisible();
});

test("a locked challenge can't be opened by typing its address", async ({ page }) => {
  await open(page, "#/missions/tournament");
  await expect(page.getByRole("heading", { name: "🔒 Not unlocked yet" })).toBeVisible();
});

test("the starter scores nothing yet, and the mat, score panel and attachments show", async ({ page }) => {
  await open(page, "#/missions/crate-to-the-dock");
  await expect(page.locator("#challenge-title")).toHaveText("Crate to the Dock");
  await expect(page.getByLabel("Attachments")).toContainText("no attachments");
  await runCode(page);
  await expect(page.getByLabel("Score")).toContainText("Precision tokens");
  await expect(page.locator(".goals .fail")).toHaveCount(1);
  await expect(page.getByText("Perfect!")).toHaveCount(0);
});

test("every mission's solution earns three stars and unlocks the next one", async ({ page }) => {
  test.setTimeout(900_000);
  await open(page, "#/missions");
  for (const [index, mission] of MISSIONS.entries()) {
    await page.goto(`/#/missions/${mission.id}`);
    await page.waitForFunction((k) => window.__trainer?.key() === k, `mission/${mission.id}`);
    if (mission.picks.length) {
      await page.evaluate((picks) => window.__trainer.choose!(picks), mission.picks);
      await page.waitForFunction((picks) => JSON.stringify(window.__trainer.picks!()) === JSON.stringify(picks), mission.picks);
    }
    await runSolution(page);
    await expect(page.getByText("Perfect!"), mission.id).toBeVisible({ timeout: 60_000 });
    const next = MISSIONS[index + 1];
    if (next) await expect(page.getByRole("link", { name: "Next challenge →" })).toHaveAttribute("href", `#/missions/${next.id}`);
  }
  await page.goto("/#/missions");
  await expect(page.getByText(`${MISSIONS.length} of ${MISSIONS.length} challenges complete`)).toBeVisible();
  await expect(page.locator(".lesson-tile.locked")).toHaveCount(0);
});

test("a student's stars are saved on the server and unlock the next challenge", async ({ page }) => {
  await signUp(page);
  await open(page, "#/missions/crate-to-the-dock");
  await runSolution(page);
  await expect(page.getByText("Perfect!")).toBeVisible();
  await page.reload();
  await open(page, "#/missions");
  await expect(page.getByText(`1 of ${MISSIONS.length} challenges complete`)).toBeVisible();
  await expect(page.locator("a.lesson-tile", { hasText: "Ring the Bell" })).toBeVisible();
  await expect(page.getByRole("link", { name: "▶ Continue: Ring the Bell" })).toBeVisible();
});
