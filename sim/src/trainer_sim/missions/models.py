"""Mission models: the things on the field that move or change.

Each type has a state, parts (the shapes something can bump into, each
with a height range), and a rule for what happens when the robot or an
attachment pushes one of its parts. `push()` returns True if the model gave
way and False if it's solid (then whatever pushed it is blocked).

| Type   | States                         | Moved by                                      |
|--------|--------------------------------|-----------------------------------------------|
| block  | on_field                       | pushing (slides away; stops at walls)         |
| lever  | two names, e.g. up / down      | pushing its bar one way; latches past its     |
|        |                                | tipping point, or springs back                |
| button | not_pressed / pressed          | pressing its face; counts presses             |
| loop   | on_post / carried / dropped    | a hook lifting it off its post                |
| flag   | down / raised                  | a hook lifting its handle                     |
| gate   | closed / open                  | a link from another model                     |

Any model can start `hidden` and be shown by a link. Links (`on:`) run
actions when a model reaches a state: open, close or show another model.
"""

import math

from ..shapes import ShapeError
from . import geometry

LINK_ACTIONS = ("open", "close", "show")
REMOVED = "removed"


def _num(spec, key, default=None):
    value = spec.get(key, default)
    if value is None:
        raise ShapeError(f"model {spec.get('id', '?')} is missing '{key}'")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ShapeError(f"model {spec.get('id', '?')}: '{key}' must be a number")
    return float(value)


def _pair(spec, key, default=None):
    value = spec.get(key, default)
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ShapeError(f"model {spec.get('id', '?')}: '{key}' must be [a, b]")
    return float(value[0]), float(value[1])


class Part:
    """A shape of a model that things can bump into."""

    __slots__ = ("model", "poly", "z", "bounds", "solid")

    def __init__(self, model, poly, z, solid=True):
        self.model = model
        self.poly = poly
        self.z = z
        self.bounds = geometry.bounds(poly)
        self.solid = solid  # False: push() decides (blocks, levers, buttons)


class Model:
    type = "model"
    states = ()

    def __init__(self, spec):
        self.spec = spec
        self.id = spec.get("id")
        if not self.id or not isinstance(self.id, str):
            raise ShapeError(f"every model needs an 'id': {spec}")
        self.label = spec.get("label", self.id)
        self.hidden = bool(spec.get("hidden", False))
        self.state = self.states[0] if self.states else ""
        self.links = self._links(spec.get("on") or {})
        self._parts = None

    def _links(self, on):
        if not isinstance(on, dict):
            raise ShapeError(f"model {self.id}: 'on' must map a state to actions")
        links = {}
        for state, actions in on.items():
            actions = actions if isinstance(actions, list) else [actions]
            parsed = []
            for action in actions:
                if not isinstance(action, dict) or len(action) != 1:
                    raise ShapeError(f"model {self.id}: each action is like {{open: gate-id}}")
                (verb, target), = action.items()
                if verb not in LINK_ACTIONS:
                    raise ShapeError(f"model {self.id}: unknown action '{verb}'. Use one of: {', '.join(LINK_ACTIONS)}")
                parsed.append((verb, target))
            links[state] = parsed
        return links

    # --- What the field asks every model ---------------------------------------

    def parts(self):
        if self.hidden or self.state == REMOVED:
            return []
        if self._parts is None:
            self._parts = self.make_parts()
        return self._parts

    def moved(self):
        self._parts = None

    def make_parts(self):
        return []

    def push(self, part, pusher, field):
        return not part.solid

    def tick(self, field, dt):
        pass

    def position(self):
        """Where the model is, for zone checks (None when it's not on the field)."""
        if self.hidden or self.state == REMOVED:
            return None
        return self.x, self.y

    def reach(self):
        """Radius around position() that holds every part."""
        return 100.0

    def snapshot(self):
        return {"state": self.state, "hidden": self.hidden}

    def all_states(self):
        return tuple(self.states) + (REMOVED,)


class Block(Model):
    """Something loose that slides when pushed: a crate, a box of cargo."""

    type = "block"
    states = ("on_field",)

    def __init__(self, spec):
        super().__init__(spec)
        self.x, self.y = _pair(spec, "at")
        self.round = "r" in spec
        if self.round:
            self.r = _num(spec, "r")
            self.w = self.h = 2 * self.r
        else:
            self.w, self.h = _pair(spec, "size")
        if self.w <= 0 or self.h <= 0:
            raise ShapeError(f"model {self.id}: size must be positive")
        self.angle = _num(spec, "angle", 0)
        self.z = _pair(spec, "z", [0, 60])

    def shape(self, x, y):
        if self.round:
            return geometry.circle(x, y, self.r)
        return geometry.rect(x, y, self.w, self.h, self.angle)

    def make_parts(self):
        return [Part(self, self.shape(self.x, self.y), self.z, solid=False)]

    def push(self, part, pusher, field):
        away = geometry.push_out(part.poly, pusher)
        if away is None:
            return True
        dx, dy = away
        length = math.hypot(dx, dy)
        dx, dy = dx * (length + 0.2) / length, dy * (length + 0.2) / length
        moved = geometry.move(part.poly, dx, dy)
        if field.shape_is_blocked(moved, self.z, ignore=self):
            return False
        self.x += dx
        self.y += dy
        self.moved()
        return True

    def reach(self):
        return math.hypot(self.w, self.h) / 2

    def snapshot(self):
        return {"state": self.state, "hidden": self.hidden, "x": round(self.x, 1), "y": round(self.y, 1)}


class Lever(Model):
    """A bar that turns on a hinge (seen from above) when pushed toward its end angle."""

    type = "lever"
    DONE_WITHIN = 3.0
    MAX_STEP = 30  # degrees one push can turn it in a tick
    SPRING_SPEED = 120.0  # deg/s

    def __init__(self, spec):
        names = spec.get("states", ["start", "done"])
        if not isinstance(names, list) or len(names) != 2 or not all(isinstance(n, str) for n in names):
            raise ShapeError(f"model {spec.get('id', '?')}: lever 'states' must be two names, like [up, down]")
        self.states = tuple(names)
        super().__init__(spec)
        self.x, self.y = _pair(spec, "hinge")
        self.length = _num(spec, "length")
        self.width = _num(spec, "width", 20)
        self.start = _num(spec, "angle", 0)
        self.end = _num(spec, "to")
        if self.start == self.end:
            raise ShapeError(f"model {self.id}: a lever's 'to' must differ from its 'angle'")
        self.angle = self.start
        self.z = _pair(spec, "z", [20, 70])
        self.latch = bool(spec.get("latch", True))
        self.spring = bool(spec.get("spring", False))
        # A latching lever pushed past its tipping point (this far along) falls the rest of the way.
        self.tip = _num(spec, "tip", 0.6)
        if not 0 < self.tip <= 1:
            raise ShapeError(f"model {self.id}: 'tip' must be between 0 and 1")
        self.pushed = False

    def bar(self, angle):
        r = math.radians(angle)
        tip = (self.x + self.length * math.cos(r), self.y - self.length * math.sin(r))
        return geometry.bar(self.x, self.y, *tip, self.width)

    def make_parts(self):
        post = Part(self, geometry.circle(self.x, self.y, 12), (0.0, self.z[1]))
        bar = Part(self, self.bar(self.angle), self.z, solid=False)
        return [post, bar]

    def _set_angle(self, angle):
        self.angle = angle
        self.moved()
        done = abs(self.angle - self.end) <= self.DONE_WITHIN
        self.state = self.states[1] if done else self.states[0]

    def push(self, part, pusher, field):
        if self.latch and self.state == self.states[1]:
            return False
        step = 1.0 if self.end > self.angle else -1.0
        angle = self.angle
        for _ in range(self.MAX_STEP):
            if angle == self.end:
                break
            angle = min(self.end, angle + step) if step > 0 else max(self.end, angle + step)
            if not geometry.overlap(self.bar(angle), pusher):
                self._set_angle(angle)
                self.pushed = True
                if self.latch and (angle - self.start) / (self.end - self.start) >= self.tip \
                        and not field.robot_touches(self.bar(self.end), self.z):
                    self._set_angle(self.end)
                return True
        return False

    def tick(self, field, dt):
        pushed, self.pushed = self.pushed, False
        if pushed or not self.spring or self.angle == self.start:
            return
        if self.latch and self.state == self.states[1]:
            return
        step = self.SPRING_SPEED * dt
        angle = self.start if abs(self.start - self.angle) <= step else self.angle + math.copysign(step, self.start - self.angle)
        if not field.robot_touches(self.bar(angle), self.z):
            self._set_angle(angle)

    def reach(self):
        return self.length + self.width

    def snapshot(self):
        return {"state": self.state, "hidden": self.hidden, "angle": round(self.angle, 1)}


class Button(Model):
    """Pressed when something pushes into its face; it gives a little, then it's solid."""

    type = "button"
    states = ("not_pressed", "pressed")

    def __init__(self, spec):
        super().__init__(spec)
        self.x, self.y = _pair(spec, "at")
        self.w, self.h = _pair(spec, "size", [40, 40])
        self.angle = _num(spec, "angle", 0)
        self.z = _pair(spec, "z", [0, 80])
        self.depth = _num(spec, "depth", 15)
        self.presses = 0
        self.down = False
        self._touched = False

    def make_parts(self):
        return [Part(self, geometry.rect(self.x, self.y, self.w, self.h, self.angle), self.z, solid=False)]

    def push(self, part, pusher, field):
        away = geometry.push_out(part.poly, pusher)
        if away is None:
            return True
        if math.hypot(*away) > self.depth:
            self._touched = True
            return False
        self._touched = True
        return True

    def tick(self, field, dt):
        touched, self._touched = self._touched, False
        # Something resting against it keeps it pressed (it isn't pushed again every tick).
        touched = touched or (not self.hidden and field.robot_touches(self.make_parts()[0].poly, self.z))
        if touched and not self.down:
            self.presses += 1
            self.state = "pressed"
            field.event("pressed", model=self.id, presses=self.presses)
        self.down = touched

    def reach(self):
        return math.hypot(self.w, self.h) / 2

    def snapshot(self):
        return {"state": self.state, "hidden": self.hidden, "presses": self.presses, "down": self.down}


class Loop(Model):
    """A ring on a short post. A hook that goes into it and lifts carries it; lowering the hook drops it."""

    type = "loop"
    states = ("on_post", "carried", "dropped")

    def __init__(self, spec):
        super().__init__(spec)
        self.x, self.y = _pair(spec, "at")
        self.r = _num(spec, "r", 25)
        self.z_ring = _pair(spec, "z", [50, 90])
        self.lift_z = _num(spec, "lift_z", self.z_ring[1] + 15)
        self.drop_z = _num(spec, "drop_z", 35)
        self.post_z = _num(spec, "post_z", 30)
        self.height = self.z_ring[0]
        self.carrier = None

    def make_parts(self):
        if self.state == "on_post" and self.post_z > 0:
            return [Part(self, geometry.circle(self.x, self.y, 10), (0.0, self.post_z))]
        return []

    def hook_under(self, hx, hy, hz):
        return math.hypot(hx - self.x, hy - self.y) <= self.r and hz < self.z_ring[1]

    def hook_inside(self, hx, hy):
        return math.hypot(hx - self.x, hy - self.y) <= self.r

    def reach(self):
        return self.r

    def snapshot(self):
        return {"state": self.state, "hidden": self.hidden, "x": round(self.x, 1), "y": round(self.y, 1),
                "z": round(self.height, 1)}


class Flag(Model):
    """A flag with a handle: a hook that goes under the handle and lifts raises it, and it stays up."""

    type = "flag"
    states = ("down", "raised")

    def __init__(self, spec):
        super().__init__(spec)
        self.x, self.y = _pair(spec, "at")
        self.w, self.h = _pair(spec, "size", [60, 60])
        self.handle_z = _num(spec, "handle_z", 70)
        self.raise_z = _num(spec, "raise_z", self.handle_z + 50)
        self.area = geometry.rect(self.x, self.y, self.w, self.h)
        self.pole = _pair(spec, "pole") if "pole" in spec else None

    def make_parts(self):
        if self.pole is None:
            return []
        return [Part(self, geometry.circle(*self.pole, 10), (0.0, 250.0))]

    def hook_inside(self, hx, hy):
        return geometry.contains(self.area, hx, hy)

    def hook_under(self, hx, hy, hz):
        return self.hook_inside(hx, hy) and hz < self.handle_z

    def reach(self):
        extra = math.hypot(self.pole[0] - self.x, self.pole[1] - self.y) + 10 if self.pole else 0
        return max(math.hypot(self.w, self.h) / 2, extra)


class Gate(Model):
    """A wall that opens when another model tells it to."""

    type = "gate"
    states = ("closed", "open")

    def __init__(self, spec):
        super().__init__(spec)
        self.x, self.y = _pair(spec, "at")
        self.w, self.h = _pair(spec, "size")
        self.angle = _num(spec, "angle", 0)
        self.z = _pair(spec, "z", [0, 100])

    def make_parts(self):
        if self.state == "open":
            return []
        return [Part(self, geometry.rect(self.x, self.y, self.w, self.h, self.angle), self.z)]

    def reach(self):
        return math.hypot(self.w, self.h) / 2


TYPES = {cls.type: cls for cls in (Block, Lever, Button, Loop, Flag, Gate)}


def make_model(spec):
    if not isinstance(spec, dict):
        raise ShapeError(f"a model must be a dictionary: {spec}")
    cls = TYPES.get(spec.get("type"))
    if cls is None:
        raise ShapeError(f"model {spec.get('id', '?')}: unknown type '{spec.get('type')}'. Use one of: {', '.join(TYPES)}")
    return cls(spec)
