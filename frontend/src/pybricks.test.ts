import { readFileSync } from "node:fs";
import { load } from "js-yaml";
import { describe, expect, it } from "vitest";
import { forRobot, trainerRobot, type TeamRobot } from "./pybricks";
import type { RobotSpec } from "./types";

const spec = load(readFileSync(new URL("../../content/robots/trainer-bot.yaml", import.meta.url), "utf8")) as RobotSpec;
const trainer = trainerRobot(spec);

const SETUP = `from pybricks.pupdevices import Motor, ColorSensor
from pybricks.parameters import Port, Direction
from pybricks.robotics import DriveBase

left_motor = Motor(Port.A, Direction.COUNTERCLOCKWISE)
right_motor = Motor(Port.B)
drive_base = DriveBase(left_motor, right_motor, wheel_diameter=56, axle_track=112)
`;

const team = (change: Partial<TeamRobot> = {}): TeamRobot => ({ ...trainer, ...change });

describe("trainerRobot", () => {
  it("describes the Trainer Bot's ports", () => {
    expect(trainer).toEqual({
      left_wheel: "A", right_wheel: "B", left_direction: "counterclockwise", right_direction: "clockwise",
      wheel_diameter: 56, axle_track: 112, color_sensor: "C", ultrasonic_sensor: "D", left_arm: "E", right_arm: "F",
    });
  });
});

describe("forRobot", () => {
  it("leaves code alone for a robot built like the Trainer Bot", () => {
    for (const robot of [null, team()]) {
      const result = forRobot(SETUP, trainer, robot);
      expect(result.code).toBe(SETUP);
      expect(result.changes).toEqual([]);
      expect(result.problems).toEqual([]);
    }
  });

  it("moves every part to the team's ports, all at once", () => {
    const robot = team({ left_wheel: "B", right_wheel: "A", color_sensor: "E", left_arm: "C" });
    const code = SETUP + "sensor = ColorSensor(Port.C)\narm = Motor(Port.E)\n";
    const result = forRobot(code, trainer, robot);
    expect(result.code).toContain("left_motor = Motor(Port.B, Direction.COUNTERCLOCKWISE)");
    expect(result.code).toContain("right_motor = Motor(Port.A)");
    expect(result.code).toContain("sensor = ColorSensor(Port.E)");
    expect(result.code).toContain("arm = Motor(Port.C)");
    expect(result.changes).toContain("Left wheel motor: `Port.A` → `Port.B`");
    expect(result.changes).toHaveLength(4);
  });

  it("doesn't touch comments or text", () => {
    const code = `# The left wheel is on Port.A\nprint("Port.A", f"{Port.A}")\n` + SETUP;
    const result = forRobot(code, trainer, team({ left_wheel: "E", left_arm: "A" }));
    expect(result.code.split("\n").slice(0, 2)).toEqual([`# The left wheel is on Port.A`, `print("Port.A", f"{Port.A}")`]);
    expect(result.code).toContain("Motor(Port.E, Direction.COUNTERCLOCKWISE)");
  });

  it("swaps the wheel sizes, named or not", () => {
    const robot = team({ wheel_diameter: 88, axle_track: 120 });
    expect(forRobot(SETUP, trainer, robot).code).toContain("wheel_diameter=88, axle_track=120)");
    const positional = SETUP.replace("wheel_diameter=56, axle_track=112", "56, 112");
    expect(forRobot(positional, trainer, robot).code).toContain("DriveBase(left_motor, right_motor, 88, 120)");
    // A size the student changed on purpose stays.
    const wrong = SETUP.replace("wheel_diameter=56", "wheel_diameter=112");
    expect(forRobot(wrong, trainer, robot).code).toContain("wheel_diameter=112, axle_track=120");
  });

  it("asks to check sizes it can't find", () => {
    const code = SETUP.replace("wheel_diameter=56, axle_track=112", "WHEEL, TRACK");
    const result = forRobot(code, trainer, team({ wheel_diameter: 88 }));
    expect(result.problems[0]).toContain("88 mm across");
  });

  it("flips wheel directions for motors mounted the other way", () => {
    const robot = team({ left_direction: "clockwise", right_direction: "counterclockwise" });
    const result = forRobot(SETUP, trainer, robot);
    expect(result.code).toContain("left_motor = Motor(Port.A, Direction.CLOCKWISE)");
    expect(result.code).toContain("right_motor = Motor(Port.B, Direction.COUNTERCLOCKWISE)");
    // A program that got the direction wrong stays wrong in the same way.
    const mistake = SETUP.replace("Motor(Port.A, Direction.COUNTERCLOCKWISE)", "Motor(Port.A)");
    expect(forRobot(mistake, trainer, robot).code).toContain("left_motor = Motor(Port.A, Direction.COUNTERCLOCKWISE)");
  });

  it("adds the Direction import when it needs one", () => {
    const code = "from pybricks.pupdevices import Motor\nfrom pybricks.parameters import Port\nright_motor = Motor(Port.B)\n";
    const result = forRobot(code, trainer, team({ right_direction: "counterclockwise" }));
    expect(result.code).toBe(
      "from pybricks.pupdevices import Motor\nfrom pybricks.parameters import Port, Direction\n" +
        "right_motor = Motor(Port.B, Direction.COUNTERCLOCKWISE)\n",
    );
    const star = code.replace("import Port", "import *");
    expect(forRobot(star, trainer, team({ right_direction: "counterclockwise" })).code).toContain("import *\n");
  });

  it("warns about parts the robot doesn't have", () => {
    const code = SETUP + "eyes = UltrasonicSensor(Port.D)\nprint(eyes.distance(), Port.D)\n";
    const result = forRobot(code, trainer, team({ ultrasonic_sensor: null }));
    expect(result.problems).toHaveLength(2);
    expect(result.problems[0]).toMatch(/^Line 8 uses `Port.D`, the distance sensor/);
    expect(result.code).toContain("UltrasonicSensor(Port.D)");
  });

  it("warns that the center button stops programs", () => {
    const waiting = SETUP + "while not hub.buttons.pressed():\n    wait(10)\n";
    expect(forRobot(waiting, trainer, null).tips[0]).toContain("set_stop_button(Button.BLUETOOTH)");
    const fixed = "hub.system.set_stop_button(Button.BLUETOOTH)\n" + waiting;
    expect(forRobot(fixed, trainer, null).tips.join()).not.toContain("center button");
  });
});
