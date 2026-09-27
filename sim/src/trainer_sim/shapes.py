"""2D shapes for mats, zones and obstacles.

World coordinates are millimeters with the origin at the bottom-left corner
of the mat, x to the right and y up. Angles follow Pybricks: degrees,
clockwise positive, with 0 pointing along +x.
"""

import math

COLOR_NAMES = (
    "black", "gray", "white", "red", "orange", "brown", "yellow",
    "green", "cyan", "blue", "violet", "magenta",
)


class ShapeError(ValueError):
    """A world or robot file has a mistake in it."""


def heading_vector(heading):
    """Unit vector pointing along a clockwise-positive heading."""
    r = math.radians(heading)
    return math.cos(r), -math.sin(r)


def to_world(x, y, heading, forward, left):
    """Convert a point on the robot (forward, left) to world coordinates."""
    r = math.radians(heading)
    c, s = math.cos(r), math.sin(r)
    return x + forward * c + left * s, y - forward * s + left * c


def disc_fraction_beyond(d, r):
    """Fraction of a disc (radius r) lying beyond a straight edge d away from its center.

    d > 0 means the edge is outside the disc's center, so less than half is covered.
    """
    if d >= r:
        return 0.0
    if d <= -r:
        return 1.0
    return (r * r * math.acos(d / r) - d * math.sqrt(r * r - d * d)) / (math.pi * r * r)


def _segment_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / length2
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _num(spec, key, default=None):
    value = spec.get(key, default)
    if value is None:
        raise ShapeError(f"{spec.get('type', 'shape')} is missing '{key}': {spec}")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ShapeError(f"'{key}' must be a number in {spec}")
    return float(value)


def _color(spec, required):
    color = spec.get("color")
    if color is None:
        if required:
            raise ShapeError(f"shape needs a 'color': {spec}")
        return None
    if color not in COLOR_NAMES:
        raise ShapeError(f"unknown color '{color}'. Use one of: {', '.join(COLOR_NAMES)}")
    return color


class Shape:
    kind = "shape"

    def __init__(self, spec, color_required):
        self.id = spec.get("id")
        self.label = spec.get("label", self.id)
        self.color = _color(spec, color_required)
        self.bbox = (0.0, 0.0, 0.0, 0.0)

    def signed_distance(self, px, py):
        raise NotImplementedError

    def contains(self, px, py):
        return self.signed_distance(px, py) <= 0

    def near(self, px, py, margin):
        x0, y0, x1, y1 = self.bbox
        return x0 - margin <= px <= x1 + margin and y0 - margin <= py <= y1 + margin

    def coverage(self, px, py, r):
        """Fraction (0-1) of a sensor spot of radius r that sees this shape."""
        if not self.near(px, py, r):
            return 0.0
        return disc_fraction_beyond(self.signed_distance(px, py), r)


class Rect(Shape):
    """Rectangle from its bottom-left corner (x, y), optionally rotated about its center."""

    kind = "rect"

    def __init__(self, spec, color_required):
        super().__init__(spec, color_required)
        x, y = _num(spec, "x"), _num(spec, "y")
        self.w, self.h = _num(spec, "w"), _num(spec, "h")
        if self.w <= 0 or self.h <= 0:
            raise ShapeError(f"rect needs a positive w and h: {spec}")
        self.angle = _num(spec, "angle", 0)
        self.cx, self.cy = x + self.w / 2, y + self.h / 2
        r = math.radians(self.angle)
        self._c, self._s = math.cos(r), math.sin(r)
        self.corners = [self._local_to_world(lx, ly) for lx, ly in (
            (-self.w / 2, -self.h / 2), (self.w / 2, -self.h / 2),
            (self.w / 2, self.h / 2), (-self.w / 2, self.h / 2),
        )]
        xs = [p[0] for p in self.corners]
        ys = [p[1] for p in self.corners]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))

    def _local_to_world(self, lx, ly):
        # Clockwise rotation in a y-up frame.
        return self.cx + lx * self._c + ly * self._s, self.cy - lx * self._s + ly * self._c

    def _world_to_local(self, px, py):
        dx, dy = px - self.cx, py - self.cy
        return dx * self._c - dy * self._s, dx * self._s + dy * self._c

    def signed_distance(self, px, py):
        lx, ly = self._world_to_local(px, py)
        qx, qy = abs(lx) - self.w / 2, abs(ly) - self.h / 2
        outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
        inside = min(max(qx, qy), 0.0)
        return outside + inside

    def to_dict(self):
        return {"type": "rect", "cx": self.cx, "cy": self.cy, "w": self.w, "h": self.h, "angle": self.angle}


class Circle(Shape):
    kind = "circle"

    def __init__(self, spec, color_required):
        super().__init__(spec, color_required)
        self.cx, self.cy, self.r = _num(spec, "x"), _num(spec, "y"), _num(spec, "r")
        if self.r <= 0:
            raise ShapeError(f"circle needs a positive r: {spec}")
        self.bbox = (self.cx - self.r, self.cy - self.r, self.cx + self.r, self.cy + self.r)

    def signed_distance(self, px, py):
        return math.hypot(px - self.cx, py - self.cy) - self.r


class _Band(Shape):
    """A painted stripe of some width around a center line (lines and arcs)."""

    def __init__(self, spec, color_required):
        super().__init__(spec, color_required)
        self.width = _num(spec, "width", 20)
        if self.width <= 0:
            raise ShapeError(f"width must be positive: {spec}")

    def center_distance(self, px, py):
        raise NotImplementedError

    def signed_distance(self, px, py):
        return self.center_distance(px, py) - self.width / 2

    def coverage(self, px, py, r):
        if not self.near(px, py, r):
            return 0.0
        c = self.center_distance(px, py)
        half = self.width / 2
        return max(0.0, disc_fraction_beyond(c - half, r) - disc_fraction_beyond(c + half, r))


class Line(_Band):
    """A line through two or more points, like a strip of tape."""

    kind = "line"

    def __init__(self, spec, color_required):
        super().__init__(spec, color_required)
        points = spec.get("points")
        if not isinstance(points, list) or len(points) < 2:
            raise ShapeError(f"line needs 'points' with at least two [x, y] pairs: {spec}")
        self.points = [(float(p[0]), float(p[1])) for p in points]
        if spec.get("closed"):
            self.points.append(self.points[0])
        half = self.width / 2
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        self.bbox = (min(xs) - half, min(ys) - half, max(xs) + half, max(ys) + half)

    def center_distance(self, px, py):
        pts = self.points
        return min(
            _segment_distance(px, py, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
            for i in range(len(pts) - 1)
        )


class Arc(_Band):
    """A curved stripe: part of a ring. Without start/end it's a full ring.

    ``start`` and ``end`` are headings (clockwise from +x); the arc sweeps
    clockwise from start to end.
    """

    kind = "arc"

    def __init__(self, spec, color_required):
        super().__init__(spec, color_required)
        self.cx, self.cy, self.r = _num(spec, "x"), _num(spec, "y"), _num(spec, "r")
        if "start" in spec or "end" in spec:
            self.start = _num(spec, "start", 0) % 360
            sweep = (_num(spec, "end", 360) - _num(spec, "start", 0)) % 360
            self.sweep = sweep if sweep > 0 else 360.0
        else:
            self.start, self.sweep = 0.0, 360.0
        reach = self.r + self.width / 2
        self.bbox = (self.cx - reach, self.cy - reach, self.cx + reach, self.cy + reach)

    def _point_at(self, heading):
        vx, vy = heading_vector(heading)
        return self.cx + self.r * vx, self.cy + self.r * vy

    def center_distance(self, px, py):
        dx, dy = px - self.cx, py - self.cy
        if self.sweep >= 360:
            return abs(math.hypot(dx, dy) - self.r)
        heading = math.degrees(math.atan2(-dy, dx))
        if (heading - self.start) % 360 <= self.sweep:
            return abs(math.hypot(dx, dy) - self.r)
        ax, ay = self._point_at(self.start)
        bx, by = self._point_at(self.start + self.sweep)
        return min(math.hypot(px - ax, py - ay), math.hypot(px - bx, py - by))


_PAINT_TYPES = {"rect": Rect, "circle": Circle, "line": Line, "arc": Arc}
_SOLID_TYPES = {"rect": Rect, "circle": Circle}


def make_paint(spec):
    """A painted shape on the mat (the color sensor can see it)."""
    cls = _PAINT_TYPES.get(spec.get("type"))
    if cls is None:
        raise ShapeError(f"unknown shape type '{spec.get('type')}'. Use one of: {', '.join(_PAINT_TYPES)}")
    return cls(spec, color_required=True)


def make_area(spec):
    """A zone: an invisible area used for goals (rect or circle)."""
    cls = _SOLID_TYPES.get(spec.get("type", "rect"))
    if cls is None:
        raise ShapeError(f"zones must be 'rect' or 'circle': {spec}")
    if not spec.get("id"):
        raise ShapeError(f"zones need an 'id': {spec}")
    return cls(spec, color_required=False)


def make_solid(spec):
    """An obstacle the robot bumps into (rect or circle)."""
    cls = _SOLID_TYPES.get(spec.get("type", "rect"))
    if cls is None:
        raise ShapeError(f"obstacles must be 'rect' or 'circle': {spec}")
    return cls(spec, color_required=False)


# --- Collision helpers -------------------------------------------------------

def _project(points, ax, ay):
    values = [px * ax + py * ay for px, py in points]
    return min(values), max(values)


def polygons_overlap(a, b):
    """Separating-axis test for two convex polygons given as lists of points."""
    for poly in (a, b):
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            ax, ay = y1 - y2, x2 - x1
            amin, amax = _project(a, ax, ay)
            bmin, bmax = _project(b, ax, ay)
            if amax <= bmin or bmax <= amin:
                return False
    return True


def circle_hits_polygon(cx, cy, r, poly):
    inside = True
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if _segment_distance(cx, cy, x1, y1, x2, y2) < r:
            return True
        # Check which side of each edge the center is on (polygon is convex).
        if (x2 - x1) * (cy - y1) - (y2 - y1) * (cx - x1) < 0:
            inside = False
    return inside


def solid_hits_polygon(solid, poly):
    if isinstance(solid, Circle):
        return circle_hits_polygon(solid.cx, solid.cy, solid.r, poly)
    return polygons_overlap(solid.corners, poly)


# --- Ray casting (ultrasonic sensor) -----------------------------------------

def ray_segment(px, py, dx, dy, ax, ay, bx, by):
    """Distance along the ray to segment AB, or None."""
    ex, ey = bx - ax, by - ay
    denom = dx * ey - dy * ex
    if abs(denom) < 1e-12:
        return None
    t = ((ax - px) * ey - (ay - py) * ex) / denom
    u = ((ax - px) * dy - (ay - py) * dx) / denom
    if t >= 0 and 0 <= u <= 1:
        return t
    return None


def ray_circle(px, py, dx, dy, cx, cy, r):
    fx, fy = px - cx, py - cy
    b = fx * dx + fy * dy
    c = fx * fx + fy * fy - r * r
    disc = b * b - c
    if disc < 0:
        return None
    root = math.sqrt(disc)
    for t in (-b - root, -b + root):
        if t >= 0:
            return t
    return None


def ray_solid(px, py, dx, dy, solid):
    if isinstance(solid, Circle):
        return ray_circle(px, py, dx, dy, solid.cx, solid.cy, solid.r)
    best = None
    corners = solid.corners
    for i in range(4):
        ax, ay = corners[i]
        bx, by = corners[(i + 1) % 4]
        t = ray_segment(px, py, dx, dy, ax, ay, bx, by)
        if t is not None and (best is None or t < best):
            best = t
    return best
