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
  /** Playground group, like "Driving" or "Sensors". */
  section?: string;
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
  type:
    | "collision" | "stalled" | "beep" | "display" | "light"
    // Mission Mode
    | "blocked" | "state" | "pressed" | "interruption" | "run_end" | "teammate";
  line: number;
  what?: string;
  frequency?: number;
  duration?: number;
  text?: string;
  color?: string;
  // Mission Mode
  model?: string;
  state?: string;
  port?: string;
  run?: number;
  how?: string;
  action?: "press" | "place";
  tokens?: number;
  presses?: number;
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
  /** Only for Mission Mode runs (trainer_sim.missions). */
  mission?: MissionTrace;
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

// --- Mission Mode (content/missions/, trainer_sim/missions) ----------------------------

export interface AttachmentSpec {
  id: string;
  name: string;
  kind: "lift" | "sweep" | "slide";
  port: "E" | "F";
  summary?: string;
  mount?: [number, number];
  direction?: number;
  length: number;
  width?: number;
  mount_z?: number;
  rest_angle?: number;
  min_angle?: number;
  max_angle?: number;
  gears?: number;
  travel?: number;
  hook?: boolean | { at?: number };
  z?: [number, number];
}

export interface ModelSpec {
  id: string;
  type: "block" | "lever" | "button" | "loop" | "flag" | "gate";
  label?: string;
  hidden?: boolean;
  at?: [number, number];
  size?: [number, number];
  r?: number;
  angle?: number;
  hinge?: [number, number];
  length?: number;
  width?: number;
  to?: number;
  states?: string[];
  pole?: [number, number];
  [key: string]: unknown;
}

/** A model's state at one moment (see Model.snapshot in trainer_sim/missions/models.py). */
export interface ModelState {
  state: string;
  hidden: boolean;
  x?: number;
  y?: number;
  z?: number;
  angle?: number;
  presses?: number;
  down?: boolean;
}

export interface MissionScoreRow {
  id: string;
  title: string;
  points: number;
}

export interface MissionRunLog {
  run: number;
  start: number;
  end: number | null;
  ended: "home" | "interrupted" | null;
  attachments: Record<string, string>;
}

export interface MissionTrace {
  initial: Record<string, ModelState>;
  changes: [frame: number, model: string, state: ModelState][];
  arms: Record<string, (number | null)[]>;
  mounts: [frame: number, port: string, attachment: string | null][];
  attachments: Record<string, AttachmentSpec>;
  runs: MissionRunLog[];
  home: string;
  score: {
    total: number;
    missions: MissionScoreRow[];
    tokens: number;
    token_start: number;
    token_points: number;
    timeline: [t: number, total: number][];
  };
  stars: number;
  thresholds: [number, number, number] | null;
  seeds: { seed: number; score: number; passed: boolean }[];
}

export interface MissionTier {
  id: number;
  icon: string;
  title: string;
  summary: string;
}

export interface MissionInfo {
  id: string;
  title: string;
  score: unknown[];
}

export interface GameSpec {
  id: string;
  title: string;
  summary?: string;
  tiers: MissionTier[];
  field: WorldSpec;
  home: string;
  models: ModelSpec[];
  attachments: AttachmentSpec[];
  robot: RobotSpec;
  missions: MissionInfo[];
  precision_tokens?: { start: number; points: number[] };
}

export interface MissionRunSpec {
  start?: Partial<Pose>;
  attachments?: Record<string, string>;
  choose?: Record<string, string[]>;
  rest?: Record<string, number>;
}

export interface MissionChallenge {
  id: string;
  title: string;
  tier: number;
  summary?: string;
  instructions?: string;
  runs?: MissionRunSpec[];
  models?: string[];
  missions?: string[];
  goals?: GoalSpec[];
  stars?: [number, number, number];
  seeds?: number[];
  realism?: Realism;
  time_limit?: number;
  handling_time?: number;
  start_button?: string;
  hints?: string[];
  starter: string;
  solution?: string;
  solution_attachments?: Record<string, string>[];
}

/** One challenge on the ladder (GET /api/missions). `unlocked` is null for guests. */
export interface LadderChallenge {
  id: string;
  title: string;
  tier: number;
  summary: string;
  unlocked: boolean | null;
  stars: number;
  best_score: number;
}

export interface LadderGame {
  id: string;
  title: string;
  summary?: string;
  tiers: MissionTier[];
  challenges: LadderChallenge[];
}

export interface MissionRunRequest {
  code: string;
  game: GameSpec;
  challenge: MissionChallenge;
  /** Attachments picked for each run, e.g. [{E: "pusher"}, {E: "forklift"}]. */
  choices: Record<string, string>[];
}
