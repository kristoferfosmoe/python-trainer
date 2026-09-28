"""Attachments: shapes bolted onto the arm motors (ports E and F).

An attachment's angle is its motor's angle (divided by its gear ratio), so
encoders, run_target, reset_angle and stall detection work as usual. There
are three kinds:

- lift:  turns around a sideways axle, so it goes up and down. 0° is level,
         pointing ahead; positive is up. Seen from above, it gets shorter as
         it rises. It can have a hook near its tip.
- sweep: turns around an upright axle, so it swings across the mat at a
         fixed height. 0° points along `direction`; positive is clockwise.
- slide: moves in and out (like a rack and pinion) by `travel` mm per degree.
"""

import math

from ..shapes import ShapeError, to_world
from . import geometry

KINDS = ("lift", "sweep", "slide")
LIFT_SEGMENTS = 4
PORTS = ("E", "F")


def _num(spec, key, default=None):
    value = spec.get(key, default)
    if value is None:
        raise ShapeError(f"attachment {spec.get('id', '?')} is missing '{key}'")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ShapeError(f"attachment {spec.get('id', '?')}: '{key}' must be a number")
    return float(value)


class AttachmentSpec:
    def __init__(self, spec):
        if not isinstance(spec, dict) or not spec.get("id"):
            raise ShapeError("an attachment needs an 'id'")
        self.id = spec["id"]
        self.name = spec.get("name", self.id)
        self.kind = spec.get("kind")
        if self.kind not in KINDS:
            raise ShapeError(f"attachment {self.id}: kind must be one of {', '.join(KINDS)}")
        self.port = spec.get("port", "E")
        if self.port not in PORTS:
            raise ShapeError(f"attachment {self.id}: port must be E or F")
        mount = spec.get("mount", [110, 0])
        self.mount = (float(mount[0]), float(mount[1]))
        self.direction = _num(spec, "direction", 0)
        self.length = _num(spec, "length")
        self.width = _num(spec, "width", 30)
        self.rest_angle = _num(spec, "rest_angle", 0)
        self.min_angle = _num(spec, "min_angle", -90)
        self.max_angle = _num(spec, "max_angle", 90)
        if not self.min_angle <= self.rest_angle <= self.max_angle:
            raise ShapeError(f"attachment {self.id}: rest_angle must be between min_angle and max_angle")
        self.gears = _num(spec, "gears", 1)
        if self.gears <= 0:
            raise ShapeError(f"attachment {self.id}: gears must be positive")
        if self.kind == "lift":
            self.mount_z = _num(spec, "mount_z", 60)
            self.thickness = _num(spec, "thickness", 16)
            hook = spec.get("hook")
            self.hook_at = None
            if hook:
                self.hook_at = float(hook.get("at", self.length)) if isinstance(hook, dict) else self.length
        else:
            z = spec.get("z", [20, 50])
            self.z = (float(z[0]), float(z[1]))
            if self.z[0] >= self.z[1]:
                raise ShapeError(f"attachment {self.id}: z must be [low, high]")
            self.hook_at = None
        self.travel = _num(spec, "travel", 0.5) if self.kind == "slide" else 0.0
        # What the motor reads when a program starts with this attachment on.
        # Normally its resting angle; a challenge can put an attachment on at
        # another angle without the motor knowing (see match.resolve).
        self.reads = _num(spec, "reads", self.rest_angle)
        self.raw = spec

    def to_dict(self):
        return self.raw


class Mounted:
    """An attachment on a motor, for one run (until the teammate swaps it)."""

    def __init__(self, spec, motor, before_start=False):
        self.spec = spec
        self.port = spec.port
        self.motor = motor
        if before_start:
            # Motors know their position when a program starts (SPIKE motors
            # have absolute encoders), so the motor reads the resting angle.
            motor.angle = spec.reads * spec.gears
        # Swapped on during a match, the attachment goes on at its resting
        # angle wherever the encoder is; the encoder keeps counting.
        self.zero = motor.angle
        motor.min_angle = self.zero + (spec.min_angle - spec.rest_angle) * spec.gears
        motor.max_angle = self.zero + (spec.max_angle - spec.rest_angle) * spec.gears
        self.blocked_by = None  # what it's pressing against, for the "blocked" event
        self._cache_key = self._cache = None

    def angle(self, motor_angle=None):
        motor_angle = self.motor.angle if motor_angle is None else motor_angle
        return self.spec.rest_angle + (motor_angle - self.zero) / self.spec.gears

    def _point(self, pose, along, angle):
        """World point `along` mm out from the mount, in the attachment's direction on the mat."""
        s = self.spec
        heading = s.direction + (angle if s.kind == "sweep" else 0.0)
        r = math.radians(heading)
        forward = s.mount[0] + along * math.cos(r)
        left = s.mount[1] - along * math.sin(r)
        return to_world(pose[0], pose[1], pose[2], forward, left)

    def segments(self, pose, motor_angle=None):
        """[(polygon, (z_low, z_high))] for the attachment at `pose` (x, y, heading).
        `motor_angle` gives its shape at another motor angle (default: now)."""
        key = (pose, self.motor.angle if motor_angle is None else motor_angle)
        if key == self._cache_key:
            return self._cache
        s = self.spec
        angle = self.angle(key[1])
        if s.kind == "lift":
            a = math.radians(angle)
            reach, rise = math.cos(a), math.sin(a)
            n = LIFT_SEGMENTS
            points = [self._point(pose, s.length * i / n * reach, angle) for i in range(n + 1)]
            parts = []
            for i in range(n):
                z0 = s.mount_z + s.length * i / n * rise
                z1 = s.mount_z + s.length * (i + 1) / n * rise
                low, high = min(z0, z1) - s.thickness / 2, max(z0, z1) + s.thickness / 2
                parts.append((geometry.bar(*points[i], *points[i + 1], s.width), (max(0.0, low), high)))
        else:
            length = s.length + (angle * s.travel if s.kind == "slide" else 0.0)
            p0 = self._point(pose, 0.0, angle)
            p1 = self._point(pose, max(1.0, length), angle)
            parts = [(geometry.bar(*p0, *p1, s.width), s.z)]
        self._cache_key, self._cache = key, parts
        return parts

    def hook(self, pose):
        """(x, y, z) of the hook, or None if it has no hook."""
        s = self.spec
        if s.hook_at is None:
            return None
        angle = self.angle()
        a = math.radians(angle)
        x, y = self._point(pose, s.hook_at * math.cos(a), angle)
        return x, y, s.mount_z + s.hook_at * math.sin(a)

    def reach(self):
        """Farthest any part can be from the robot's center (for quick distance checks)."""
        s = self.spec
        extra = s.travel * max(abs(s.min_angle), abs(s.max_angle))
        return math.hypot(*s.mount) + s.length + extra + s.width
