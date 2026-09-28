import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type Page } from "@playwright/test";
import { load } from "js-yaml";

declare global {
  interface Window {
    __trainer: {
      setCode: (code: string) => void;
      key: () => string;
      code: () => string;
      runs: () => number;
      solution: () => string;
      skipToEnd: () => void;
      // Mission Mode only: pick each run's attachments.
      choose?: (picks: Record<string, string>[]) => void;
      picks?: () => Record<string, string>[];
    };
  }
}

// Students never receive solutions from the server, so tests read them from content/.
type Yaml = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const CONTENT = join(dirname(fileURLToPath(import.meta.url)), "../../../content");
const read = (path: string) => load(readFileSync(path, "utf8")) as Yaml;
const yamlFiles = (dir: string) => readdirSync(dir).filter((f) => f.endsWith(".yaml")).sort().map((f) => join(dir, f));

const playground = new Map(yamlFiles(join(CONTENT, "challenges")).map((p) => [read(p).id as string, read(p)]));
export const SOLUTIONS = new Map<string, string>();
for (const [id, challenge] of playground) SOLUTIONS.set(`playground/${id}`, challenge.solution);

/** Mission Mode challenges in ladder order (content/missions/<game>/challenges/), with the attachments their solutions need. */
export const MISSIONS: { id: string; title: string; picks: Record<string, string>[] }[] = [];
for (const game of readdirSync(join(CONTENT, "missions")).sort()) {
  const dir = join(CONTENT, "missions", game, "challenges");
  for (const file of yamlFiles(dir)) {
    const challenge = read(file);
    SOLUTIONS.set(`mission/${challenge.id}`, challenge.solution);
    MISSIONS.push({ id: challenge.id, title: challenge.title, picks: challenge.solution_attachments ?? [] });
  }
}

/** Each lesson's id, and its challenges with goals: their (1-based) page and editor key. */
export const LESSONS: { id: string; challenges: { page: number; key: string }[] }[] = [];
export let UNIT_COUNT = 0;
for (const course of readdirSync(join(CONTENT, "courses"))) {
  const courseDir = join(CONTENT, "courses", course);
  for (const unit of readdirSync(courseDir).sort()) {
    const unitDir = join(courseDir, unit);
    if (!statSync(unitDir).isDirectory()) continue;
    UNIT_COUNT++;
    for (const file of yamlFiles(unitDir).filter((f) => !f.endsWith("unit.yaml"))) {
      const lesson = read(file);
      const challenges: { page: number; key: string }[] = [];
      let page = 1;
      (lesson.blocks as Yaml[]).forEach((raw, index) => {
        const block = raw.ref ? { ...playground.get(raw.ref), ...raw } : raw;
        if (block.type === "challenge") {
          const id = raw.id ?? raw.ref ?? `block-${index + 1}`;
          if (block.solution) SOLUTIONS.set(`lesson/${lesson.id}/${id}`, block.solution);
          if (block.goals?.length) challenges.push({ page, key: `lesson/${lesson.id}/${id}` });
        }
        if (block.type !== "text") page++;
      });
      LESSONS.push({ id: lesson.id, challenges });
    }
  }
}

export async function open(page: Page, hash = "#/") {
  await page.goto(`/${hash}`);
  await expect(page.getByText("Python ready")).toBeVisible({ timeout: 60_000 });
}

/** Run the code in the challenge workspace and skip to the end of the playback. */
export async function runCode(page: Page, code?: string) {
  if (code !== undefined) {
    await page.evaluate((c) => window.__trainer.setCode(c), code);
    // Wait for React to render the new code, so Run runs it.
    await page.waitForFunction((c) => window.__trainer.code() === c, code);
  }
  const workspace = page.locator(".workspace");
  const runs = Number(await workspace.getAttribute("data-runs"));
  await workspace.getByRole("button", { name: "▶ Run" }).click();
  await expect(workspace).toHaveAttribute("data-runs", String(runs + 1), { timeout: 30_000 });
  // The hooks update just after the page does; skip with the new run's hooks.
  await page.waitForFunction((n) => window.__trainer.runs() === n, runs + 1);
  await page.evaluate(() => window.__trainer.skipToEnd());
}

export async function runSolution(page: Page) {
  const key = await page.evaluate(() => window.__trainer.key());
  const solution = SOLUTIONS.get(key);
  if (!solution) throw new Error(`No solution for ${key}`);
  await runCode(page, solution);
}

export function uniqueName(prefix = "Tester") {
  return `${prefix}${Date.now().toString(36).slice(-5)}${Math.floor(Math.random() * 1000)}`;
}

export const PIN = "271828";

export async function signUp(page: Page, username = uniqueName()) {
  await page.goto("/#/signup");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Make a 6-number PIN").fill(PIN);
  await page.getByLabel("Type your PIN again").fill(PIN);
  await page.getByRole("button", { name: "Sign up" }).click();
  await expect(page.locator(".account-chip")).toContainText(username);
  await expect(page).not.toHaveURL(/#\/signup/); // signing up ends on the course map
  return username;
}

export { COACH } from "./accounts";

export async function signIn(page: Page, username: string, secret: string) {
  await page.goto("/#/signin");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel(/PIN/).fill(secret);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator(".account-chip")).toBeVisible();
  await expect(page).not.toHaveURL(/#\/signin/); // signing in ends on the map or the teams page
}

export async function signOut(page: Page) {
  await page.goto("/#/account");
  await page.getByRole("button", { name: "Sign out" }).click();
  // Signing out ends on the course map; wait for that before going anywhere else.
  await expect(page.getByText("You're a guest")).toBeVisible();
  await expect(page).toHaveURL(/#\/$/);
}
