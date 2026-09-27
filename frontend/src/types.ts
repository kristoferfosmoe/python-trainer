// Shapes of the content files (content/*.yaml) and of the simulator's trace.
// The trace is produced by sim/src/trainer_sim/runner.py.

export type ColorName =
  | "black" | "gray" | "white" | "red" | "orange" | "brown"
  | "yellow" | "green" | "cyan" | "blue" | "violet" | "magenta";

export type ShapeSpec =
  | { type: "rect"; x: number; y: number; w: number; h: number; angle?: number; color?: ColorName; id?: string; label?: string }
  | { type: "circle"; x: number; y: number; r: number; color?: ColorName; id?: string; label?: string }
  | { type: "line"; points: [number, number][]; width?: number; closed?: boolean; color: ColorName }
  | { type: "arc"; x: number; y: number; r: number; width?: number; start?: number; end?: number; color: ColorName };

export type ZoneSpec = Extract<ShapeSpec, { type: "rect" } | { type: "circle" }> & { id: string; label?: string };

export interface Pose {
  x: number;
  y: number;
  heading: number;
}

export interface WorldSpec {
  id: string;
  name: string;
  size: [number, number];
  background?: ColorName;
  grid?: number;
  start?: Partial<Pose>;
  shapes?: ShapeSpec[];
  zones?: ZoneSpec[];
  obstacles?: (Extract<ShapeSpec, { type: "rect" } | { type: "circle" }> & { label?: string })[];
}

export interface PortSpec {
  device: "motor" | "color_sensor" | "ultrasonic_sensor" | "force_sensor";
  role?: "left_wheel" | "right_wheel" | "arm";
  label?: string;
  mirrored?: boolean;
  position?: [number, number];
  min_angle?: number;
  max_angle?: number;
}

export interface RobotSpec {
  id: string;
  name: string;
  wheel_diameter: number;
  axle_track: number;
  body: { front: number; back: number; width: number };
  ports: Record<string, PortSpec>;
}

export interface GoalSpec {
  type: string;
  [key: string]: unknown;
}

export interface Challenge {
  id: string;
  title: string;
  world: string;
  start?: Pose;
  time_limit?: number;
  realism?: string | boolean;
  summary: string;
  instructions: string;
  goals?: GoalSpec[];
  hints?: string[];
  starter: string;
  solution?: string;
}

// --- Trace -------------------------------------------------------------------

export interface KidError {
  type: string;
  line: number | null;
  python_message: string;
  kid_message: string;
}

export interface EndInfo {
  reason: "finished" | "error" | "time_limit" | "step_limit";
  t: number;
  line: number | null;
  error?: KidError;
}

export interface TraceEvent {
  t: number;
  type: "collision" | "stalled" | "beep" | "display" | "light";
  line: number;
  what?: string;
  frequency?: number;
  duration?: number;
  text?: string;
  color?: string;
}

export interface GoalResult {
  id: string;
  type: string;
  label: string;
  passed: boolean;
  detail: string;
}

export type VarEntry = [name: string, value: string, scope: "global" | "local"];

export interface Trace {
  sim_version: string;
  frame_ms: number;
  start: Pose;
  frames: { t: number[]; x: number[]; y: number[]; heading: number[]; line: number[] };
  sensors: Record<string, (number | string)[]>;
  motors: Record<string, number[]>;
  steps: [number, number][];
  steps_truncated: boolean;
  vars: { t: number; vars: VarEntry[] }[];
  prints: { t: number; line: number; text: string }[];
  prints_truncated: boolean;
  events: TraceEvent[];
  end: EndInfo;
  warnings: { line: number; message: string }[];
  goals: GoalResult[];
  stats: { lines: number; sim_ms: number; wall_ms: number };
}

export interface RunRequest {
  code: string;
  world: WorldSpec;
  robot: RobotSpec;
  options: {
    time_limit?: number;
    realism?: string | boolean;
    start?: Pose;
    seed?: number;
  };
  goals?: GoalSpec[];
}
