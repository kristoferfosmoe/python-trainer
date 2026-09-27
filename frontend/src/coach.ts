// The coach tools' API: teams, students' progress and accounts, and the
// team's robot. Coaches and mentors can look; only coaches change things.

import { api } from "./api";
import type { LessonProgress } from "./session";
import type { TeamRobot } from "./pybricks";

export type Role = "student" | "mentor" | "coach";

export interface TeamInfo {
  id: number;
  name: string;
  season: string;
  join_code: string;
  robot: TeamRobot | null;
}

export interface TeamListing {
  teams: { id: number; name: string; season: string; role: Role | "staff"; students: number }[];
  can_create: boolean;
}

export interface Person {
  username: string;
  display_name: string;
  avatar: string;
  role: Role;
  locked: boolean;
  joined_at: string;
}

export interface StudentRow extends Person {
  lessons: Record<string, LessonProgress>;
  attempts: number;
  solved: number;
  last_active: string | null;
}

export interface Dashboard {
  team: TeamInfo;
  role: Role | "staff";
  can_manage: boolean;
  students: StudentRow[];
  leaders: Person[];
}

export interface ChallengeWork {
  key: string;
  title: string;
  where: string;
  lesson: string | null;
  attempts: number;
  passed: boolean;
  last_at: string | null;
  last_passed: boolean | null;
  last_code: string | null;
  last_goals: { id: string; passed: boolean }[];
  passed_code: string | null;
  draft: string | null;
}

export interface MemberDetail {
  team: { id: number; name: string };
  student: Person & { last_active: string | null };
  can_manage: boolean;
  lessons: Record<string, LessonProgress & { updated_at: string }>;
  challenges: ChallengeWork[];
}

/** A new account or PIN, shown once so the coach can hand it out. */
export interface LoginCard {
  username: string;
  display_name: string;
  pin: string;
}

const team = (id: number) => `/teams/${id}`;
const member = (id: number, username: string) => `/teams/${id}/members/${encodeURIComponent(username)}`;

export const listTeams = () => api<TeamListing>("/teams");
export const createTeam = (name: string, season: string) =>
  api<TeamInfo>("/teams", { method: "POST", body: { name, season } });
export const loadDashboard = (id: number) => api<Dashboard>(team(id));
export const changeTeam = (id: number, change: { name?: string; season?: string; robot?: TeamRobot | Record<string, never> }) =>
  api<TeamInfo>(team(id), { method: "PATCH", body: change });
export const newJoinCode = (id: number) => api<TeamInfo>(`${team(id)}/join-code`, { method: "POST" });
export const loadMember = (id: number, username: string) => api<MemberDetail>(member(id, username));
export const newPin = (id: number, username: string) => api<LoginCard>(`${member(id, username)}/pin`, { method: "POST" });
export const unlock = (id: number, username: string) => api(`${member(id, username)}/unlock`, { method: "POST" });
export const setRole = (id: number, username: string, role: "student" | "mentor") =>
  api(member(id, username), { method: "PATCH", body: { role } });
export const removeMember = (id: number, username: string) => api(member(id, username), { method: "DELETE" });

const BATCH = 10; // the server hashes each new PIN, so accounts are made a few at a time

/** Make student accounts, a batch at a time, reporting progress. */
export async function createStudents(
  id: number,
  students: { display_name: string; username: string }[],
  onProgress: (made: LoginCard[]) => void,
): Promise<LoginCard[]> {
  const made: LoginCard[] = [];
  for (let i = 0; i < students.length; i += BATCH) {
    const { created } = await api<{ created: LoginCard[] }>(`${team(id)}/members`, {
      method: "POST",
      body: { students: students.slice(i, i + BATCH) },
    });
    made.push(...created);
    onProgress([...made]);
  }
  return made;
}

/** "Sam" or "Sam, RoboSam" per line: a nickname and, if wanted, a username. */
export function parseStudentList(text: string): { display_name: string; username: string }[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [display_name, username = ""] = line.split(",").map((part) => part.trim());
      return { display_name, username };
    });
}
