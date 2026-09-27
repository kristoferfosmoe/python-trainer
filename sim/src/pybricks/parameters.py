"""Simulated ``pybricks.parameters``: ports, directions, colors and other constants."""


class _Constant:
    """A named constant such as ``Port.A``. Each one is a singleton."""

    _group = "?"

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"{self._group}.{self.name}"

    __str__ = __repr__


def _fill(cls, names):
    for name in names:
        setattr(cls, name, cls(name))
    cls._members = tuple(getattr(cls, name) for name in names)


class Port(_Constant):
    _group = "Port"


class Direction(_Constant):
    _group = "Direction"


class Stop(_Constant):
    _group = "Stop"


class Button(_Constant):
    _group = "Button"


class Side(_Constant):
    _group = "Side"


class Axis(_Constant):
    _group = "Axis"


class Icon(_Constant):
    _group = "Icon"


_fill(Port, ["A", "B", "C", "D", "E", "F"])
_fill(Direction, ["CLOCKWISE", "COUNTERCLOCKWISE"])
_fill(Stop, ["COAST", "COAST_SMART", "BRAKE", "HOLD", "NONE"])
_fill(Button, ["LEFT", "RIGHT", "CENTER", "BLUETOOTH"])
_fill(Side, ["TOP", "BOTTOM", "FRONT", "BACK", "LEFT", "RIGHT"])
_fill(Axis, ["X", "Y", "Z"])
_fill(Icon, [
    "HAPPY", "SAD", "HEART", "EMPTY", "FULL", "UP", "DOWN", "LEFT", "RIGHT",
    "ARROW_UP", "ARROW_DOWN", "ARROW_LEFT", "ARROW_RIGHT", "CIRCLE", "SQUARE",
    "TRIANGLE_UP", "TRIANGLE_DOWN", "TRIANGLE_LEFT", "TRIANGLE_RIGHT",
    "PAUSE", "EYE_LEFT", "EYE_RIGHT", "CLOCKWISE", "COUNTERCLOCKWISE", "TRUE", "FALSE",
])


# (h, s, v) values match real Pybricks.
_COLOR_VALUES = {
    "NONE": (0, 0, 0),
    "BLACK": (0, 0, 10),
    "GRAY": (0, 0, 50),
    "WHITE": (0, 0, 100),
    "RED": (0, 100, 100),
    "ORANGE": (30, 100, 100),
    "BROWN": (30, 100, 50),
    "YELLOW": (60, 100, 100),
    "GREEN": (120, 100, 100),
    "CYAN": (180, 100, 100),
    "BLUE": (240, 100, 100),
    "VIOLET": (270, 100, 100),
    "MAGENTA": (300, 100, 100),
}
_COLOR_NAMES = {hsv: name for name, hsv in _COLOR_VALUES.items()}


class Color:
    """A color with hue (0-359), saturation (0-100) and value/brightness (0-100)."""

    def __init__(self, h, s=100, v=100):
        self.h = int(h) % 360
        self.s = max(0, min(100, int(s)))
        self.v = max(0, min(100, int(v)))

    @property
    def name(self):
        return _COLOR_NAMES.get((self.h, self.s, self.v))

    def __eq__(self, other):
        return isinstance(other, Color) and (self.h, self.s, self.v) == (other.h, other.s, other.v)

    def __hash__(self):
        return hash((self.h, self.s, self.v))

    def __repr__(self):
        name = self.name
        if name:
            return f"Color.{name}"
        return f"Color(h={self.h}, s={self.s}, v={self.v})"

    __str__ = __repr__


for _name, _hsv in _COLOR_VALUES.items():
    setattr(Color, _name, Color(*_hsv))
del _name, _hsv
