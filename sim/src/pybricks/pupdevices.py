"""Simulated ``pybricks.pupdevices``: motors and sensors."""

from trainer_sim.context import current
from trainer_sim.errors import ArgumentError, NotInSimulator
from trainer_sim.motion import (
    DEFAULT_MOTOR_ACCEL, MAX_MOTOR_SPEED, Hold, RunProfile, RunSpeed,
    RunUntilStalled, TimedRun, Trapezoid, brake, coast,
)

from ._args import flag, number, stop
from .parameters import Color, Direction, Stop

_COLOR_CONSTANTS = {
    name.lower(): getattr(Color, name)
    for name in ("BLACK", "GRAY", "WHITE", "RED", "ORANGE", "BROWN", "YELLOW",
                 "GREEN", "CYAN", "BLUE", "VIOLET", "MAGENTA")
}


def _gear_ratio(gears):
    if gears is None:
        return 1.0
    if not isinstance(gears, (list, tuple)) or not gears:
        raise ArgumentError(
            "gears must be a list like [12, 36]",
            "`gears=` needs a list of teeth counts, like `gears=[12, 36]`.",
        )
    trains = gears if isinstance(gears[0], (list, tuple)) else [gears]
    ratio = 1.0
    for train in trains:
        if len(train) < 2:
            raise ArgumentError("each gear train needs at least two gears", "Each gear list needs at least two gears.")
        ratio *= number(train[-1], "gears", "Motor") / number(train[0], "gears", "Motor")
    return ratio


def _then(value):
    if value is Stop.HOLD:
        return lambda m: Hold(m.angle)
    if value is Stop.NONE:
        return lambda m: RunSpeed(m.speed, DEFAULT_MOTOR_ACCEL, m.speed)
    if value is Stop.BRAKE:
        return brake
    return coast


class _MotorControl:
    """Stand-in for ``motor.control``: only ``limits()`` does anything."""

    def __init__(self, motor):
        self._motor = motor

    def limits(self, speed=None, acceleration=None, torque=None):
        m = self._motor
        if speed is None and acceleration is None and torque is None:
            return (int(m._max_speed), int(m._accel), 200)
        if speed is not None:
            m._max_speed = min(MAX_MOTOR_SPEED, abs(number(speed, "speed", "limits")))
        if acceleration is not None:
            m._accel = abs(number(acceleration, "acceleration", "limits"))

    def pid(self, *args, **kwargs):
        return (0, 0, 0, 0, 0)

    def target_tolerances(self, *args, **kwargs):
        return (10, 10)

    def stall_tolerances(self, *args, **kwargs):
        return (20, 200)


class Motor:
    """A motor with a rotation sensor."""

    def __init__(self, port, positive_direction=Direction.CLOCKWISE, gears=None,
                 reset_angle=True, profile=None):
        self._sim = current()
        self._sim.claim(port, "motor")
        self.sim_motor = self._sim.motors[port.name]
        self._port = port
        if not isinstance(positive_direction, Direction):
            raise ArgumentError(
                f"expected a Direction, got {positive_direction!r}",
                "The second value for `Motor()` must be `Direction.CLOCKWISE` or `Direction.COUNTERCLOCKWISE`.",
            )
        self._sign = -1.0 if positive_direction is Direction.COUNTERCLOCKWISE else 1.0
        self._ratio = _gear_ratio(gears)
        self._max_speed = MAX_MOTOR_SPEED / self._ratio
        self._accel = DEFAULT_MOTOR_ACCEL / self._ratio
        self._offset = 0.0
        self.control = _MotorControl(self)
        if reset_angle:
            raw = self.user_angle()
            self._offset = raw - (((raw + 180) % 360) - 180)

    def __repr__(self):
        return f"Motor({self._port!r})"

    # Conversions between the student's units and the physical motor.
    def user_angle(self):
        return self.sim_motor.angle * self._sign / self._ratio

    def user_speed(self):
        return self.sim_motor.speed * self._sign / self._ratio

    def user_to_physical_speed(self, speed):
        return speed * self._sign * self._ratio

    def _physical(self, user_degrees):
        return user_degrees * self._sign * self._ratio

    def _clamp(self, speed):
        return max(-self._max_speed, min(self._max_speed, speed))

    def _start(self, control, wait):
        self.sim_motor.control = control
        if wait:
            self._sim.run_until(lambda: control.done)

    # --- Measuring ---------------------------------------------------------------

    def angle(self):
        return int(round(self.user_angle() - self._offset))

    def speed(self, window=None):
        return int(round(self.user_speed()))

    def load(self):
        return 0

    def reset_angle(self, angle=None):
        if angle is None:
            raw = self.user_angle()
            self._offset = raw - (((raw + 180) % 360) - 180)
        else:
            self._offset = self.user_angle() - number(angle, "angle", "reset_angle")

    def done(self):
        return self.sim_motor.control.done

    def stalled(self):
        return self.sim_motor.stall_time > 0

    # --- Stopping ----------------------------------------------------------------

    def stop(self):
        self.sim_motor.control = coast(self.sim_motor)

    def brake(self):
        self.sim_motor.control = brake(self.sim_motor)

    def hold(self):
        self.sim_motor.control = Hold(self.sim_motor.angle)

    # --- Running -----------------------------------------------------------------

    def run(self, speed):
        speed = self._clamp(number(speed, "speed", "run"))
        self.sim_motor.control = RunSpeed(
            self._physical(speed), self._physical(self._accel), self.sim_motor.speed,
        )

    def dc(self, duty):
        duty = max(-100.0, min(100.0, number(duty, "duty", "dc")))
        self.run(duty / 100 * self._max_speed)

    def run_time(self, speed, time, then=Stop.HOLD, wait=True):
        speed = self._clamp(number(speed, "speed", "run_time"))
        time = number(time, "time", "run_time")
        profile = TimedRun(self._physical(speed), max(0.0, time) / 1000, abs(self._physical(self._accel)))
        control = RunProfile(self.sim_motor, profile, _then(stop(then, "run_time")))
        self._start(control, flag(wait, "wait", "run_time"))

    def run_angle(self, speed, rotation_angle, then=Stop.HOLD, wait=True):
        speed = self._clamp(number(speed, "speed", "run_angle"))
        angle = number(rotation_angle, "rotation_angle", "run_angle")
        direction = -1.0 if (speed < 0) != (angle < 0) else 1.0
        self._run_by(direction * abs(angle), abs(speed), stop(then, "run_angle"), flag(wait, "wait", "run_angle"))

    def run_target(self, speed, target_angle, then=Stop.HOLD, wait=True):
        speed = self._clamp(number(speed, "speed", "run_target"))
        target = number(target_angle, "target_angle", "run_target")
        delta = target - (self.user_angle() - self._offset)
        self._run_by(delta, abs(speed), stop(then, "run_target"), flag(wait, "wait", "run_target"))

    def _run_by(self, user_delta, speed, then, wait):
        profile = Trapezoid(
            self._physical(user_delta), abs(self._physical(speed)), abs(self._physical(self._accel)),
            keep_speed=then is Stop.NONE,
        )
        self._start(RunProfile(self.sim_motor, profile, _then(then)), wait)

    def run_until_stalled(self, speed, then=Stop.COAST, duty_limit=None):
        speed = self._clamp(number(speed, "speed", "run_until_stalled"))
        control = RunUntilStalled(self._physical(speed), abs(self._physical(self._accel)),
                                  _then(stop(then, "run_until_stalled")))
        self._start(control, True)
        return self.angle()

    def track_target(self, target_angle):
        target = number(target_angle, "target_angle", "track_target")
        self.sim_motor.control = Hold(self._physical(target + self._offset))


class DCMotor:
    def __init__(self, *args, **kwargs):
        raise NotInSimulator("DCMotor")


class _SensorLights:
    def on(self, *brightness):
        pass

    def off(self):
        pass


class ColorSensor:
    """Looks down at the mat: color() and reflection()."""

    def __init__(self, port):
        self._sim = current()
        self._sim.claim(port, "color_sensor")
        self._port = port
        self._detectable = None
        self.lights = _SensorLights()

    def __repr__(self):
        return f"ColorSensor({self._port!r})"

    def _color(self):
        return _COLOR_CONSTANTS[self._sim.color_name(self._port.name)]

    def color(self, surface=True):
        seen = self._color()
        if self._detectable is not None and seen not in self._detectable:
            # Pick the closest color the student asked for, by hue and brightness.
            def distance(c):
                hue = min(abs(c.h - seen.h), 360 - abs(c.h - seen.h)) if c.s and seen.s else 0
                return hue + abs(c.s - seen.s) + abs(c.v - seen.v)
            return min(self._detectable, key=distance)
        return seen

    def reflection(self):
        return self._sim.reflection(self._port.name)

    def ambient(self):
        return 20

    def hsv(self, surface=True):
        seen = self._color()
        return Color(seen.h, seen.s, self.reflection())

    def detectable_colors(self, colors=None):
        if colors is None:
            return tuple(self._detectable or _COLOR_CONSTANTS.values())
        self._detectable = [c for c in colors if isinstance(c, Color)]


class UltrasonicSensor:
    """Measures the distance to what's in front of the robot (mm)."""

    def __init__(self, port):
        self._sim = current()
        self._sim.claim(port, "ultrasonic_sensor")
        self._port = port
        self.lights = _SensorLights()

    def __repr__(self):
        return f"UltrasonicSensor({self._port!r})"

    def distance(self):
        return self._sim.distance(self._port.name)

    def presence(self):
        return False


class ForceSensor:
    def __init__(self, port):
        self._sim = current()
        self._sim.claim(port, "force_sensor")
        self._port = port

    def force(self):
        return 0.0

    def distance(self):
        return 0.0

    def pressed(self, force=3):
        return False

    def touched(self):
        return False


class ColorDistanceSensor:
    def __init__(self, *args, **kwargs):
        raise NotInSimulator("ColorDistanceSensor")
