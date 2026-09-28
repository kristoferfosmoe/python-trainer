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

/** Best result on a Mission Mode challenge. Only ever goes up. */
export interface MissionResult {
  stars: number;
  best_score: number;
}

interface Saved {
  lessons: Record<string, LessonProgress>;
  solved: string[];
  drafts: Record<string, string>;
  missions: Record<string, MissionResult>;
}

export interface SessionState extends Saved {
  me: Me | null;
  unsaved: boolean; // a save to the server failed; it's tried again
  /** The server signed the student out (a new PIN, or the session ran out): their work waits until they sign in again. */
  signedOut: boolean;
  /** Still signed in from an earlier visit. On a shared computer, that might be someone else. */
  restored: boolean;
}

const GUEST_KEY = "guest:v1";
const EMPTY: Saved = { lessons: {}, solved: [], drafts: {}, missions: {} };
const listeners = new Set<() => void>();
let state: SessionState = { ...EMPTY, me: null, unsaved: false, signedOut: false, restored: false };

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
  const saved: Saved = { lessons: {}, solved: [], drafts: {}, missions: {} };
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
  Object.keys(saved.lessons).length > 0 || saved.solved.length > 0 || Object.keys(saved.drafts).length > 0 ||
  Object.keys(saved.missions).length > 0;

function persistGuest() {
  if (!state.me) writeGuest({ lessons: state.lessons, solved: state.solved, drafts: state.drafts, missions: state.missions });
}

// --- Server sync -----------------------------------------------------------------
//
// Every change is a save with a key. A lesson's progress and an editor's code
// only need their newest version sent; each challenge run is a save of its own.
// A save that fails because of the network or the server is kept and tried
// again: after 5 seconds, then less and less often, and as soon as the
// connection comes back. If the server has signed the student out, their
// saves wait until the same student signs in again (someone else signing in
// on this computer never gets them). Saves the server refuses (like a program
// that's too long) are dropped, since sending them again wouldn't help.

interface Save {
  key: string;
  seq: number; // newer saves of the same key have bigger numbers
  user: string; // whose work it is
  path: string;
  method: "PUT" | "POST";
  body: unknown;
}

const FIRST_RETRY_MS = 5_000;
const LAST_RETRY_MS = 60_000;
let seq = 0;
const inFlight = new Set<Promise<void>>();
const unsent = new Map<string, Save>();
let retryDelay = FIRST_RETRY_MS;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let returnHash: string | null = null; // where the student was when they were signed out

const worthRetrying = (error: unknown) =>
  !(error instanceof ApiError) || error.status === 0 || error.status === 401 || error.status >= 500;

function save(key: string, path: string, method: Save["method"], body: unknown) {
  if (state.me) void send({ key, seq: ++seq, user: state.me.username, path, method, body });
}

function send(item: Save): Promise<void> {
  const tracked = api(item.path, { method: item.method, body: item.body }).then(
    () => {
      if ((unsent.get(item.key)?.seq ?? Infinity) <= item.seq) unsent.delete(item.key);
      retryDelay = FIRST_RETRY_MS;
      if (state.unsaved && unsent.size === 0) set({ unsaved: false });
    },
    (error) => {
      console.warn("Couldn't save to the server", error);
      if (!worthRetrying(error)) return;
      if ((unsent.get(item.key)?.seq ?? -1) < item.seq) unsent.set(item.key, item);
      if (error instanceof ApiError && error.status === 401) {
        if (!state.signedOut && typeof window !== "undefined") returnHash = window.location.hash;
        set({ unsaved: true, signedOut: true });
      } else {
        set({ unsaved: true });
        scheduleRetry();
      }
    },
  );
  inFlight.add(tracked);
  void tracked.finally(() => inFlight.delete(tracked));
  return tracked;
}

function scheduleRetry() {
  if (retryTimer !== null) return;
  retryTimer = setTimeout(retryNow, retryDelay);
  retryDelay = Math.min(retryDelay * 2, LAST_RETRY_MS);
}

function retryNow() {
  if (retryTimer !== null) clearTimeout(retryTimer);
  retryTimer = null;
  const me = state.me;
  if (!me || state.signedOut) return;
  for (const item of [...unsent.values()]) if (sameUser(item.user, me.username)) void send(item);
}

const sameUser = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();

/** After a sign-in: send the work that was waiting, if it's this student's.
 * Anyone else's is dropped, never sent as this student. */
async function sendWaiting(user: Me) {
  const waiting = [...unsent.values()];
  unsent.clear();
  await Promise.all(waiting.filter((item) => sameUser(item.user, user.username)).map(send));
}

if (typeof window !== "undefined") {
  window.addEventListener("online", retryNow);
  window.addEventListener("beforeunload", (event) => {
    if (unsent.size > 0) event.preventDefault(); // "Leave site? Changes you made may not be saved."
  });
}

const draftTimers = new Map<string, ReturnType<typeof setTimeout>>();

const saveDraftNow = (key: string) => save(`draft:${key}`, "/drafts", "PUT", { key, code: state.drafts[key] });

/** Send drafts still waiting for their pause, and wait until every save is done. */
async function flushSaves() {
  for (const [key, timer] of draftTimers) {
    clearTimeout(timer);
    saveDraftNow(key);
  }
  draftTimers.clear();
  retryNow();
  await Promise.all(inFlight);
}

/** Where to go back to after signing in again (see signedOut). */
export function takeReturnHash(): string | null {
  const hash = returnHash;
  returnHash = null;
  return hash;
}

// --- Starting up and signing in/out ------------------------------------------------

export async function initSession() {
  const { user } = await api<{ user: Me | null }>("/auth/me");
  if (user) {
    await loadAccount(user);
    set({ restored: true });
  } else set({ ...readGuest(), me: null });
}

/** The "Not you?" note has been seen. */
export const dismissRestored = () => set({ restored: false });

async function loadAccount(user: Me) {
  const saved = await api<Saved>("/me/state");
  set({ ...EMPTY, ...saved, me: user, unsaved: unsent.size > 0 });
}

async function afterSignIn(user: Me) {
  await sendWaiting(user); // before loading the account, so it includes them
  set({ signedOut: false });
  const guest = readGuest();
  if (hasProgress(guest)) {
    await api("/me/import", { method: "POST", body: guest });
    clearGuest();
  }
  await loadAccount(user);
  set({ restored: false });
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
  set({ ...readGuest(), me: null, unsaved: false, signedOut: false, restored: false });
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
  if (state.me) save(`progress:${lessonId}`, `/progress/${encodeURIComponent(lessonId)}`, "PUT", after);
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
      saveDraftNow(key);
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
  save(`attempt:${seq + 1}`, "/attempts", "POST", attempt);
}

// --- Mission Mode results --------------------------------------------------------------------

export function missionResult(challengeId: string): MissionResult {
  return state.missions[challengeId] ?? { stars: 0, best_score: 0 };
}

/** Keep the best stars and score for a mission challenge (never lowers them). */
export function recordMissionResult(challengeId: string, stars: number, score: number) {
  const before = missionResult(challengeId);
  const after = { stars: Math.max(before.stars, stars), best_score: Math.max(before.best_score, score) };
  if (state.missions[challengeId] && after.stars === before.stars && after.best_score === before.best_score) return;
  set({ missions: { ...state.missions, [challengeId]: after } });
  if (state.me) {
    save(`mission:${challengeId}`, `/missions/challenges/${encodeURIComponent(challengeId)}/progress`, "PUT", { stars, score });
  } else persistGuest();
}
