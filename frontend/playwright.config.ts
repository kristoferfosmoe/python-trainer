import { tmpdir } from "node:os";
import { join } from "node:path";
import { defineConfig, devices } from "@playwright/test";
import { COACH } from "./tests/e2e/accounts";

// CHROMIUM_PATH lets environments with a preinstalled Chromium skip the download.
const executablePath = process.env.CHROMIUM_PATH || undefined;
const BACKEND_PORT = 8765;
const WEB_PORT = 5174;
const database = join(tmpdir(), `trainer-e2e-${process.pid}.sqlite3`);

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 90_000,
  reporter: "list",
  workers: 2,
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], launchOptions: { executablePath } } }],
  webServer: [
    {
      // A fresh database with the real lessons, for every test run.
      command: [
        `rm -f ${database}`,
        "uv run python manage.py migrate -v0",
        "uv run python manage.py import_content --no-check -v0",
        `uv run python manage.py create_coach ${COACH.username} --password '${COACH.password}' > /dev/null`,
        `uv run python manage.py runserver 127.0.0.1:${BACKEND_PORT} --noreload`,
      ].join(" && "),
      cwd: "../backend",
      env: { DJANGO_SQLITE_PATH: database, DJANGO_SERVER_LOG_LEVEL: "WARNING" },
      url: `http://127.0.0.1:${BACKEND_PORT}/api/auth/me`,
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort`,
      env: { VITE_API_URL: `http://127.0.0.1:${BACKEND_PORT}` },
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
    },
  ],
});
