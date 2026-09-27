import { expect, test } from "@playwright/test";
import { LESSONS, UNIT_COUNT, open, runSolution } from "./helpers";

test("the course map lists every unit and lesson", async ({ page }) => {
  await open(page);
  await expect(page.getByRole("heading", { name: /Unit \d+:/ })).toHaveCount(UNIT_COUNT);
  await expect(page.locator(".lesson-tile")).toHaveCount(LESSONS.length);
  await expect(page.getByText(`0 of ${LESSONS.length} lessons complete`)).toBeVisible();
});

test("a student can complete lesson 1 from start to finish", async ({ page }) => {
  await open(page);
  await page.getByRole("link", { name: /Start: Hello, Python!/ }).click();

  // Page 1: run an example.
  await page.getByRole("button", { name: "▶ Run" }).click();
  await expect(page.locator(".example-output")).toContainText("Hello, robot!");
  await page.getByRole("button", { name: "Continue →" }).click();

  // Page 2: a quiz blocks Continue until it's answered correctly.
  const next = page.getByRole("button", { name: "Continue →" });
  await expect(next).toBeDisabled();
  await page.locator(".choice").nth(0).click();
  await expect(page.getByText("Not quite.")).toBeVisible();
  await page.locator(".choice").nth(1).click();
  await expect(page.getByText("✔ Correct!")).toBeVisible();
  await next.click();

  // Pages 3 and 4: examples (the second one has a bug on purpose).
  await next.click();
  await page.getByRole("button", { name: "▶ Run" }).click();
  await expect(page.getByText("Problem on line 2")).toBeVisible();
  await next.click();

  // Page 5: the challenge. Continue says "Skip" until it's solved.
  await expect(page.getByRole("button", { name: "Skip for now →" })).toBeVisible();
  await runSolution(page);
  await expect(page.getByText("Challenge complete!")).toBeVisible();
  await page.locator(".feedback.notice").getByRole("button", { name: "Finish lesson 🎉" }).click();

  await expect(page.getByRole("heading", { name: "Lesson complete!" })).toBeVisible();
  await page.getByRole("link", { name: /Next: First Moves/ }).click();
  await expect(page.getByRole("heading", { name: /Lesson 2: First Moves/ })).toBeVisible();

  await page.getByRole("link", { name: "🗺️ Lessons" }).click();
  await expect(page.getByText(`1 of ${LESSONS.length} lessons complete`)).toBeVisible();
  await expect(page.locator(".lesson-tile.done")).toHaveCount(1);
});

test("the visualizer steps through a loop", async ({ page }) => {
  await open(page, "#/lesson/for-loops/1");
  const forward = page.getByRole("button", { name: "Step forward" });
  await expect(page.getByText("Step 1 of 10")).toBeVisible();
  await expect(page.locator(".cm-note")).toHaveText("🔁 round 1: side = 0");
  await forward.click();
  await forward.click();
  await expect(page.locator(".stepper .output")).toHaveText("Round 0");
  await expect(page.locator(".cm-count-gutter")).toContainText("×1");
  for (let i = 0; i < 8; i++) await forward.click();
  await expect(page.getByText("✔ Finished")).toBeVisible();
  await expect(page.locator(".stepper .output")).toHaveText("Round 0\nRound 1\nRound 2\nRound 3\nDone!");
});

test("every lesson challenge's solution passes in the browser's Python", async ({ page }) => {
  await open(page);
  let checked = 0;
  for (const lesson of LESSONS) {
    for (const pageNumber of lesson.challengePages) {
      await page.goto(`/#/lesson/${lesson.id}/${pageNumber}`);
      // Wait for this lesson's workspace (the previous one can still be on screen).
      await page.waitForFunction((id) => window.__trainer?.key().startsWith(`lesson/${id}/`), lesson.id);
      await runSolution(page);
      await expect(page.getByText("Challenge complete!"), `${lesson.id} page ${pageNumber}`).toBeVisible({ timeout: 30_000 });
      checked++;
    }
  }
  expect(checked).toBeGreaterThanOrEqual(12);
});
