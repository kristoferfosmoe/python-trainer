"""The simulation: virtual clock, robot physics, sensors and the recording.

Time is virtual. Blocking commands such as ``straight()`` or ``wait()``
move the clock forward, and every line of student code costs a little time
too, so loops that never call ``wait()`` still let the robot move. The
physics runs in fixed 5 ms ticks.
"""

import math
import random

from pybricks.parameters import Button

from .errors import DeviceError, StepLimit, TimeUp
from .motion import SimMotor
from .robot import RobotSpec
from .shapes import to_world
from .snapshot import snapshot
from .world import ULTRASONIC_MAX, ULTRASONIC_MIN, World

DT_MS = 5.0
RECORD_EVERY = 4  # ticks per recorded frame (20 ms)
LINE_COST_MS = 0.25

REALISM_PRESETS = {
    "off": {},
    "on": {"wheel_mismatch": 0.025, "slip": 0.01, "gyro_drift": 0.05, "sensor_noise": 1.5},
}


class Realism:
    def __init__(self, spec):
        if isinstance(spec, bool) or spec is None:  # YAML reads `on`/`off` as booleans
            spec = "on" if spec else "off"
        if isinstance(spec, str):
            if spec not in REALISM_PRESETS:
                raise ValueError(f"realism must be one of {', '.join(REALISM_PRESETS)} or a dictionary")
            spec = REALISM_PRESETS[spec]
        spec = spec or {}
        self.wheel_mismatch = float(spec.get("wheel_mismatch", 0))  # left wheel smaller by this fraction
        self.slip = float(spec.get("slip", 0))  # random travel lost per tick
        self.gyro_drift = float(spec.get("gyro_drift", 0))  # deg/s
        self.sensor_noise = float(spec.get("sensor_noise", 0))  # standard deviation


class Simulation:
    def __init__(self, world, robot, options=None):
        options = options or {}
        self.world = world if isinstance(world, World) else World(world)
        self.robot = robot if isinstance(robot, RobotSpec) else RobotSpec(robot)
        self.time_limit_ms = float(options.get("time_limit", 150)) * 1000
        self.max_lines = int(options.get("max_lines", 2_000_000))
        self.realism = Realism(options.get("realism", "off"))
        self.rng = random.Random(options.get("seed", 1))
        self.button_presses = options.get("buttons", [])

        self.now = 0.0  # virtual time in ms
        self.phys_t = 0.0  # time of the last physics tick
        self.ticks = 0
        start = options.get("start")
        if start:
            self.start = (float(start["x"]), float(start["y"]), float(start.get("heading", 0)))
        else:
            self.start = self.world.start
        self.x, self.y, self.heading = self.start
        self.start_heading = self.heading
        self.motors = {port: SimMotor(port, spec) for port, spec in self.robot.motor_ports()}
        mismatch = self.realism.wheel_mismatch
        self.wheel_scale = {
            self.robot.left_port: 1 - mismatch / 2,
            self.robot.right_port: 1 + mismatch / 2,
        }
        self.drivebases = []
        self.in_contact = None
        self.speed = 0.0  # mm/s
        self.turn_rate = 0.0  # deg/s, clockwise
        self.imu_offset = 0.0
        self.current_line = 0
        self.current_frame = None
        self.module_frame = None
        self.vars_dirty = False
        self.lines_executed = 0
        self._sensor_cache = {}
        self.recorder = Recorder(self)
        self.recorder.frame()

    # --- Clock -------------------------------------------------------------------

    def check_time(self):
        if self.now >= self.time_limit_ms:
            raise TimeUp()

    def advance(self, ms):
        """Let `ms` milliseconds of robot time pass."""
        self.check_time()
        target = min(self.now + max(0.0, ms), self.time_limit_ms)
        while self.phys_t + DT_MS <= target + 1e-9:
            self._tick()
        self.now = max(self.now, target)
        self.check_time()

    def run_until(self, condition):
        """Keep the robot moving until condition() is true (blocking commands)."""
        while not condition():
            self.check_time()
            self._tick()
            self.now = max(self.now, self.phys_t)
        self.check_time()

    def on_line(self, frame):
        """Called before every line of student code runs."""
        self.lines_executed += 1
        if self.lines_executed > self.max_lines:
            raise StepLimit()
        self.current_line = frame.f_lineno
        self.current_frame = frame
        if frame.f_code.co_name == "<module>":
            self.module_frame = frame
        self.vars_dirty = True
        self.recorder.step(frame)
        self.advance(LINE_COST_MS)

    # --- Physics -----------------------------------------------------------------

    def _tick(self):
        dt = DT_MS / 1000
        for drivebase in self.drivebases:
            drivebase.update(dt)
        for motor in self.motors.values():
            motor.step(dt)
        self._move_robot()
        for motor in self.motors.values():
            motor.end_tick(dt)
        self.phys_t += DT_MS
        self.ticks += 1
        if self.ticks % RECORD_EVERY == 0:
            self.recorder.frame()

    def _wheel_travel(self, port):
        motor = self.motors[port]
        if motor.last_delta == 0:
            return 0.0
        turns = motor.last_delta / 360 * (-1 if motor.mirrored else 1)
        travel = turns * math.pi * self.robot.wheel_diameter * self.wheel_scale[port]
        if self.realism.slip:
            travel *= 1 - abs(self.rng.gauss(0, self.realism.slip))
        return travel

    def _move_robot(self):
        left, right = self.robot.left_port, self.robot.right_port
        if left is None or right is None:
            return
        dl, dr = self._wheel_travel(left), self._wheel_travel(right)
        self.speed = self.turn_rate = 0.0
        if dl == 0 and dr == 0:
            return
        ds = (dl + dr) / 2
        dh = math.degrees((dl - dr) / self.robot.axle_track)
        mid = math.radians(self.heading + dh / 2)
        nx = self.x + ds * math.cos(mid)
        ny = self.y - ds * math.sin(mid)
        nh = self.heading + dh
        hit = self.world.collision(self.robot.outline(nx, ny, nh))
        if hit:
            self.motors[left].block()
            self.motors[right].block()
            if self.in_contact != hit:
                self.event("collision", what=hit)
            self.in_contact = hit
            return
        self.in_contact = None
        self.x, self.y, self.heading = nx, ny, nh
        self.speed = ds / (DT_MS / 1000)
        self.turn_rate = dh / (DT_MS / 1000)

    # --- Sensors -----------------------------------------------------------------

    def _noise(self, amount=1.0):
        if not self.realism.sensor_noise:
            return 0.0
        return self.rng.gauss(0, self.realism.sensor_noise * amount)

    def sensor_point(self, port):
        forward, left = self.robot.ports[port].position
        return to_world(self.x, self.y, self.heading, forward, left)

    def _cached(self, key, compute):
        # Sensors update once per physics tick, like real ones.
        entry = self._sensor_cache.get(key)
        if entry is not None and entry[0] == self.ticks:
            return entry[1]
        value = compute()
        self._sensor_cache[key] = (self.ticks, value)
        return value

    def reflection(self, port):
        def compute():
            px, py = self.sensor_point(port)
            value = self.world.reflection(px, py) + self._noise()
            return int(round(max(0.0, min(100.0, value))))
        return self._cached(("reflection", port), compute)

    def color_name(self, port):
        def compute():
            px, py = self.sensor_point(port)
            return self.world.color_at(px, py)
        return self._cached(("color", port), compute)

    def distance(self, port):
        def compute():
            px, py = self.sensor_point(port)
            d = self.world.ray_distance(px, py, self.heading)
            if d > ULTRASONIC_MAX:
                return ULTRASONIC_MAX
            d += self._noise(2.0)
            return int(round(max(ULTRASONIC_MIN, min(ULTRASONIC_MAX, d))))
        return self._cached(("distance", port), compute)

    def gyro_heading(self):
        """Heading since the program started, as the hub's gyro sees it."""
        drift = self.realism.gyro_drift * self.phys_t / 1000
        return self.heading - self.start_heading + drift

    def pressed_buttons(self):
        pressed = set()
        for press in self.button_presses:
            start = float(press.get("at", 0))
            if start <= self.now < start + float(press.get("duration", 200)):
                pressed.add(getattr(Button, press.get("button", "CENTER")))
        return pressed

    # --- Devices -----------------------------------------------------------------

    def claim(self, port, kind):
        """Check that a device of this kind is plugged into the port."""
        from pybricks.parameters import Port
        if not isinstance(port, Port):
            raise DeviceError.bad_port(port)
        spec = self.robot.ports.get(port.name)
        if spec is None or spec.device != kind:
            raise DeviceError(port.name, kind, spec.device if spec else None)
        return spec

    # --- Recording -----------------------------------------------------------------

    def event(self, kind, **data):
        self.recorder.event(kind, data)

    def write_output(self, text):
        self.recorder.write(text)

    def finish(self):
        self.recorder.flush_output()
        self.recorder.frame(final=True)
        if self.module_frame is not None:
            # Show the variables as the program left them.
            self.recorder.final_vars(self.module_frame)
        self.current_frame = self.module_frame = None


class Recorder:
    MAX_STEPS = 5000
    MAX_VAR_CHANGES = 20000
    MAX_PRINTS = 1000
    MAX_EVENTS = 1000

    def __init__(self, sim):
        self.sim = sim
        robot = sim.robot
        self.frames = {"t": [], "x": [], "y": [], "heading": [], "line": []}
        self.color_ports = robot.sensor_ports("color_sensor")
        self.distance_ports = robot.sensor_ports("ultrasonic_sensor")
        self.sensors = {"gyro": []}
        for port in self.color_ports:
            self.sensors[f"{port}.reflection"] = []
            self.sensors[f"{port}.color"] = []
        for port in self.distance_ports:
            self.sensors[f"{port}.distance"] = []
        self.arm_ports = [p for p, m in sim.motors.items() if m.role not in ("left_wheel", "right_wheel")]
        self.motor_angles = {port: [] for port in self.arm_ports}
        self.steps = []
        self.steps_truncated = False
        self.var_changes = []
        self._last_vars = None
        self.prints = []
        self.prints_truncated = False
        self._partial = ""
        self._partial_line = 0
        self.events = []

    def frame(self, final=False):
        sim = self.sim
        t = sim.now if final else sim.phys_t
        f = self.frames
        if final and f["t"] and f["t"][-1] >= t:
            return
        f["t"].append(round(t, 1))
        f["x"].append(round(sim.x, 1))
        f["y"].append(round(sim.y, 1))
        f["heading"].append(round(sim.heading, 2))
        f["line"].append(sim.current_line)
        self.sensors["gyro"].append(round(sim.gyro_heading() - sim.imu_offset, 1))
        for port in self.color_ports:
            self.sensors[f"{port}.reflection"].append(sim.reflection(port))
            self.sensors[f"{port}.color"].append(sim.color_name(port))
        for port in self.distance_ports:
            self.sensors[f"{port}.distance"].append(sim.distance(port))
        for port in self.arm_ports:
            self.motor_angles[port].append(round(sim.motors[port].angle, 1))
        if sim.vars_dirty and sim.current_frame is not None:
            self._record_vars(sim.current_frame, t)

    def step(self, frame):
        if len(self.steps) >= self.MAX_STEPS:
            self.steps_truncated = True
            return
        t = round(self.sim.now, 2)
        self.steps.append([t, frame.f_lineno])
        self._record_vars(frame, t)

    def final_vars(self, frame):
        self._record_vars(frame, round(self.sim.now, 2))

    def _record_vars(self, frame, t):
        self.sim.vars_dirty = False
        if len(self.var_changes) >= self.MAX_VAR_CHANGES:
            return
        values = snapshot(frame)
        if values != self._last_vars:
            self._last_vars = values
            self.var_changes.append({"t": t, "vars": values})

    def event(self, kind, data):
        if len(self.events) >= self.MAX_EVENTS:
            return
        entry = {"t": round(self.sim.now, 1), "type": kind, "line": self.sim.current_line}
        entry.update(data)
        self.events.append(entry)

    def write(self, text):
        if not self._partial:
            self._partial_line = self.sim.current_line
        self._partial += text
        while "\n" in self._partial:
            line, self._partial = self._partial.split("\n", 1)
            self._add_print(line)
            self._partial_line = self.sim.current_line

    def flush_output(self):
        if self._partial:
            self._add_print(self._partial)
            self._partial = ""

    def _add_print(self, text):
        if len(self.prints) >= self.MAX_PRINTS:
            self.prints_truncated = True
            return
        self.prints.append({"t": round(self.sim.now, 1), "line": self._partial_line, "text": text[:500]})

    def to_dict(self):
        return {
            "frames": self.frames,
            "sensors": self.sensors,
            "motors": self.motor_angles,
            "steps": self.steps,
            "steps_truncated": self.steps_truncated,
            "vars": self.var_changes,
            "prints": self.prints,
            "prints_truncated": self.prints_truncated,
            "events": self.events,
        }
