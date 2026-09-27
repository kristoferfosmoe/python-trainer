"""The mat the robot drives on: painted shapes, zones, obstacles and walls."""

import math

from .shapes import (
    COLOR_NAMES, ShapeError, make_area, make_paint, make_solid, ray_solid, solid_hits_polygon,
)

# FLL table inner size in millimeters.
DEFAULT_SIZE = (2362, 1143)

# How bright each mat color looks to the color sensor's reflection() (0-100).
REFLECTION = {
    "black": 9, "gray": 45, "white": 98, "red": 58, "orange": 68, "brown": 22,
    "yellow": 88, "green": 32, "cyan": 62, "blue": 28, "violet": 30, "magenta": 52,
}

# Radius (mm) of the spot the color sensor looks at.
SENSOR_SPOT = 6.0

# Farthest the ultrasonic sensor can see; Pybricks returns 2000 for "nothing".
ULTRASONIC_MAX = 2000
ULTRASONIC_MIN = 40


class World:
    def __init__(self, spec):
        if not isinstance(spec, dict):
            raise ShapeError("world must be a dictionary")
        self.id = spec.get("id", "world")
        self.name = spec.get("name", self.id)
        size = spec.get("size", DEFAULT_SIZE)
        self.width, self.height = float(size[0]), float(size[1])
        self.background = spec.get("background", "white")
        if self.background not in COLOR_NAMES:
            raise ShapeError(f"unknown background color '{self.background}'")
        self.shapes = [make_paint(s) for s in spec.get("shapes", [])]
        self.obstacles = [make_solid(s) for s in spec.get("obstacles", [])]
        self.zones = {}
        for z in spec.get("zones", []):
            zone = make_area(z)
            if zone.id in self.zones:
                raise ShapeError(f"two zones are named '{zone.id}'")
            self.zones[zone.id] = zone
        start = spec.get("start", {})
        self.start = (
            float(start.get("x", 200)),
            float(start.get("y", 200)),
            float(start.get("heading", 0)),
        )

    # --- Color sensor ---------------------------------------------------------

    def reflection(self, px, py, r=SENSOR_SPOT):
        """Reflected light (0-100), blending colors at the edges of shapes."""
        value = REFLECTION[self.background]
        for shape in self.shapes:
            cover = shape.coverage(px, py, r)
            if cover > 0:
                value += (REFLECTION[shape.color] - value) * cover
        return value

    def color_at(self, px, py, r=SENSOR_SPOT):
        """Name of the color that covers most of the sensor spot."""
        for shape in reversed(self.shapes):
            if shape.coverage(px, py, r) >= 0.5:
                return shape.color
        return self.background

    # --- Ultrasonic sensor ----------------------------------------------------

    def ray_distance(self, px, py, heading):
        """Distance (mm) to the nearest wall or obstacle straight ahead."""
        r = math.radians(heading)
        dx, dy = math.cos(r), -math.sin(r)
        best = math.inf
        if dx > 1e-9:
            best = min(best, (self.width - px) / dx)
        elif dx < -1e-9:
            best = min(best, -px / dx)
        if dy > 1e-9:
            best = min(best, (self.height - py) / dy)
        elif dy < -1e-9:
            best = min(best, -py / dy)
        for solid in self.obstacles:
            t = ray_solid(px, py, dx, dy, solid)
            if t is not None and t < best:
                best = t
        return best

    # --- Collisions -----------------------------------------------------------

    def collision(self, polygon):
        """What the robot's outline hits: 'wall', an obstacle label, or None."""
        for x, y in polygon:
            if x < 0 or y < 0 or x > self.width or y > self.height:
                return "wall"
        for solid in self.obstacles:
            if solid_hits_polygon(solid, polygon):
                return solid.label or "obstacle"
        return None

    def zone_at(self, zone_id):
        zone = self.zones.get(zone_id)
        if zone is None:
            raise ShapeError(f"there is no zone called '{zone_id}'")
        return zone
