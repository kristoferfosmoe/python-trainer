"""The mission field during a run: models, attachments and what touches what.

Simulation._tick calls `step()` once per physics tick, after the robot has
moved (only when the simulation has a mission; lessons and the playground
never get here). A step has four phases:

1. Arms. Each attachment whose motor turned is checked where the robot was.
   If it pushes into something solid, the motor's step is undone and it
   stalls, like the mechanical stops already do.
2. The robot. If the robot moved, its body and attachments are checked where
   it is now. Loose things get pushed; if something won't give way, the move
   is undone and the wheels stall, as with walls.
3. Hooks. A hook that goes under a loop or a flag's handle and then lifts
   carries the loop or raises the flag. Carried loops follow their hook.
4. Models. Levers spring back, buttons count presses, and links run.
"""

import math

from ..shapes import ShapeError, solid_hits_polygon
from . import geometry
from .attachments import Mounted
from .models import REMOVED, make_model

DEFAULT_BODY_HEIGHT = 90.0
NEAR_MARGIN = 30.0


class MissionField:
    def __init__(self, sim, model_specs, body_height=DEFAULT_BODY_HEIGHT):
        self.sim = sim
        self.world = sim.world
        self.models = {}
        for spec in model_specs:
            model = make_model(spec)
            if model.id in self.models:
                raise ShapeError(f"two models are called '{model.id}'")
            self.models[model.id] = model
        # A challenge can leave some of the game's models off the field; links
        # to those do nothing (resolve() checks every link names a real model).
        self.body_z = (0.0, float(body_height))
        self.mounts = {}
        self.robot_blocked_by = None
        self.under = set()  # (port, model id): a hook is under this loop or handle
        self.body_reach = math.hypot(max(sim.robot.front, sim.robot.back), sim.robot.half_width)
        self.listeners = []  # called with (model, old_state) when a model changes state
        self._states = {m.id: m.state for m in self.models.values()}
        # Recording (see Recorder in sim.py: one entry per recorded frame).
        self.initial = {m.id: m.snapshot() for m in self.models.values()}
        self._last = dict(self.initial)
        self.changes = []
        self.arms = {port: [] for port in ("E", "F") if port in sim.motors}
        self.mount_log = []
        self._frames_seen = 0

    # --- Attachments --------------------------------------------------------------

    def mount(self, spec, before_start=False):
        motor = self.sim.motors.get(spec.port)
        if motor is None:
            raise ShapeError(f"attachment {spec.id} goes on port {spec.port}, but the robot has no motor there")
        self.mounts[spec.port] = Mounted(spec, motor, before_start)
        self.mount_log.append([self._frame_index(), spec.port, spec.id])

    def unmount(self, port):
        mounted = self.mounts.pop(port, None)
        if mounted is None:
            return
        mounted.motor.min_angle = mounted.motor.max_angle = None
        self.mount_log.append([self._frame_index(), port, None])
        for model in self.models.values():
            if getattr(model, "carrier", None) == port:
                # The teammate takes it off the robot (in Home).
                model.carrier = None
                model.height = 0.0
                self._set_state(model, "dropped")

    # --- The robot's shapes -----------------------------------------------------------

    def pose(self):
        return self.sim.x, self.sim.y, self.sim.heading

    def robot_shapes(self, pose, body=True):
        """[(polygon, z range, mount or None)]: the body, then every attachment segment."""
        shapes = [(self.sim.robot.outline(*pose), self.body_z, None)] if body else []
        for mounted in self.mounts.values():
            shapes += [(poly, z, mounted) for poly, z in mounted.segments(pose)]
        return shapes

    def robot_touches(self, poly, z):
        box = geometry.bounds(poly)
        pose = self.pose()
        reach = self._reach()
        if box[0] > pose[0] + reach or box[2] < pose[0] - reach or box[1] > pose[1] + reach or box[3] < pose[1] - reach:
            return False
        for shape, shape_z, _ in self.robot_shapes(pose):
            if geometry.z_overlap(z, shape_z) and geometry.bounds_touch(box, geometry.bounds(shape)) \
                    and geometry.overlap(poly, shape):
                return True
        return False

    def _reach(self):
        return max([self.body_reach] + [m.reach() for m in self.mounts.values()])

    def _near(self, pose):
        reach = self._reach()
        near = []
        for model in self.models.values():
            where = model.position()
            if where is None:
                continue
            if math.hypot(where[0] - pose[0], where[1] - pose[1]) <= reach + model.reach() + NEAR_MARGIN:
                near.append(model)
        return near

    def shape_is_blocked(self, poly, z, ignore=None):
        """Would something pushed into this place hit a wall, an obstacle or another model?"""
        for x, y in poly:
            if x < 0 or y < 0 or x > self.world.width or y > self.world.height:
                return True
        for solid in self.world.obstacles:
            if solid_hits_polygon(solid, poly):
                return True
        box = geometry.bounds(poly)
        for model in self.models.values():
            if model is ignore:
                continue
            for part in model.parts():
                if geometry.z_overlap(z, part.z) and geometry.bounds_touch(box, part.bounds) \
                        and geometry.overlap(poly, part.poly):
                    return True
        return False

    def _push(self, shapes, near, check_obstacles, before=None):
        """Push everything these shapes overlap. Returns what blocked them, or None.

        `before` has each shape's height range before it moved. A shape that
        was above or below a part came down onto it (or up under it): that
        doesn't push the part sideways, it rests against it."""
        for index, (poly, z, mounted) in enumerate(shapes):
            box = geometry.bounds(poly)
            if check_obstacles or mounted is not None:
                for solid in self.world.obstacles:
                    if geometry.bounds_touch(box, solid.bbox) and solid_hits_polygon(solid, poly):
                        return solid.label or "obstacle"
            for model in near:
                for part in model.parts():
                    if not geometry.z_overlap(z, part.z) or not geometry.bounds_touch(box, part.bounds):
                        continue
                    if not geometry.overlap(part.poly, poly):
                        continue
                    if before is not None and not geometry.z_overlap(before[index], part.z):
                        return model.label
                    if part.solid or not model.push(part, poly, self):
                        return model.label
        return None

    # --- The physics tick -------------------------------------------------------------

    def step(self, old_pose, dt):
        sim = self.sim
        # 1. Arms that turned, with the robot where it was.
        for mounted in self.mounts.values():
            if mounted.motor.last_delta == 0:
                continue
            near = self._near(old_pose)
            if not near and not self.world.obstacles:
                continue
            before = [z for _, z in mounted.segments(old_pose, mounted.motor.angle - mounted.motor.last_delta)]
            shapes = [(poly, z, mounted) for poly, z in mounted.segments(old_pose)]
            hit = self._push(shapes, near, check_obstacles=False, before=before)
            if hit is None:
                mounted.blocked_by = None
                continue
            mounted.motor.block()
            if mounted.blocked_by != hit:
                self.event("blocked", port=mounted.port, what=hit)
            mounted.blocked_by = hit

        # 2. The robot, if it moved.
        pose = self.pose()
        if pose != old_pose:
            near = self._near(pose)
            hit = None
            if near or (self.mounts and self.world.obstacles):
                # The body was already checked against walls and obstacles (Simulation._move_robot).
                hit = self._push(self.robot_shapes(pose, body=bool(near)), near, check_obstacles=False)
            if hit is None:
                self.robot_blocked_by = None
            else:
                sim.x, sim.y, sim.heading = old_pose
                sim.speed = sim.turn_rate = 0.0
                for port in (sim.robot.left_port, sim.robot.right_port):
                    sim.motors[port].block()
                if self.robot_blocked_by != hit:
                    self.event("collision", what=hit)
                self.robot_blocked_by = hit

        # 3. Hooks.
        self._hooks()

        # 4. Models.
        for model in self.models.values():
            model.tick(self, dt)
        self._check_states()

    def _hooks(self):
        pose = self.pose()
        for port, mounted in self.mounts.items():
            hook = mounted.hook(pose)
            if hook is None:
                continue
            hx, hy, hz = hook
            for model in self.models.values():
                if model.hidden or model.type not in ("loop", "flag"):
                    continue
                if (model.type, model.state) not in (("loop", "on_post"), ("flag", "down")):
                    continue
                key = (port, model.id)
                if not model.hook_inside(hx, hy):
                    self.under.discard(key)
                elif model.hook_under(hx, hy, hz):
                    self.under.add(key)
                elif key in self.under and hz >= (model.lift_z if model.type == "loop" else model.raise_z):
                    self.under.discard(key)
                    if model.type == "loop":
                        model.carrier = port
                        model.moved()
                        self._set_state(model, "carried")
                    else:
                        self._set_state(model, "raised")
            for model in self.models.values():
                if model.type == "loop" and model.state == "carried" and model.carrier == port:
                    model.x, model.y, model.height = hx, hy, max(0.0, hz - 10)
                    if hz < model.drop_z:
                        model.carrier = None
                        model.height = 0.0
                        self._set_state(model, "dropped")

    # --- States and links ---------------------------------------------------------------

    def _set_state(self, model, state):
        model.state = state
        model.moved()
        self._check_states()

    def _check_states(self):
        for model in self.models.values():
            old = self._states[model.id]
            if model.state == old:
                continue
            self._states[model.id] = model.state
            self.event("state", model=model.id, state=model.state)
            for verb, target_id in model.links.get(model.state, []):
                target = self.models.get(target_id)
                if target is None:
                    continue
                if verb == "show":
                    target.hidden = False
                elif verb in ("open", "close") and target.type == "gate":
                    target.state = "open" if verb == "open" else "closed"
                target.moved()
            for listener in self.listeners:
                listener(model, old)

    def remove_carried(self):
        """Interruption: whatever the robot carries is taken off the field."""
        for model in self.models.values():
            if getattr(model, "carrier", None) is not None:
                model.carrier = None
                self._set_state(model, REMOVED)

    def event(self, kind, **data):
        """Record an event at physics time (the program's clock lags during a wait())."""
        sim = self.sim
        recorder = sim.recorder
        if len(recorder.events) >= recorder.MAX_EVENTS:
            return
        entry = {"t": round(max(sim.now, sim.phys_t), 2), "type": kind, "line": sim.current_line}
        entry.update(data)
        recorder.events.append(entry)

    # --- Recording --------------------------------------------------------------------------

    def _frame_index(self):
        return max(0, len(self.sim.recorder.frames["t"]) - 1)

    def record(self):
        """Called after every tick: when the recorder made a new frame, record the field too."""
        count = len(self.sim.recorder.frames["t"])
        new = self._frames_seen < count
        while self._frames_seen < count:
            self._frames_seen += 1
            frame = self._frames_seen - 1
            for port, angles in self.arms.items():
                mounted = self.mounts.get(port)
                angles.append(round(mounted.angle(), 1) if mounted else None)
            for model in self.models.values():
                snap = model.snapshot()
                if snap != self._last[model.id]:
                    self._last[model.id] = snap
                    self.changes.append([frame, model.id, snap])
        return new

    def to_dict(self):
        return {
            "initial": self.initial,
            "changes": self.changes,
            "arms": self.arms,
            "mounts": self.mount_log,
        }
