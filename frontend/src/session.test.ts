import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./api";

// What the fake server does with each request: return a value, or throw.
type Handler = (path: string, body: unknown) => unknown;
let handler: Handler;
const calls: { path: string; body: unknown }[] = [];

vi.mock("./api", async (original) => ({
  ...(await original<typeof import("./api")>()),
  api: vi.fn(async (path: string, options: { body?: unknown } = {}) => {
    calls.push({ path, body: options.body });
    return handler(path, options.body);
  }),
}));
vi.mock("./content", () => ({ loadCatalog: vi.fn(async () => undefined) }));

const me = (username: string) => ({ username, display_name: username, avatar: "🦊", kind: "student", is_staff: false, teams: [] });
const EMPTY_STATE = { lessons: {}, solved: [], drafts: {} };
const offline = () => {
  throw new ApiError(0, "Can't reach the server.");
};

async function signedInAs(username: string, rest: Handler = () => ({ ok: true })) {
  handler = (path, body) => {
    if (path === "/auth/me") return { user: me(username) };
    if (path === "/me/state") return EMPTY_STATE;
    return rest(path, body);
  };
  const session = await import("./session");
  await session.initSession();
  return session;
}

const settle = () => vi.advanceTimersByTimeAsync(0);
const sent = (path: string) => calls.filter((c) => c.path === path);

describe("saving to the server", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.resetModules();
    calls.length = 0;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("tries a failed save again, and says so until it works", async () => {
    let online = false;
    const session = await signedInAs("KidOne", () => (online ? { ok: true } : offline()));
    session.reachPage("for-loops", 2);
    await settle();
    expect(session.getSession().unsaved).toBe(true);
    online = true;
    await vi.advanceTimersByTimeAsync(5_000);
    expect(sent("/progress/for-loops")).toHaveLength(2);
    expect(session.getSession().unsaved).toBe(false);
  });

  it("waits longer between tries, up to a minute", async () => {
    const session = await signedInAs("KidOne", offline);
    session.reachPage("for-loops", 2);
    await settle();
    for (const wait of [5_000, 10_000, 20_000, 40_000, 60_000, 60_000]) {
      const before = sent("/progress/for-loops").length;
      await vi.advanceTimersByTimeAsync(wait - 1);
      expect(sent("/progress/for-loops")).toHaveLength(before);
      await vi.advanceTimersByTimeAsync(1);
      expect(sent("/progress/for-loops")).toHaveLength(before + 1);
    }
  });

  it("sends only the newest code for an editor", async () => {
    let online = false;
    const session = await signedInAs("KidOne", () => (online ? { ok: true } : offline()));
    session.saveDraft("playground/first-drive", "print(1)");
    await vi.advanceTimersByTimeAsync(800);
    session.saveDraft("playground/first-drive", "print(2)");
    await vi.advanceTimersByTimeAsync(800);
    online = true;
    calls.length = 0;
    await vi.advanceTimersByTimeAsync(10_000);
    expect(sent("/drafts").map((c) => c.body)).toEqual([{ key: "playground/first-drive", code: "print(2)" }]);
  });

  it("drops saves the server refuses", async () => {
    const session = await signedInAs("KidOne", () => {
      throw new ApiError(400, "That program is too long to save.");
    });
    session.saveDraft("playground/first-drive", "x");
    await vi.advanceTimersByTimeAsync(800);
    await vi.advanceTimersByTimeAsync(120_000);
    expect(sent("/drafts")).toHaveLength(1);
    expect(session.getSession().unsaved).toBe(false);
  });

  it("keeps work while signed out, and sends it when the same student signs in again", async () => {
    let signedIn = false;
    const session = await signedInAs("KidOne", (path) => {
      if (path === "/auth/login") {
        signedIn = true;
        return { user: me("kidone") };
      }
      if (!signedIn) throw new ApiError(401, "Unauthorized");
      return { ok: true };
    });
    session.recordAttempt({ key: "playground/first-drive", code: "go()", passed: true, goals: [], sim_version: "1" });
    await settle();
    expect(session.getSession().signedOut).toBe(true);
    await vi.advanceTimersByTimeAsync(120_000);
    expect(sent("/attempts")).toHaveLength(1); // no point trying while signed out

    await session.signIn("kidone", "314159");
    const order = calls.map((c) => c.path);
    expect(sent("/attempts")).toHaveLength(2);
    expect(order.lastIndexOf("/attempts")).toBeLessThan(order.lastIndexOf("/me/state"));
    expect(session.getSession().signedOut).toBe(false);
    expect(session.getSession().unsaved).toBe(false);
  });

  it("never sends one student's work as another's", async () => {
    let signedIn = false;
    const session = await signedInAs("KidOne", (path) => {
      if (path === "/auth/login") {
        signedIn = true;
        return { user: me("KidTwo") };
      }
      if (!signedIn) throw new ApiError(401, "Unauthorized");
      return { ok: true };
    });
    session.reachPage("for-loops", 3);
    await settle();
    await session.signIn("KidTwo", "271828");
    await vi.advanceTimersByTimeAsync(120_000);
    expect(sent("/progress/for-loops")).toHaveLength(1);
    expect(session.getSession().unsaved).toBe(false);
  });
});
