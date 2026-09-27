"""A team's real robot: which port each part is plugged into and the wheel
sizes. The web app uses it to turn simulator code (written for the Trainer
Bot) into code for the team's robot. An empty dict means "built like the
Trainer Bot"."""

PORTS = ("A", "B", "C", "D", "E", "F")
DIRECTIONS = ("clockwise", "counterclockwise")

# Part -> (label, the Trainer Bot's port). Wheels are required; the rest can be
# left out when the robot doesn't have them.
PARTS = {
    "left_wheel": ("Left wheel motor", "A"),
    "right_wheel": ("Right wheel motor", "B"),
    "color_sensor": ("Color sensor", "C"),
    "ultrasonic_sensor": ("Distance sensor", "D"),
    "left_arm": ("Left arm motor", "E"),
    "right_arm": ("Right arm motor", "F"),
}
REQUIRED = ("left_wheel", "right_wheel")
LIMITS = {"wheel_diameter": (20, 200), "axle_track": (40, 400)}


class RobotError(ValueError):
    pass


def clean_robot(data):
    """Check a team robot and return it in a standard form. Raises RobotError."""
    if not data:
        return {}
    if not isinstance(data, dict):
        raise RobotError("The robot must be a dictionary.")
    unknown = set(data) - set(PARTS) - set(LIMITS) - {"left_direction", "right_direction"}
    if unknown:
        raise RobotError(f"Unknown robot settings: {', '.join(sorted(unknown))}.")
    robot = {}
    used = {}
    for part, (label, _) in PARTS.items():
        port = data.get(part)
        if port in (None, ""):
            if part in REQUIRED:
                raise RobotError(f"Pick a port for the {label.lower()}.")
            robot[part] = None
            continue
        port = str(port).upper()
        if port not in PORTS:
            raise RobotError(f"{label}: ports are A to F.")
        if port in used:
            raise RobotError(f"The {label.lower()} and the {used[port].lower()} can't both use port {port}.")
        used[port] = label
        robot[part] = port
    for side in ("left", "right"):
        direction = str(data.get(f"{side}_direction") or "").lower()
        if direction not in DIRECTIONS:
            raise RobotError(f"The {side} wheel's direction must be clockwise or counterclockwise.")
        robot[f"{side}_direction"] = direction
    for key, (low, high) in LIMITS.items():
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
            name = key.replace("_", " ")
            raise RobotError(f"The {name} must be a number of millimeters from {low} to {high}.")
        robot[key] = round(float(value), 1) if value % 1 else int(value)
    return robot
