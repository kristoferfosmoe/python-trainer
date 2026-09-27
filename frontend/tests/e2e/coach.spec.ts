import { expect, test, type Page } from "@playwright/test";
import { COACH, PIN, open, runSolution, signIn, signOut, uniqueName } from "./helpers";

const acceptDialogs = (page: Page) => page.on("dialog", (dialog) => void dialog.accept());

async function makeTeam(page: Page) {
  const name = uniqueName("Team");
  await page.getByRole("link", { name: "👥 Teams" }).click();
  await page.getByLabel("Team name").fill(name);
  await page.getByRole("button", { name: "Make team" }).click();
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  return name;
}

test("a coach makes accounts, sets up the robot and sees a student's work", async ({ page }) => {
  acceptDialogs(page);
  await signIn(page, COACH.username, COACH.password);
  const teamName = await makeTeam(page);
  await expect(page.getByText("No students yet")).toBeVisible();

  // Two accounts: one with a made-up username, one with a chosen one.
  const chosen = uniqueName("Rita");
  await page.getByLabel("Students to add").fill(`Sam\nRita, ${chosen}`);
  await page.getByRole("button", { name: "Make 2 accounts" }).click();
  await expect(page.getByTestId("card-pin")).toHaveCount(2);
  const usernames = await page.getByTestId("card-username").allTextContents();
  const pin = (await page.getByTestId("card-pin").allTextContents())[1];
  expect(usernames[1]).toBe(chosen);
  expect(usernames[0]).toMatch(/^[A-Z][a-z]+[A-Z][a-z]+\d\d$/);
  await expect(page.locator(".progress-table tbody tr")).toHaveCount(2);

  // The team's real robot: left wheel on E (the arm moves to A), bigger wheels.
  await page.locator("#port-left_arm").selectOption("A");
  await page.locator("#port-left_wheel").selectOption("E");
  await page.getByLabel("Wheel diameter (mm)").fill("88");
  await page.getByRole("button", { name: "Save robot" }).click();
  await expect(page.getByText("Saved. Students' code will now fit this robot.")).toBeVisible();

  // Rita signs in with her card, solves a challenge and gets code for the team robot.
  await signOut(page);
  await signIn(page, chosen, pin);
  await open(page, "#/playground/first-drive");
  await runSolution(page);
  await expect(page.getByRole("link", { name: /First Drive/ })).toContainText("✔");
  await page.getByRole("button", { name: "🤖 Run on your robot" }).click();
  const dialog = page.getByRole("dialog", { name: "🤖 Run it on your robot" });
  await expect(dialog.getByText("Changed to fit")).toBeVisible();
  await expect(dialog.locator(".change-list")).toContainText("Left wheel motor: Port.A → Port.E");
  const robotCode = dialog.getByRole("textbox", { name: "Code for your robot" });
  await expect(robotCode).toContainText("left_motor = Motor(Port.E, Direction.COUNTERCLOCKWISE)");
  await expect(robotCode).toContainText("wheel_diameter=88");
  await expect(dialog.getByRole("link", { name: "Open Pybricks ↗" })).toHaveAttribute("href", "https://code.pybricks.com");
  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(dialog).toBeHidden();

  // The coach sees Rita's progress and code, and gives her a new PIN.
  await signOut(page);
  await signIn(page, COACH.username, COACH.password);
  await page.getByRole("link", { name: "👥 Teams" }).click();
  await page.locator(".team-card", { hasText: teamName }).click();
  const ritaRow = page.locator(".progress-table tbody tr", { hasText: chosen });
  await expect(ritaRow.locator("td").last()).toHaveText("1");
  await ritaRow.getByRole("link").click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Rita");
  const work = page.locator(".work-list li", { hasText: "First Drive" });
  await expect(work).toContainText("1 run");
  await work.locator("summary").click();
  await expect(work.getByRole("textbox").first()).toContainText("drive_base.straight(930)");

  // A new PIN lets whoever has it sign in as Rita, so the coach types their password first.
  await page.getByRole("button", { name: "🔑 Make a new PIN" }).click();
  await page.getByLabel("Your password").fill("not the password");
  await page.getByRole("button", { name: "Make the new PIN" }).click();
  await expect(page.getByRole("alert")).toContainText("isn't right");
  await page.getByLabel("Your password").fill(COACH.password);
  await page.getByRole("button", { name: "Make the new PIN" }).click();
  await expect(page.getByTestId("card-pin")).toHaveCount(1);
  const newPin = await page.getByTestId("card-pin").textContent();
  expect(newPin).not.toBe(pin);

  await signOut(page);
  await page.goto("/#/signin");
  await page.getByLabel("Username").fill(chosen);
  await page.getByLabel(/PIN/).fill(pin);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toContainText("don't match");
  await signIn(page, chosen, newPin!);
});

test("students who sign up with the join code show up for the coach", async ({ page }) => {
  await signIn(page, COACH.username, COACH.password);
  const teamName = await makeTeam(page);
  const teamPage = new URL(page.url()).hash;
  const code = await page.getByTestId("join-code").textContent();
  await signOut(page);

  await page.goto("/#/signup");
  const username = uniqueName("Joiner");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Make a 6-number PIN").fill(PIN);
  await page.getByLabel("Type your PIN again").fill(PIN);
  await page.getByLabel("Team code (optional)").fill(code!);
  await page.getByRole("button", { name: "Sign up" }).click();
  await expect(page.locator(".account-chip")).toContainText(username);
  await expect(page).not.toHaveURL(/#\/signup/);
  await page.goto("/#/lesson/hello-python/2");
  await page.locator(".choice").nth(1).click();
  await expect(page.getByText("✔ Correct!")).toBeVisible();
  // Students don't get the team pages, even for their own team.
  await expect(page.getByRole("link", { name: "👥 Teams" })).toHaveCount(0);
  await page.goto(`/${teamPage}`);
  await expect(page.getByText("Only this team's coaches and mentors can see this.")).toBeVisible();

  await signOut(page);
  await signIn(page, COACH.username, COACH.password);
  await page.getByRole("link", { name: "👥 Teams" }).click();
  await page.locator(".team-card", { hasText: teamName }).click();
  const row = page.locator(".progress-table tbody tr", { hasText: username });
  await expect(row.locator(".unit-cell.started")).toHaveCount(1);
});

test("guests get Trainer Bot code to copy into Pybricks", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await open(page, "#/playground/first-drive");
  await page.getByRole("button", { name: "🤖 Run on your robot" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("built like the Trainer Bot");
  await dialog.getByRole("button", { name: "📋 Copy code" }).click();
  await expect(dialog.getByRole("button", { name: "✔ Copied!" })).toBeVisible();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toContain("left_motor = Motor(Port.A, Direction.COUNTERCLOCKWISE)");
  expect(copied).toContain("drive_base.straight(300)");
});
