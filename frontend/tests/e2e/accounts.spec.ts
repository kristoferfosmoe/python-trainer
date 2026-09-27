import { expect, test } from "@playwright/test";
import { PIN, open, runSolution, signUp, uniqueName } from "./helpers";

test("guest progress comes along when you sign up", async ({ page }) => {
  await open(page, "#/playground/first-drive");
  await runSolution(page);
  await expect(page.getByRole("link", { name: /First Drive/ })).toContainText("✔");

  const username = await signUp(page);
  await page.goto("/#/playground/first-drive");
  await expect(page.getByRole("link", { name: /First Drive/ })).toContainText("✔");
  // Saved on the server: it's still there after the browser forgets everything.
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(page.locator(".account-chip")).toContainText(username);
  await expect(page.getByRole("link", { name: /First Drive/ })).toContainText("✔");
});

test("progress follows the student, not the computer", async ({ page }) => {
  const username = await signUp(page);
  await page.goto("/#/lesson/hello-python/2");
  await page.locator(".choice").nth(1).click();
  await expect(page.getByText("✔ Correct!")).toBeVisible();

  // Sign out: the guest map starts fresh.
  await page.locator(".account-chip").click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByText("You're a guest")).toBeVisible();
  await expect(page.locator(".lesson-tile.started")).toHaveCount(0);

  // Sign back in: the lesson is in progress and the quiz is still answered.
  await page.goto("/#/signin");
  await page.getByLabel("Username").fill(username.toLowerCase());
  await page.getByLabel(/PIN/).fill(PIN);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator(".lesson-tile.started")).toHaveCount(1);
  await page.goto("/#/lesson/hello-python/2");
  await expect(page.getByText("✔ Correct!")).toBeVisible();
});

test("saved code comes back after signing in again", async ({ page }) => {
  await signUp(page);
  await page.goto("/#/playground/free-drive");
  await page.evaluate(() => window.__trainer.setCode("print('my own program')\n"));
  await page.waitForTimeout(1500); // drafts save after a short pause
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(page.locator(".cm-content").first()).toContainText("my own program");
});

test("wrong PINs and easy PINs get clear messages", async ({ page }) => {
  await page.goto("/#/signup");
  await page.getByLabel("Username").fill(uniqueName());
  await page.getByLabel("Make a 6-number PIN").fill("123456");
  await page.getByLabel("Type your PIN again").fill("123456");
  await page.getByRole("button", { name: "Sign up" }).click();
  await expect(page.getByRole("alert")).toContainText("too easy to guess");

  await page.goto("/#/signin");
  await page.getByLabel("Username").fill("NobodyHere");
  await page.getByLabel(/PIN/).fill("975310");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toContainText("don't match");
});

test("students never receive challenge solutions", async ({ page }) => {
  await signUp(page);
  await page.goto("/#/lesson/for-loops/3");
  await expect(page.locator(".workspace")).toBeVisible();
  expect(await page.evaluate(() => window.__trainer.solution())).toBe("");
});

test("the make-one-up button suggests a username", async ({ page }) => {
  await page.goto("/#/signup");
  await page.getByRole("button", { name: /Make one up/ }).click();
  await expect(page.getByLabel("Username")).toHaveValue(/^[A-Z][a-z]+[A-Z][a-z]+\d\d$/);
});
