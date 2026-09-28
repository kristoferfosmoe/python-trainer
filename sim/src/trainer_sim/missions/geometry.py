"""Convex polygons for Mission Mode: robot parts, attachments and models.

Everything is a convex polygon (circles are drawn with 16 sides), so one
separating-axis test answers "do these touch?" and "how far apart must
they move?". Units and angles follow shapes.py: millimeters, y up, headings
clockwise from +x.
"""

import math

CIRCLE_SIDES = 16


def rect(cx, cy, w, h, angle=0.0):
    """A w × h rectangle centered on (cx, cy), turned clockwise by `angle`."""
    r = math.radians(angle)
    c, s = math.cos(r), math.sin(r)
    points = []
    for lx, ly in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        points.append((cx + lx * c + ly * s, cy - lx * s + ly * c))
    return points


def circle(cx, cy, r):
    return [
        (cx + r * math.cos(2 * math.pi * i / CIRCLE_SIDES), cy + r * math.sin(2 * math.pi * i / CIRCLE_SIDES))
        for i in range(CIRCLE_SIDES)
    ]


def bar(ax, ay, bx, by, width):
    """A bar of `width` from point A to point B (a rectangle along AB)."""
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return rect(ax, ay, width, width)
    nx, ny = -dy / length * width / 2, dx / length * width / 2
    return [(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)]


def bounds(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def bounds_touch(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def center(poly):
    return sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)


def _axes(poly):
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        ax, ay = y1 - y2, x2 - x1
        length = math.hypot(ax, ay)
        if length > 1e-12:
            yield ax / length, ay / length


def _project(poly, ax, ay):
    values = [px * ax + py * ay for px, py in poly]
    return min(values), max(values)


def push_out(a, b):
    """How far polygon `a` must move to stop overlapping `b`, as (dx, dy), or None if they don't overlap."""
    best = None
    for poly in (a, b):
        for ax, ay in _axes(poly):
            amin, amax = _project(a, ax, ay)
            bmin, bmax = _project(b, ax, ay)
            overlap = min(amax, bmax) - max(amin, bmin)
            if overlap <= 1e-9:
                return None
            if best is None or overlap < best[0]:
                best = (overlap, ax, ay)
    overlap, ax, ay = best
    (acx, acy), (bcx, bcy) = center(a), center(b)
    if (acx - bcx) * ax + (acy - bcy) * ay < 0:
        ax, ay = -ax, -ay
    return ax * overlap, ay * overlap


def overlap(a, b):
    return push_out(a, b) is not None


def move(poly, dx, dy):
    return [(x + dx, y + dy) for x, y in poly]


def contains(poly, px, py):
    """Is the point inside the convex polygon (either winding)?"""
    sign = 0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cross = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
        if abs(cross) < 1e-9:
            continue
        s = 1 if cross > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    return True


def z_overlap(a, b):
    """Do two height ranges (low, high) overlap?"""
    return a[0] < b[1] and b[0] < a[1]
