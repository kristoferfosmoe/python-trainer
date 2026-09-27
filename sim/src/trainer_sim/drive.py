"""The drive base controller behind ``pybricks.robotics.DriveBase``.

It works only from what a real drive base knows: motor encoders, the wheel
diameter and axle track the student typed in, and (with use_gyro) the hub's
gyro. If the student's numbers are wrong, the robot drives wrong, just like
the real thing.
"""

import math

from pybricks.parameters import Stop

from .motion import Commanded, Hold, Idle, Scaled, Trapezoid

HEADING_GAIN = 8.0  # 1/s, gyro heading correction
STALL_GIVE_UP = 1.0  # seconds of being stuck before a move gives up
SETTLE_TIMEOUT = 1.0  # extra seconds a gyro move gets to reach its target


class _Maneuver:
    done = False
    stop = None

    def __init__(self, s0, h0, left0, right0):
        self.t = 0.0
        self.s0, self.h0 = s0, h0
        self.left0, self.right0 = left0, right0

    def reference(self, dt):
        """(distance, speed, heading, turn_rate) relative to the start, at self.t."""
        raise NotImplementedError


class _Profiled(_Maneuver):
    def __init__(self, start, distance_profile, heading_profile, stop):
        super().__init__(*start)
        self.dist = distance_profile
        self.head = heading_profile
        self.duration = max(distance_profile.duration, heading_profile.duration)
        self.stop = stop

    def reference(self, dt):
        s, v = self.dist.at(self.t)
        h, w = self.head.at(self.t)
        return s, v, h, w


class _Driving(_Maneuver):
    """drive(speed, turn_rate): keep going until told otherwise."""

    def __init__(self, start, speed, turn_rate, accel, turn_accel, v0=0.0, w0=0.0):
        super().__init__(*start)
        self.target_v, self.target_w = speed, turn_rate
        self.accel, self.turn_accel = accel, turn_accel
        self.v, self.w = v0, w0
        self.s, self.h = 0.0, 0.0

    @staticmethod
    def _ramp(value, target, step):
        if abs(target - value) <= step:
            return target
        return value + math.copysign(step, target - value)

    def reference(self, dt):
        self.v = self._ramp(self.v, self.target_v, self.accel * dt)
        self.w = self._ramp(self.w, self.target_w, self.turn_accel * dt)
        self.s += self.v * dt
        self.h += self.w * dt
        return self.s, self.v, self.h, self.w


class _Flat:
    duration = 0.0
    end_speed = 0.0

    def at(self, t):
        return 0.0, 0.0


class DriveController:
    def __init__(self, sim, left, right, wheel_diameter, axle_track):
        self.sim = sim
        self.left, self.right = left, right  # pybricks Motor objects (user units)
        self.wheel_diameter = wheel_diameter
        self.axle_track = axle_track
        self.circumference = math.pi * wheel_diameter
        self.use_gyro = False
        self.straight_speed = 200.0
        self.straight_acceleration = 700.0
        self.straight_deceleration = 700.0
        self.turn_rate = 180.0
        self.turn_acceleration = 720.0
        self.turn_deceleration = 720.0
        self.maneuver = None
        self._commands = None
        self.stall_time = 0.0
        self.distance_offset = 0.0
        self.angle_offset = 0.0

    # --- Measurements (what the robot "knows") ---------------------------------

    def encoder_distance(self):
        return (self.left.user_angle() + self.right.user_angle()) / 2 * self.circumference / 360

    def encoder_heading(self):
        diff = (self.left.user_angle() - self.right.user_angle()) * self.circumference / 360
        return math.degrees(diff / self.axle_track)

    def heading(self):
        return self.sim.gyro_heading() if self.use_gyro else self.encoder_heading()

    def speeds(self):
        v = (self.left.user_speed() + self.right.user_speed()) / 2 * self.circumference / 360
        w = (self.left.user_speed() - self.right.user_speed()) * self.circumference / 360
        return v, math.degrees(w / self.axle_track)

    # --- Starting moves ----------------------------------------------------------

    def _start(self):
        return (
            self.encoder_distance(),
            self.heading(),
            self.left.user_angle(),
            self.right.user_angle(),
        )

    def _take_motors(self):
        self._commands = (Commanded(self), Commanded(self))
        self.left.sim_motor.control = self._commands[0]
        self.right.sim_motor.control = self._commands[1]
        self.stall_time = 0.0

    def straight(self, distance, stop):
        profile = Trapezoid(
            distance, self.straight_speed, self.straight_acceleration,
            self.straight_deceleration, keep_speed=stop is Stop.NONE,
        )
        self.maneuver = _Profiled(self._start(), profile, _Flat(), stop)
        self._take_motors()

    def turn(self, angle, stop):
        profile = Trapezoid(
            angle, self.turn_rate, self.turn_acceleration,
            self.turn_deceleration, keep_speed=stop is Stop.NONE,
        )
        self.maneuver = _Profiled(self._start(), _Flat(), profile, stop)
        self._take_motors()

    def curve(self, radius, angle, stop):
        distance = abs(radius) * math.radians(abs(angle))
        distance = math.copysign(distance, radius) if radius else 0.0
        turn = math.copysign(abs(angle), angle if radius >= 0 else -angle)
        keep = stop is Stop.NONE
        dist_profile = Trapezoid(distance, self.straight_speed, self.straight_acceleration,
                                 self.straight_deceleration, keep_speed=keep)
        turn_profile = Trapezoid(turn, self.turn_rate, self.turn_acceleration,
                                 self.turn_deceleration, keep_speed=keep)
        if dist_profile.duration >= turn_profile.duration and distance:
            head = Scaled(dist_profile, turn / distance)
            dist = dist_profile
        elif turn:
            dist = Scaled(turn_profile, distance / turn)
            head = turn_profile
        else:
            dist, head = dist_profile, _Flat()
        self.maneuver = _Profiled(self._start(), dist, head, stop)
        self._take_motors()

    def drive(self, speed, turn_rate):
        v0 = w0 = 0.0
        if isinstance(self.maneuver, _Driving) and self._owns_motors():
            v0, w0 = self.maneuver.v, self.maneuver.w
        self.maneuver = _Driving(
            self._start(), float(speed), float(turn_rate),
            self.straight_acceleration, self.turn_acceleration, v0, w0,
        )
        self._take_motors()

    def stop(self):
        self.maneuver = None
        if self._owns_motors():
            self.left.sim_motor.control = Idle()
            self.right.sim_motor.control = Idle()
        self._commands = None

    def done(self):
        return self.maneuver is None or self.maneuver.done

    def stalled(self):
        return self.stall_time > 0

    def _owns_motors(self):
        return (
            self._commands is not None
            and self.left.sim_motor.control is self._commands[0]
            and self.right.sim_motor.control is self._commands[1]
        )

    # --- Every tick ----------------------------------------------------------------

    def update(self, dt):
        m = self.maneuver
        if m is not None and m.done:
            # The last step of a move happens on the tick it's marked done;
            # the stop (hold, coast, keep going) starts on the next one.
            self._finish(m)
            m = self.maneuver
        if m is None:
            return
        if not self._owns_motors():
            # The student took over a wheel motor directly; this move is cancelled.
            self.maneuver = None
            self._commands = None
            return

        m.t += dt
        s_ref, _, h_ref, w_ref = m.reference(dt)

        if self.use_gyro:
            h_now = self.sim.gyro_heading() - m.h0
            h_enc_now = self.encoder_heading() - self._enc_h0(m)
            h_target = h_enc_now + (w_ref + HEADING_GAIN * (h_ref - h_now)) * dt
        else:
            h_target = h_ref

        half = math.radians(h_target) * self.axle_track / 2
        left_target = m.left0 + (s_ref + half) / self.circumference * 360
        right_target = m.right0 + (s_ref - half) / self.circumference * 360
        self._set_user_speed(0, self.left, (left_target - self.left.user_angle()) / dt)
        self._set_user_speed(1, self.right, (right_target - self.right.user_angle()) / dt)

        stuck = self.left.sim_motor.stall_time > 0 or self.right.sim_motor.stall_time > 0
        self.stall_time = self.stall_time + dt if stuck else 0.0

        if isinstance(m, _Profiled):
            finished = m.t >= m.duration
            if finished and self.use_gyro:
                on_target = abs(h_ref - (self.sim.gyro_heading() - m.h0)) < 1.0
                finished = on_target or m.t >= m.duration + SETTLE_TIMEOUT
            if self.stall_time >= STALL_GIVE_UP:
                self.sim.event("stalled", what="drive base")
                finished = True
            if finished:
                m.done = True

    def _enc_h0(self, m):
        diff = (m.left0 - m.right0) * self.circumference / 360
        return math.degrees(diff / self.axle_track)

    def _set_user_speed(self, index, motor, user_speed):
        self._commands[index].value = motor.user_to_physical_speed(user_speed)

    def _finish(self, m):
        stop = m.stop
        if stop is Stop.NONE:
            v = m.dist.end_speed
            w = m.head.end_speed
            self.maneuver = _Driving(
                self._start(), v, w, self.straight_acceleration, self.turn_acceleration, v, w,
            )
            return
        self.maneuver = None
        self._commands = None
        if stop is Stop.HOLD:
            self.left.sim_motor.control = Hold(self.left.sim_motor.angle)
            self.right.sim_motor.control = Hold(self.right.sim_motor.angle)
        else:
            self.left.sim_motor.control = Idle()
            self.right.sim_motor.control = Idle()

