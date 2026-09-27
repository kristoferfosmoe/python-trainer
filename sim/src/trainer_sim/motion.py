"""Motors and motion profiles.

Motors are ideal position-controlled servos: they go exactly where their
controller tells them to, limited only by top speed, mechanical limits and
collisions. Real-world imperfections (wheel slip, uneven wheels) are added
where wheel rotation turns into robot movement, not here, so encoder readings
stay perfect, just like on a real robot.
"""

import math

MAX_MOTOR_SPEED = 1000.0  # deg/s, roughly a SPIKE Prime motor
DEFAULT_MOTOR_ACCEL = 2000.0  # deg/s^2


class Trapezoid:
    """Speed up, cruise, slow down: covers `distance` and ends at rest.

    With keep_speed=True it skips the slowdown and ends at cruising speed
    (used for Stop.NONE).
    """

    def __init__(self, distance, speed, accel, decel=None, keep_speed=False):
        self.sign = -1.0 if distance < 0 else 1.0
        self.distance = abs(float(distance))
        v = abs(float(speed))
        a = abs(float(accel)) or 1.0
        d = math.inf if keep_speed else (abs(float(decel)) if decel else a)
        self.keep_speed = keep_speed
        if self.distance < 1e-9 or v < 1e-9:
            self.v_peak = 0.0
            self.ta = self.tc = self.td = self.duration = 0.0
            self.a = a
            self.d = d
            self.da = self.dc = 0.0
            return
        if math.isinf(d):
            v_peak = min(v, math.sqrt(2 * a * self.distance))
            td, dd = 0.0, 0.0
        else:
            v_peak = min(v, math.sqrt(2 * self.distance * a * d / (a + d)))
            td, dd = v_peak / d, v_peak * v_peak / (2 * d)
        ta, da = v_peak / a, v_peak * v_peak / (2 * a)
        dc = max(0.0, self.distance - da - dd)
        self.a, self.d, self.v_peak = a, d, v_peak
        self.ta, self.tc, self.td = ta, dc / v_peak, td
        self.da, self.dc = da, dc
        self.duration = ta + self.tc + td

    @property
    def end_speed(self):
        return self.sign * self.v_peak if self.keep_speed else 0.0

    def at(self, t):
        """(position, speed) at time t seconds."""
        if t <= 0:
            return 0.0, 0.0
        if t >= self.duration:
            return self.sign * self.distance, self.end_speed
        if t < self.ta:
            return self.sign * 0.5 * self.a * t * t, self.sign * self.a * t
        if t < self.ta + self.tc:
            return self.sign * (self.da + self.v_peak * (t - self.ta)), self.sign * self.v_peak
        tau = t - self.ta - self.tc
        s = self.da + self.dc + self.v_peak * tau - 0.5 * self.d * tau * tau
        return self.sign * s, self.sign * (self.v_peak - self.d * tau)


class TimedRun:
    """Run at `speed` for exactly `duration` seconds, ramping up and down."""

    def __init__(self, speed, duration, accel):
        self.duration = max(0.0, float(duration))
        v = float(speed)
        a = abs(float(accel)) or 1.0
        self.ta = min(abs(v) / a, self.duration / 2)
        self.v_peak = math.copysign(a * self.ta, v) if v else 0.0
        self.a = math.copysign(a, v) if v else 0.0
        self.end_speed = 0.0

    def at(self, t):
        T, ta = self.duration, self.ta
        if t <= 0:
            return 0.0, 0.0
        t = min(t, T)
        if t < ta:
            return 0.5 * self.a * t * t, self.a * t
        s_up = 0.5 * self.a * ta * ta
        if t <= T - ta:
            return s_up + self.v_peak * (t - ta), self.v_peak
        tau = t - (T - ta)
        s = s_up + self.v_peak * (T - 2 * ta) + self.v_peak * tau - 0.5 * self.a * tau * tau
        return s, self.v_peak - self.a * tau


class Scaled:
    """Another profile's shape, scaled (to move two things in sync)."""

    def __init__(self, profile, ratio):
        self.profile, self.ratio = profile, ratio
        self.duration = profile.duration

    @property
    def end_speed(self):
        return self.profile.end_speed * self.ratio

    def at(self, t):
        s, v = self.profile.at(t)
        return s * self.ratio, v * self.ratio


# --- Motor controllers --------------------------------------------------------
# Each controller returns the motor speed (deg/s, physical) for the next tick.
# `then` builds the controller to switch to when this one is done.

class Control:
    done = False
    then = None

    def speed(self, motor, dt):
        return 0.0


class Idle(Control):
    """Motor off (coast or brake)."""

    done = True


class Hold(Control):
    """Actively hold an angle."""

    done = True

    def __init__(self, angle):
        self.angle = angle

    def speed(self, motor, dt):
        return (self.angle - motor.angle) / dt


class RunSpeed(Control):
    """Run forever at a speed, ramping from the current speed."""

    def __init__(self, target, accel, current=0.0):
        self.target = float(target)
        self.accel = abs(float(accel))
        self.command = float(current)

    def speed(self, motor, dt):
        step = self.accel * dt
        if abs(self.target - self.command) <= step:
            self.command = self.target
        else:
            self.command += math.copysign(step, self.target - self.command)
        return self.command


class RunProfile(Control):
    """Follow a position profile exactly (run_angle, run_target, run_time)."""

    STALL_GIVE_UP = 0.5  # seconds

    def __init__(self, motor, profile, then):
        self.start = motor.angle
        self.profile = profile
        self.then = then
        self.t = 0.0

    def speed(self, motor, dt):
        self.t += dt
        s, _ = self.profile.at(self.t)
        if self.t >= self.profile.duration or motor.stall_time >= self.STALL_GIVE_UP:
            self.done = True
        return (self.start + s - motor.angle) / dt


class RunUntilStalled(Control):
    STALL_TIME = 0.05

    def __init__(self, target, accel, then):
        self.run = RunSpeed(target, accel)
        self.then = then

    def speed(self, motor, dt):
        if motor.stall_time >= self.STALL_TIME:
            self.done = True
            return 0.0
        return self.run.speed(motor, dt)


class Commanded(Control):
    """Speed set every tick by someone else (the drive base)."""

    def __init__(self, owner):
        self.owner = owner
        self.value = 0.0

    def speed(self, motor, dt):
        return self.value


class SimMotor:
    """The physical motor plugged into a port."""

    def __init__(self, port, spec):
        self.port = port
        self.role = spec.get("role")
        self.label = spec.get("label", f"Motor {port}")
        self.mirrored = bool(spec.get("mirrored", False))
        self.min_angle = spec.get("min_angle")
        self.max_angle = spec.get("max_angle")
        self.angle = 0.0
        self.speed = 0.0
        self.last_delta = 0.0
        self.control = Idle()
        self.stalled = False
        self.stall_time = 0.0

    def step(self, dt):
        command = self.control.speed(self, dt)
        command = max(-MAX_MOTOR_SPEED, min(MAX_MOTOR_SPEED, command))
        new = self.angle + command * dt
        stalled = False
        if self.min_angle is not None and new < self.min_angle:
            new, stalled = float(self.min_angle), command < 0
        elif self.max_angle is not None and new > self.max_angle:
            new, stalled = float(self.max_angle), command > 0
        self.last_delta = new - self.angle
        self.angle = new
        self.speed = self.last_delta / dt
        self.stalled = stalled

    def block(self):
        """Undo this tick's movement because the robot hit something."""
        self.angle -= self.last_delta
        self.last_delta = 0.0
        self.speed = 0.0
        self.stalled = True

    def end_tick(self, dt):
        self.stall_time = self.stall_time + dt if self.stalled else 0.0
        control = self.control
        if control.done and control.then is not None:
            self.control = control.then(self)
