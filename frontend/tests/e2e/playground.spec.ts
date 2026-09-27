import { expect, test, type Page } from "@playwright/test";

declare global {
  interface Window {
    __trainer: { setCode: (code: string) => void; solution: () => string; skipToEnd: () => void };
  }
}

async function open(page: Page) {
  await page.goto("/");
  await expect(page.getByText("Python ready")).toBeVisible({ timeout: 60_000 });
}

async function runCode(page: Page, code?: string) {
  if (code !== undefined) await page.evaluate((c) => window.__trainer.setCode(c), code);
  const app = page.locator(".app");
  const runs = Number(await app.getAttribute("data-runs"));
  await page.getByRole("button", { name: "▶ Run" }).click();
  await expect(app).toHaveAttribute("data-runs", String(runs + 1), { timeout: 30_000 });
  // Skip to the end of the playback.
  await page.evaluate(() => window.__trainer.skipToEnd());
}

test("first drive: starter misses the garage, solution parks in it", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: /First Drive/ }).click();
  await runCode(page);
  await expect(page.getByText(/Program finished after/)).toBeVisible();
  await expect(page.locator(".goals .fail")).toHaveCount(1);

  await runCode(page, await page.evaluate(() => window.__trainer.solution()));
  await expect(page.getByText("Challenge complete!")).toBeVisible();
  await expect(page.getByRole("button", { name: /First Drive/ })).toContainText("✔");
});

test("syntax errors get a kid-friendly explanation and line", async ({ page }) => {
  await open(page);
  await runCode(page, "for i in range(4)\n    print(i)\n");
  await expect(page.getByText("Problem on line 1")).toBeVisible();
  await expect(page.getByText(/need a colon/)).toBeVisible();
  await page.getByText("What Python said").click();
  await expect(page.getByText("SyntaxError: expected ':'")).toBeVisible();
});

test("a loop that never ends hits the time limit instead of freezing", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: /First Drive/ }).click();
  await runCode(page, "while True:\n    pass\n");
  await expect(page.getByText(/Time's up!/)).toBeVisible();
});

test("prints and variables show during playback", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: /Square Dance/ }).click();
  await runCode(page);
  await expect(page.getByText("Driving side 3")).toBeVisible();
  await page.getByRole("tab", { name: "Variables" }).click();
  await expect(page.locator(".vars")).toContainText("side");
});

test("every challenge's solution passes in the browser's Python", async ({ page }) => {
  await open(page);
  const chips = page.getByRole("navigation", { name: "Challenges" }).getByRole("button");
  const count = await chips.count();
  for (let i = 0; i < count; i++) {
    await chips.nth(i).click();
    const solution = await page.evaluate(() => window.__trainer.solution());
    if (!solution) continue;
    await runCode(page, solution);
    await expect(page.getByText("Challenge complete!"), await chips.nth(i).innerText()).toBeVisible({ timeout: 30_000 });
  }
});
