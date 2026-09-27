// Getting simulator code onto a real robot with Pybricks (code.pybricks.com).
//
// Lesson code is written for the Trainer Bot. A team's real robot may use
// other ports or wheels, so forRobot() rewrites the setup to match: port
// letters, wheel directions and the DriveBase measurements. It also points
// out things that work differently on a real hub.

import { parser } from "@lezer/python";
import type { RobotSpec } from "./types";

export type Direction = "clockwise" | "counterclockwise";

/** Which port each part uses, and the wheel sizes (mm). Same shape as the backend's team robot. */
export interface TeamRobot {
  left_wheel: string;
  right_wheel: string;
  left_direction: Direction;
  right_direction: Direction;
  wheel_diameter: number;
  axle_track: number;
  color_sensor: string | null;
  ultrasonic_sensor: string | null;
  left_arm: string | null;
  right_arm: string | null;
}

export type PartKey = "left_wheel" | "right_wheel" | "color_sensor" | "ultrasonic_sensor" | "left_arm" | "right_arm";

export const PARTS: { key: PartKey; label: string; required: boolean }[] = [
  { key: "left_wheel", label: "Left wheel motor", required: true },
  { key: "right_wheel", label: "Right wheel motor", required: true },
  { key: "color_sensor", label: "Color sensor", required: false },
  { key: "ultrasonic_sensor", label: "Distance sensor", required: false },
  { key: "left_arm", label: "Left arm motor", required: false },
  { key: "right_arm", label: "Right arm motor", required: false },
];

export const PORTS = ["A", "B", "C", "D", "E", "F"];
export const PYBRICKS_URL = "https://code.pybricks.com";

/** The simulator's robot, described like a team robot. */
export function trainerRobot(spec: RobotSpec): TeamRobot {
  const ports = Object.entries(spec.ports).sort(([a], [b]) => a.localeCompare(b));
  const find = (test: (p: RobotSpec["ports"][string]) => boolean) => ports.find(([, p]) => test(p))?.[0] ?? null;
  const arms = ports.filter(([, p]) => p.role === "arm").map(([port]) => port);
  const left = find((p) => p.role === "left_wheel") ?? "A";
  const right = find((p) => p.role === "right_wheel") ?? "B";
  const direction = (port: string): Direction => (spec.ports[port]?.mirrored ? "counterclockwise" : "clockwise");
  return {
    left_wheel: left,
    right_wheel: right,
    left_direction: direction(left),
    right_direction: direction(right),
    wheel_diameter: spec.wheel_diameter,
    axle_track: spec.axle_track,
    color_sensor: find((p) => p.device === "color_sensor"),
    ultrasonic_sensor: find((p) => p.device === "ultrasonic_sensor"),
    left_arm: arms[0] ?? null,
    right_arm: arms[1] ?? null,
  };
}

export interface Conversion {
  code: string;
  /** What was changed to fit the robot, in plain words. */
  changes: string[];
  /** Things that will go wrong on the robot unless someone fixes them. */
  problems: string[];
  /** Good to know before running (Markdown). */
  tips: string[];
}

interface Edit {
  from: number;
  to: number;
  text: string;
}

/** The code with comments and strings blanked out, so only real code is matched. */
function codeOnly(code: string): string {
  const chars = code.split("");
  parser.parse(code).iterate({
    enter(node) {
      if (node.name === "Comment" || node.name === "String" || node.name === "FormatString") {
        for (let i = node.from; i < node.to; i++) if (chars[i] !== "\n") chars[i] = " ";
        return false;
      }
      return undefined;
    },
  });
  return chars.join("");
}

function applyEdits(code: string, edits: Edit[]): string {
  let result = code;
  for (const edit of [...edits].sort((a, b) => b.from - a.from)) {
    result = result.slice(0, edit.from) + edit.text + result.slice(edit.to);
  }
  return result;
}

/** Where a regex group matched (the regex needs the `d` flag). */
function span(match: RegExpExecArray | RegExpMatchArray, group: number): [number, number] {
  const found = match.indices?.[group];
  if (!found) throw new Error(`group ${group} didn't match`);
  return found;
}

const lineOf = (code: string, index: number) => code.slice(0, index).split("\n").length;
const other = (d: Direction): Direction => (d === "clockwise" ? "counterclockwise" : "clockwise");
const sameNumber = (text: string, value: number) => Math.abs(Number(text) - value) < 1e-9;
const mm = (value: number) => `${value} mm`;

/**
 * The code, changed to run on `team` (a robot built like the Trainer Bot when
 * null), plus what changed and what to watch out for.
 */
export function forRobot(code: string, trainer: TeamRobot, team: TeamRobot | null): Conversion {
  const plain = codeOnly(code);
  const edits: Edit[] = [];
  const changes: string[] = [];
  const problems: string[] = [];
  const tips: string[] = [];
  const target = team ?? trainer;

  // Ports: Port.A on the Trainer Bot is the left wheel, so it becomes the
  // team's left wheel port, and so on for every part.
  const partForPort = new Map(PARTS.filter((p) => trainer[p.key]).map((p) => [trainer[p.key] as string, p]));
  const reported = new Set<string>();
  for (const match of plain.matchAll(/\bPort\.([A-F])\b/dg)) {
    const part = partForPort.get(match[1]);
    if (!part) continue;
    const port = target[part.key];
    const [start, end] = span(match, 1);
    if (port === null) {
      const text = `Line ${lineOf(code, match.index)} uses \`Port.${match[1]}\`, the ${part.label.toLowerCase()} on the Trainer Bot. Your team's robot doesn't have one, so the program will stop there with an error.`;
      if (!reported.has(text)) problems.push(text);
      reported.add(text);
    } else if (port !== match[1]) {
      edits.push({ from: start, to: end, text: port });
      const text = `${part.label}: \`Port.${match[1]}\` → \`Port.${port}\``;
      if (!reported.has(text)) changes.push(text);
      reported.add(text);
    }
  }

  // Wheel directions: a motor mounted the other way needs the other Direction.
  let needsDirectionImport = false;
  const motorCall = /\bMotor\(\s*Port\.([A-F])\b(\s*,\s*(?:positive_direction\s*=\s*)?Direction\.(CLOCKWISE|COUNTERCLOCKWISE)\b)?/dg;
  for (const match of plain.matchAll(motorCall)) {
    const side = match[1] === trainer.left_wheel ? "left" : match[1] === trainer.right_wheel ? "right" : null;
    if (!side || target[`${side}_direction`] === trainer[`${side}_direction`]) continue;
    const written: Direction = match[3] === "COUNTERCLOCKWISE" ? "counterclockwise" : "clockwise";
    const wanted = other(written); // flip whatever the program says, to keep its meaning
    if (match[2]) {
      const [from, to] = span(match, 3);
      edits.push({ from, to, text: wanted.toUpperCase() });
    } else {
      const at = span(match, 1)[1];
      edits.push({ from: at, to: at, text: ", Direction.COUNTERCLOCKWISE" });
      needsDirectionImport = true;
    }
    changes.push(`The ${side} wheel motor faces the other way on your robot: \`Direction.${wanted.toUpperCase()}\``);
  }
  const importsDirection = /\bimport\b[^\n]*\bDirection\b|^from pybricks\.parameters import \*/m.test(plain);
  if (needsDirectionImport && !importsDirection) {
    const parameters = /^from pybricks\.parameters import ([^\n(]+)$/m.exec(plain);
    if (parameters) {
      const at = parameters.index + parameters[0].trimEnd().length;
      edits.push({ from: at, to: at, text: ", Direction" });
    } else {
      edits.push({ from: 0, to: 0, text: "from pybricks.parameters import Direction\n" });
    }
  }

  // Wheel sizes: swap the Trainer Bot's measurements for the robot's.
  const usesDriveBase = /\bDriveBase\(/.test(plain);
  let sizesFound = false;
  const replaceSize = (text: string, [from, to]: [number, number], key: "wheel_diameter" | "axle_track") => {
    sizesFound = true;
    if (!sameNumber(text, trainer[key]) || sameNumber(text, target[key])) return;
    edits.push({ from, to, text: String(target[key]) });
    changes.push(`\`${key}\`: ${mm(trainer[key])} → ${mm(target[key])}`);
  };
  for (const key of ["wheel_diameter", "axle_track"] as const) {
    for (const match of plain.matchAll(new RegExp(`\\b${key}\\s*=\\s*(\\d+(?:\\.\\d+)?)\\b`, "dg"))) {
      replaceSize(match[1], span(match, 1), key);
    }
  }
  // DriveBase(left, right, 56, 112) without the names.
  for (const match of plain.matchAll(/\bDriveBase\([^(),]+,[^(),]+,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)/dg)) {
    replaceSize(match[1], span(match, 1), "wheel_diameter");
    replaceSize(match[2], span(match, 2), "axle_track");
  }
  const sizesDiffer = target.wheel_diameter !== trainer.wheel_diameter || target.axle_track !== trainer.axle_track;
  if (usesDriveBase && sizesDiffer && !sizesFound) {
    problems.push(
      `Your robot's wheels are ${mm(target.wheel_diameter)} across and ${mm(target.axle_track)} apart. ` +
        "Check the numbers you give `DriveBase()`, or it will drive the wrong distances.",
    );
  }

  // Things that work differently on a real hub.
  if (/\bbuttons\.pressed\(/.test(plain) && !/\bset_stop_button\(/.test(plain)) {
    tips.push(
      "The **center button** stops programs on a real hub. If you press it to start a mission, add " +
        "`hub.system.set_stop_button(Button.BLUETOOTH)` near the top first.",
    );
  }
  if (/\b(ColorSensor|UltrasonicSensor)\(/.test(plain)) {
    tips.push(
      "Real sensors see a little differently than the simulator. `print()` the readings on your real mat, " +
        "and adjust the numbers your program compares them with.",
    );
  }
  if (/^\s*(import|from)\s+(math|random)\b/m.test(plain)) {
    tips.push("If Pybricks says there's no module named `math` or `random`, update the hub's firmware, or write `umath` / `urandom` instead.");
  }
  tips.push(
    "Real robots aren't perfect: wheels slip and batteries run down, so the robot won't stop in exactly the same " +
      "spot as in the simulator. Test it, measure, and adjust your numbers.",
  );

  return { code: applyEdits(code, edits), changes: [...new Set(changes)], problems, tips };
}
