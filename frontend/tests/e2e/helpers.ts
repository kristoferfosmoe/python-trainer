import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type Page } from "@playwright/test";
import { load } from "js-yaml";

declare global {
  interface Window {
    __trainer: { setCode: (code: string) => void; key: () => string; solution: () => string; skipToEnd: () => void };
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

/** Each lesson's id and the (1-based) pages that have a challenge with goals. */
export const LESSONS: { id: string; challengePages: number[] }[] = [];
for (const course of readdirSync(join(CONTENT, "courses"))) {
  const courseDir = join(CONTENT, "courses", course);
  for (const unit of readdirSync(courseDir).sort()) {
    const unitDir = join(courseDir, unit);
    if (!statSync(unitDir).isDirectory()) continue;
    for (const file of yamlFiles(unitDir).filter((f) => !f.endsWith("unit.yaml"))) {
      const lesson = read(file);
      const challengePages: number[] = [];
      let page = 1;
      (lesson.blocks as Yaml[]).forEach((raw, index) => {
        const block = raw.ref ? { ...playground.get(raw.ref), ...raw } : raw;
        if (block.type === "challenge") {
          const id = raw.id ?? raw.ref ?? `block-${index + 1}`;
          if (block.solution) SOLUTIONS.set(`lesson/${lesson.id}/${id}`, block.solution);
          if (block.goals?.length) challengePages.push(page);
        }
        if (block.type !== "text") page++;
      });
      LESSONS.push({ id: lesson.id, challengePages });
    }
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
  return username;
}
