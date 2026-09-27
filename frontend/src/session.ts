// Who's signed in, and their progress, saved code and solved challenges.
//
// Guests: everything stays in this browser (localStorage).
// Signed in: the server is the source of truth. Changes update the screen
// right away and are sent to the server in the background.
// Signing up or in as a guest brings the guest's progress along.

import { useSyncExternalStore } from "react";
import { api, ApiError } from "./api";
import { loadCatalog } from "./content";
import type { TeamRobot } from "./pybricks";

export interface Team {
  id: number;
  name: string;
  role: "student" | "mentor" | "coach";
  /** The team's real robot, if the coach set it up (for copying code to Pybricks). */
  robot: TeamRobot | null;
}

export interface Me {
  username: string;
  display_name: string;
  avatar: string;
  kind: "student" | "adult";
  is_staff: boolean;
  teams: Team[];
}

export interface LessonProgress {
  page: number; // furthest page reached (0-based)
  done: string[]; // ids of finished quizzes and challenges
  finished: boolean; // reached the end of the lesson
}

interface Saved {
  lessons: Record<string, LessonProgress>;
  solved: string[];
  drafts: Record<string, string>;
}

export interface SessionState extends Saved {
  me: Me | null;
  unsaved: boolean; // a save to the server failed; we'll retry
}

const GUEST_KEY = "guest:v1";
const EMPTY: Saved = { lessons: {}, solved: [], drafts: {} };
const listeners = new Set<() => void>();
let state: SessionState = { ...EMPTY, me: null, unsaved: false };

function set(change: Partial<SessionState>) {
  state = { ...state, ...change };
  listeners.forEach((listener) => listener());
}

export function useSession(): SessionState {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => state,
  );
}

export const getSession = () => state;

// --- Guest storage ---------------------------------------------------------------

function readGuest(): Saved {
  try {
    const saved = localStorage.getItem(GUEST_KEY);
    if (saved) return { ...EMPTY, ...(JSON.parse(saved) as Saved) };
    return migrateOldStorage();
  } catch {
    return { ...EMPTY };
  }
}

/** Progress saved by earlier versions of the app (before accounts). */
function migrateOldStorage(): Saved {
  const saved: Saved = { lessons: {}, solved: [], drafts: {} };
  try {
    saved.lessons = JSON.parse(localStorage.getItem("progress:v1") ?? "{}");
    saved.solved = JSON.parse(localStorage.getItem("solved") ?? "[]");
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)!;
      if (key.startsWith("code:lesson/")) saved.drafts[key.slice(5)] = JSON.parse(localStorage.getItem(key)!);
      else if (key.startsWith("code:")) saved.drafts[`playground/${key.slice(5)}`] = JSON.parse(localStorage.getItem(key)!);
    }
  } catch {
    // ignore anything unreadable
  }
  return saved;
}

function writeGuest(saved: Saved) {
  try {
    localStorage.setItem(GUEST_KEY, JSON.stringify(saved));
  } catch {
    // Private windows can block storage; progress just won't be remembered.
  }
}

function clearGuest() {
  try {
    localStorage.removeItem(GUEST_KEY);
    for (const key of ["progress:v1", "solved"]) localStorage.removeItem(key);
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const key = localStorage.key(i)!;
      if (key.startsWith("code:")) localStorage.removeItem(key);
    }
  } catch {
    // ignore
  }
}

const hasProgress = (saved: Saved) =>
  Object.keys(saved.lessons).length > 0 || saved.solved.length > 0 || Object.keys(saved.drafts).length > 0;

function persistGuest() {
  if (!state.me) writeGuest({ lessons: state.lessons, solved: state.solved, drafts: state.drafts });
}

// --- Server sync -----------------------------------------------------------------

const inFlight = new Set<Promise<void>>();

function background(request: Promise<unknown>) {
  const tracked = request.then(
    () => {
      if (state.unsaved) set({ unsaved: false });
    },
    (error) => {
      console.warn("Couldn't save to the server", error);
      if (!(error instanceof ApiError && error.status === 400)) set({ unsaved: true });
    },
  );
  inFlight.add(tracked);
  void tracked.finally(() => inFlight.delete(tracked));
}

const draftTimers = new Map<string, ReturnType<typeof setTimeout>>();

/** Send drafts still waiting for their pause, and wait until every save is done. */
async function flushSaves() {
  for (const [key, timer] of draftTimers) {
    clearTimeout(timer);
    background(api("/drafts", { method: "PUT", body: { key, code: state.drafts[key] } }));
  }
  draftTimers.clear();
  await Promise.all(inFlight);
}

// --- Starting up and signing in/out ------------------------------------------------

export async function initSession() {
  const { user } = await api<{ user: Me | null }>("/auth/me");
  if (user) await loadAccount(user);
  else set({ ...readGuest(), me: null });
}

async function loadAccount(user: Me) {
  const saved = await api<Saved>("/me/state");
  set({ ...saved, me: user, unsaved: false });
}

async function afterSignIn(user: Me) {
  const guest = readGuest();
  if (hasProgress(guest)) {
    await api("/me/import", { method: "POST", body: guest });
    clearGuest();
  }
  await loadAccount(user);
  await loadCatalog(); // solutions and team courses depend on who's signed in
}

export interface SignupData {
  username: string;
  pin: string;
  display_name: string;
  avatar: string;
  join_code: string;
}

export async function signUp(data: SignupData) {
  const { user } = await api<{ user: Me }>("/auth/signup", { method: "POST", body: data });
  await afterSignIn(user);
}

export async function signIn(username: string, secret: string) {
  const { user } = await api<{ user: Me }>("/auth/login", { method: "POST", body: { username, secret } });
  await afterSignIn(user);
}

export async function signOut() {
  await flushSaves(); // so nothing the student just did is lost
  await api("/auth/logout", { method: "POST" });
  set({ ...readGuest(), me: null, unsaved: false });
  await loadCatalog();
}

export async function joinTeam(code: string) {
  const { user } = await api<{ user: Me }>("/teams/join", { method: "POST", body: { code } });
  set({ me: user });
  await loadCatalog();
}

/** After changing teams on the coach pages: update the teams list, and solutions in the catalog. */
export async function refreshMe() {
  const { user } = await api<{ user: Me | null }>("/auth/me");
  if (user && state.me) set({ me: user });
  await loadCatalog();
}

/** Coaches, mentors and adults get the team pages. */
export const usesTeamPages = (me: Me | null) =>
  Boolean(me && (me.kind === "adult" || me.is_staff || me.teams.some((t) => t.role !== "student")));

/** The first of your teams with a real robot set up, if any. */
export function teamWithRobot(me: Me | null): Team | null {
  return me?.teams.find((t) => t.robot) ?? null;
}

export const suggestUsername = () => api<{ username: string }>("/auth/suggest-username").then((r) => r.username);

// --- Progress ------------------------------------------------------------------------

export function lessonProgress(lessonId: string): LessonProgress {
  return state.lessons[lessonId] ?? { page: 0, done: [], finished: false };
}

function updateLesson(lessonId: string, change: (p: LessonProgress) => LessonProgress) {
  const before = lessonProgress(lessonId);
  const after = change(before);
  if (after === before) return;
  set({ lessons: { ...state.lessons, [lessonId]: after } });
  if (state.me) background(api(`/progress/${encodeURIComponent(lessonId)}`, { method: "PUT", body: after }));
  else persistGuest();
}

export function markDone(lessonId: string, blockId: string) {
  updateLesson(lessonId, (p) => (p.done.includes(blockId) ? p : { ...p, done: [...p.done, blockId] }));
}

export function reachPage(lessonId: string, page: number) {
  updateLesson(lessonId, (p) => (page > p.page ? { ...p, page } : p));
}

export function finishLesson(lessonId: string) {
  updateLesson(lessonId, (p) => (p.finished ? p : { ...p, finished: true }));
}

// --- Saved code ------------------------------------------------------------------------

export const draft = (key: string): string | undefined => state.drafts[key];

export function saveDraft(key: string, code: string) {
  if (state.drafts[key] === code) return;
  set({ drafts: { ...state.drafts, [key]: code } });
  if (!state.me) {
    persistGuest();
    return;
  }
  clearTimeout(draftTimers.get(key));
  draftTimers.set(
    key,
    setTimeout(() => {
      draftTimers.delete(key);
      background(api("/drafts", { method: "PUT", body: { key, code: state.drafts[key] } }));
    }, 800),
  );
}

// --- Challenge results -------------------------------------------------------------------

export interface AttemptData {
  key: string;
  code: string;
  passed: boolean;
  goals: { id: string; passed: boolean }[];
  sim_version: string;
  lesson_id?: string;
  block_id?: string;
}

export function recordAttempt(attempt: AttemptData) {
  if (attempt.passed && attempt.key.startsWith("playground/")) {
    const id = attempt.key.slice("playground/".length);
    if (!state.solved.includes(id)) {
      set({ solved: [...state.solved, id] });
      persistGuest();
    }
  }
  if (state.me) background(api("/attempts", { method: "POST", body: attempt }));
}
