"""Simulated ``pybricks.robotics``: the DriveBase."""

from trainer_sim.context import current
from trainer_sim.drive import DriveController
from trainer_sim.errors import ArgumentError, ArgumentValueError

from ._args import flag, number, positive, stop
from .parameters import Stop
from .pupdevices import Motor


class DriveBase:
    """Two wheel motors working together to drive and turn."""

    def __init__(self, left_motor, right_motor, wheel_diameter, axle_track):
        sim = current()
        for name, motor in (("left_motor", left_motor), ("right_motor", right_motor)):
            if not isinstance(motor, Motor):
                raise ArgumentError(
                    f"DriveBase() expected a Motor for '{name}', got {motor!r}",
                    f"`DriveBase()` needs two Motor objects first. `{name}` is `{motor!r}`, "
                    "not a Motor. Create it with something like `Motor(Port.A)`.",
                )
        if left_motor.sim_motor is right_motor.sim_motor:
            raise ArgumentValueError(
                "DriveBase() needs two different motors",
                "`DriveBase()` got the same motor twice. The left and right motors must be on different ports.",
            )
        self._sim = sim
        self._ctl = DriveController(
            sim, left_motor, right_motor,
            positive(wheel_diameter, "wheel_diameter", "DriveBase"),
            positive(axle_track, "axle_track", "DriveBase"),
        )
        sim.drivebases.append(self._ctl)

    def _wait(self, wait, func):
        if flag(wait, "wait", func):
            self._sim.run_until(self._ctl.done)

    # --- Moving ------------------------------------------------------------------

    def straight(self, distance, then=Stop.HOLD, wait=True):
        self._ctl.straight(number(distance, "distance", "straight"), stop(then, "straight"))
        self._wait(wait, "straight")

    def turn(self, angle, then=Stop.HOLD, wait=True):
        self._ctl.turn(number(angle, "angle", "turn"), stop(then, "turn"))
        self._wait(wait, "turn")

    def curve(self, radius, angle, then=Stop.HOLD, wait=True):
        self._ctl.curve(number(radius, "radius", "curve"), number(angle, "angle", "curve"), stop(then, "curve"))
        self._wait(wait, "curve")

    def arc(self, radius, angle=None, distance=None, then=Stop.HOLD, wait=True):
        radius = number(radius, "radius", "arc")
        if angle is None and distance is not None:
            if radius == 0:
                raise ArgumentValueError("arc() radius can't be 0 with a distance", "`arc()` needs a radius that isn't 0.")
            import math
            angle = math.degrees(number(distance, "distance", "arc") / radius)
        if angle is None:
            raise ArgumentError("arc() needs an angle or a distance", "`arc()` needs `angle=` or `distance=`.")
        self.curve(radius, angle, then, wait)

    def drive(self, speed, turn_rate):
        self._ctl.drive(number(speed, "speed", "drive"), number(turn_rate, "turn_rate", "drive"))

    def stop(self):
        self._ctl.stop()

    def brake(self):
        self._ctl.stop()

    # --- Measuring ---------------------------------------------------------------

    def distance(self):
        return int(round(self._ctl.encoder_distance() - self._ctl.distance_offset))

    def angle(self):
        return int(round(self._ctl.heading() - self._ctl.angle_offset))

    def state(self):
        v, w = self._ctl.speeds()
        return (self.distance(), int(round(v)), self.angle(), int(round(w)))

    def reset(self, distance=0, angle=0):
        self._ctl.distance_offset = self._ctl.encoder_distance() - number(distance, "distance", "reset")
        self._ctl.angle_offset = self._ctl.heading() - number(angle, "angle", "reset")

    def done(self):
        return self._ctl.done()

    def stalled(self):
        return self._ctl.stalled()

    # --- Settings ----------------------------------------------------------------

    def settings(self, straight_speed=None, straight_acceleration=None, turn_rate=None, turn_acceleration=None):
        c = self._ctl
        if straight_speed is None and straight_acceleration is None and turn_rate is None and turn_acceleration is None:
            return (
                int(c.straight_speed), int(c.straight_acceleration),
                int(c.turn_rate), int(c.turn_acceleration),
            )
        if straight_speed is not None:
            c.straight_speed = positive(straight_speed, "straight_speed", "settings")
        if straight_acceleration is not None:
            c.straight_acceleration, c.straight_deceleration = _accel(straight_acceleration, "straight_acceleration")
        if turn_rate is not None:
            c.turn_rate = positive(turn_rate, "turn_rate", "settings")
        if turn_acceleration is not None:
            c.turn_acceleration, c.turn_deceleration = _accel(turn_acceleration, "turn_acceleration")

    def use_gyro(self, use_gyro):
        was = self._ctl.use_gyro
        self._ctl.use_gyro = flag(use_gyro, "use_gyro", "use_gyro")
        if was != self._ctl.use_gyro:
            # Keep angle() continuous when the heading source changes.
            self._ctl.angle_offset = 0.0


def _accel(value, name):
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return positive(value[0], name, "settings"), positive(value[1], name, "settings")
    v = positive(value, name, "settings")
    return v, v


class GyroDriveBase(DriveBase):
    """Older Pybricks name for a DriveBase that uses the gyro."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_gyro(True)
