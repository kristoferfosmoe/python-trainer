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
  world?: string; // no world: a console-only challenge
  start?: Pose;
  time_limit?: number;
  realism?: Realism;
  summary?: string;
  instructions?: string;
  goals?: GoalSpec[];
  hints?: string[];
  starter: string;
  solution?: string;
  /** Scripted hub button presses, e.g. a teammate pressing CENTER. */
  buttons?: ButtonPress[];
}

/** "on"/"off", or custom amounts: {slip, wheel_mismatch, gyro_drift, sensor_noise}. */
export type Realism = string | boolean | Record<string, number>;

export interface ButtonPress {
  at: number; // ms
  button: "LEFT" | "RIGHT" | "CENTER";
  duration?: number;
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

export interface CodeStructure {
  line: number;
  body: [first: number, last: number];
  kind: "for" | "while" | "if" | "elif";
  target?: string;
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
  structure: CodeStructure[];
  goals: GoalResult[];
  stats: { lines: number; sim_ms: number; wall_ms: number };
}

export interface RunRequest {
  code: string;
  world: WorldSpec;
  robot: RobotSpec;
  options: {
    time_limit?: number;
    realism?: Realism;
    start?: Pose;
    seed?: number;
    buttons?: ButtonPress[];
  };
  goals?: GoalSpec[];
}

// --- Lessons -------------------------------------------------------------------

export interface TextBlock {
  type: "text";
  id: string;
  markdown: string;
}

export interface CodeBlock {
  type: "example" | "visualize";
  id: string;
  code: string;
  expect_error?: boolean;
}

export type QuizChoice = string | { text: string; why?: string };

export interface QuizBlock {
  type: "quiz";
  id: string;
  question: string;
  code?: string;
  check?: "output";
  choices: QuizChoice[];
  answer: number;
  explain?: string;
}

export interface ChallengeBlock extends Challenge {
  type: "challenge";
  ref?: string;
}

export type Block = TextBlock | CodeBlock | QuizBlock | ChallengeBlock;

export interface LessonSummary {
  id: string;
  title: string;
  summary: string;
}

export interface Lesson extends LessonSummary {
  concepts?: string[];
  blocks: Block[];
  version?: number;
}

export interface UnitSummary {
  id: string;
  title: string;
  icon?: string;
  summary: string;
  lessons: LessonSummary[];
}

export interface CourseSummary {
  id: string;
  title: string;
  summary: string;
  units: UnitSummary[];
}
