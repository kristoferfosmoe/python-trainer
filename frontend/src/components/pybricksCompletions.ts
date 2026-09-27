// Autocomplete for the parts of the Pybricks API the simulator supports.

import type { Completion, CompletionContext, CompletionResult } from "@codemirror/autocomplete";

const m = (label: string, info: string, apply?: string): Completion => ({
  label,
  info,
  type: "method",
  apply: apply ?? `${label}()`,
});
const c = (label: string, info = ""): Completion => ({ label, info, type: "constant" });

const DRIVE_BASE = [
  m("straight", "straight(distance) — drive this many mm (negative = backwards)", "straight(200)"),
  m("turn", "turn(angle) — turn in place, positive = right", "turn(90)"),
  m("curve", "curve(radius, angle) — drive along a curve", "curve(200, 90)"),
  m("drive", "drive(speed, turn_rate) — start driving and keep going", "drive(150, 0)"),
  m("stop", "stop() — stop the wheels"),
  m("distance", "distance() — mm driven since the start or reset()"),
  m("angle", "angle() — degrees turned since the start or reset()"),
  m("reset", "reset() — set distance() and angle() back to 0"),
  m("settings", "settings(straight_speed=..., turn_rate=...) — change speeds"),
  m("use_gyro", "use_gyro(True) — use the hub's gyro to drive straighter", "use_gyro(True)"),
  m("done", "done() — True when the last move has finished"),
  m("stalled", "stalled() — True if the robot is stuck"),
];

const MOTOR = [
  m("run", "run(speed) — spin forever at this speed (deg/s)", "run(500)"),
  m("run_angle", "run_angle(speed, angle) — spin by this many degrees", "run_angle(500, 90)"),
  m("run_target", "run_target(speed, target) — go to an angle", "run_target(500, 0)"),
  m("run_time", "run_time(speed, time) — spin for this many ms", "run_time(500, 1000)"),
  m("run_until_stalled", "run_until_stalled(speed) — spin until it can't move", "run_until_stalled(300)"),
  m("angle", "angle() — current angle in degrees"),
  m("reset_angle", "reset_angle(0) — set the angle to a new value", "reset_angle(0)"),
  m("speed", "speed() — current speed in deg/s"),
  m("hold", "hold() — stop and hold this position"),
  m("brake", "brake() — stop"),
];

const SENSORS = [
  m("reflection", "reflection() — how bright the mat is, 0 to 100"),
  m("color", "color() — the color under the sensor, like Color.BLACK"),
  m("hsv", "hsv() — hue, saturation and brightness"),
  m("distance", "distance() — mm to whatever is in front"),
];

const HUB = [
  { label: "imu", type: "property", info: "gyro: heading(), reset_heading(0)" },
  { label: "light", type: "property", info: "light.on(Color.RED), light.off()" },
  { label: "display", type: "property", info: "display.text('Hi'), display.number(42)" },
  { label: "speaker", type: "property", info: "speaker.beep(), speaker.play_notes([...])" },
  { label: "buttons", type: "property", info: "buttons.pressed()" },
  m("heading", "imu.heading() — which way the robot points (degrees)"),
  m("reset_heading", "imu.reset_heading(0)", "reset_heading(0)"),
  m("on", "light.on(Color.GREEN)", "on(Color.GREEN)"),
  m("off", "turn off the light or display"),
  m("text", "display.text('Hi')", "text('Hi')"),
  m("number", "display.number(42)", "number(42)"),
  m("beep", "speaker.beep(frequency, duration)", "beep(500, 100)"),
  m("play_notes", "speaker.play_notes(['C4/4', 'E4/4', 'G4/2'])", "play_notes(['C4/4', 'E4/4', 'G4/2'])"),
  m("pressed", "buttons.pressed() — set of pressed buttons"),
];

const CONSTANTS: Record<string, Completion[]> = {
  Port: ["A", "B", "C", "D", "E", "F"].map((p) => c(p)),
  Direction: [c("CLOCKWISE"), c("COUNTERCLOCKWISE")],
  Stop: [c("HOLD", "hold position"), c("BRAKE"), c("COAST", "roll to a stop"), c("NONE", "keep going")],
  Color: ["BLACK", "WHITE", "GRAY", "RED", "ORANGE", "YELLOW", "GREEN", "CYAN", "BLUE", "VIOLET", "MAGENTA", "BROWN", "NONE"].map((n) => c(n)),
  Button: [c("LEFT"), c("RIGHT"), c("CENTER")],
};

const MEMBERS = [...DRIVE_BASE, ...MOTOR, ...SENSORS, ...HUB].filter(
  (item, index, all) => all.findIndex((other) => other.label === item.label) === index,
);

const TOP_LEVEL: Completion[] = [
  { label: "PrimeHub", type: "class", info: "from pybricks.hubs import PrimeHub" },
  { label: "Motor", type: "class", info: "from pybricks.pupdevices import Motor" },
  { label: "ColorSensor", type: "class", info: "from pybricks.pupdevices import ColorSensor" },
  { label: "UltrasonicSensor", type: "class", info: "from pybricks.pupdevices import UltrasonicSensor" },
  { label: "DriveBase", type: "class", info: "from pybricks.robotics import DriveBase" },
  { label: "StopWatch", type: "class", info: "from pybricks.tools import StopWatch" },
  { label: "wait", type: "function", info: "wait(ms) — pause the program", apply: "wait(100)" },
  ...Object.keys(CONSTANTS).map((name) => ({ label: name, type: "class", info: `from pybricks.parameters import ${name}` })),
];

export function pybricksCompletions(context: CompletionContext): CompletionResult | null {
  const member = context.matchBefore(/[A-Za-z_]\w*\.\w*/);
  if (member) {
    const dot = member.text.indexOf(".");
    const owner = member.text.slice(0, dot);
    return {
      from: member.from + dot + 1,
      options: CONSTANTS[owner] ?? MEMBERS,
      validFor: /^\w*$/,
    };
  }
  const word = context.matchBefore(/[A-Za-z_]\w*/);
  if (!word || (word.from === word.to && !context.explicit)) return null;
  return { from: word.from, options: TOP_LEVEL, validFor: /^\w*$/ };
}
