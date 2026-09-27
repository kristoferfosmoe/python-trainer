import { expect, test } from "@playwright/test";
import { open, runCode, runSolution } from "./helpers";

test("first drive: starter misses the garage, solution parks in it", async ({ page }) => {
  await open(page, "#/playground/first-drive");
  await runCode(page);
  await expect(page.getByText(/Program finished after/)).toBeVisible();
  await expect(page.locator(".goals .fail")).toHaveCount(1);

  await runSolution(page);
  await expect(page.getByText("Challenge complete!")).toBeVisible();
  await expect(page.getByRole("link", { name: /First Drive/ })).toContainText("✔");
});

test("syntax errors get a kid-friendly explanation and line", async ({ page }) => {
  await open(page, "#/playground/free-drive");
  await runCode(page, "for i in range(4)\n    print(i)\n");
  await expect(page.getByText("Problem on line 1")).toBeVisible();
  await expect(page.getByText(/need a colon/)).toBeVisible();
  await page.getByText("What Python said").click();
  await expect(page.getByText("SyntaxError: expected ':'")).toBeVisible();
});

test("a loop that never ends hits the time limit instead of freezing", async ({ page }) => {
  await open(page, "#/playground/first-drive");
  await runCode(page, "while True:\n    pass\n");
  await expect(page.getByText(/Time's up!/)).toBeVisible();
});

test("prints and variables show during playback", async ({ page }) => {
  await open(page, "#/playground/square-dance");
  await runCode(page);
  await expect(page.getByText("Driving side 3")).toBeVisible();
  await page.getByRole("tab", { name: "Variables" }).click();
  await expect(page.locator(".vars")).toContainText("side");
});

test("every playground solution passes in the browser's Python", async ({ page }) => {
  await open(page, "#/playground");
  const chips = page.getByRole("navigation", { name: "Challenges" }).getByRole("link");
  const count = await chips.count();
  for (let i = 0; i < count; i++) {
    const title = (await chips.nth(i).innerText()).replace(/^\d+\s*/, "").replace("✔", "").trim();
    await chips.nth(i).click();
    await expect(page.locator("#challenge-title")).toHaveText(title);
    const solution = await page.evaluate(() => window.__trainer.solution());
    if (!solution) continue;
    await runCode(page, solution);
    await expect(page.getByText("Challenge complete!"), await chips.nth(i).innerText()).toBeVisible({ timeout: 30_000 });
  }
});
